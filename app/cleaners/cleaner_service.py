"""
CleanerService (v5)

Safety fixes
------------
* _path_is_safe now uses whole-path-component matching via is_path_component_match()
  (previously a substring match; "Documents_backup" would incorrectly block).
* _remove_tree_counted is now iterative (explicit stack) — eliminates Python
  recursion-limit risk on deep cache trees (some pip caches are 8+ levels deep).
* Consulted ignored_paths from the DB — users' protected directories are now
  actually honoured at the cleaner level, not just the UI.
* subprocess.run called with shell=False (explicit) for clarity.

Content Analysis (v5 new)
--------------------------
* analyze_directory() runs before any directory deletion (dry-run and real).
* In dry-run: flagged files appear in CleanResult.checks so user sees them
  in the DryRunResultDialog "Protected files" section.
* In real mode: flagged files are SKIPPED and the directory iterator avoids
  them — they remain on disk.  The list of preserved files is included in
  CleanResult.checks.

Performance
-----------
* _fast_dir_size is also iterative for the same reason.
"""
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

from loguru import logger

from app.models import CacheItem, CleanupMethod, RiskLevel
from app.database import log_cleanup, get_ignored_paths
from app.utils import fmt_bytes, is_path_component_match

# NOTE: content_analyzer is imported lazily inside _handle_directory to avoid
# circular imports: cleaner_service ← content_analyzer ← services/__init__
#                                                        ← scan_worker ← scanners
_content_analyzer = None

def _get_content_analyzer():
    global _content_analyzer
    if _content_analyzer is None:
        import importlib
        _content_analyzer = importlib.import_module("app.services.content_analyzer")
    return _content_analyzer


@dataclass
class CleanResult:
    success: bool
    bytes_reclaimed: float   # float to safely handle large AI model caches (>2 GB, int32 overflow)
    message: str
    error: Optional[str] = None
    dry_run: bool = False
    checks: List[str] = field(default_factory=list)
    content_warnings: List = field(default_factory=list)   # List[ContentWarning]
    preserved_files: List[str] = field(default_factory=list)  # files skipped in real mode


class CleanerService:

    # These names are checked as whole path components (not substrings)
    PROTECTED_COMPONENTS = {
        ".git", ".ssh", "Documents", "Desktop", "Downloads",
        "Pictures", "Music", "Videos",
    }

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        # Load user-defined protected paths once per service instance.
        # Fail-safe: if DB read fails we fall back to an empty set (no user
        # paths protected) rather than crashing — the hard-coded PROTECTED_COMPONENTS
        # list still guards the most critical paths.
        try:
            raw = get_ignored_paths()
            self._ignored_paths: set[Path] = set()
            for p in raw:
                try:
                    self._ignored_paths.add(Path(p).resolve())
                except Exception:
                    pass  # Skip unresolvable entries individually
        except Exception:
            self._ignored_paths = set()

    def clean(self, item: CacheItem) -> CleanResult:
        # ── safety gates ──────────────────────────────────────────────────────
        if item.risk_level == RiskLevel.DANGER:
            return CleanResult(False, 0,
                "Refused: DANGER items cannot be auto-cleaned.",
                error="risk_level=DANGER", dry_run=self.dry_run)

        blocked, reason = self._check_blocked(item.path)
        if blocked:
            return CleanResult(False, 0,
                f"Refused: {reason}",
                error="blocked_path", dry_run=self.dry_run)

        logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}Clean: {item.name}")

        try:
            if item.cleanup_method == CleanupMethod.COMMAND:
                result = self._handle_command(item)
            elif item.cleanup_method == CleanupMethod.DIRECTORY:
                result = self._handle_directory(item)
            else:
                result = CleanResult(False, 0, "No cleanup method for this item.",
                                     dry_run=self.dry_run)

            if not self.dry_run:
                log_cleanup(
                    cache_id=item.id, cache_name=item.name,
                    bytes_reclaimed=result.bytes_reclaimed if result.success else 0,
                    method=str(item.cleanup_method),
                    command=item.cleanup_command,
                    success=result.success, error=result.error,
                )
            return result

        except Exception as exc:
            logger.exception(f"Cleanup error for {item.name}")
            return CleanResult(False, 0, f"Unexpected error: {exc}",
                               error=str(exc), dry_run=self.dry_run)

    # ── safety ────────────────────────────────────────────────────────────────

    def _check_blocked(self, path_str: str) -> tuple[bool, str]:
        """Returns (is_blocked, reason_string).

        Fail-safe: any unexpected exception returns (True, reason) so that
        an unresolvable or suspicious path is BLOCKED, not silently permitted.
        """
        try:
            # Resolve to canonical form first — prevents symlink / relative-path bypass.
            # If resolution fails (broken symlink, permission error, etc.) we block.
            try:
                resolved = Path(path_str).resolve()
            except Exception as exc:
                return True, f"Cannot resolve path '{path_str}': {exc}"

            resolved_home = Path.home().resolve()

            # Hard-block: home root or anything above it
            if resolved == resolved_home:
                return True, f"'{path_str}' is the home directory"
            try:
                resolved.relative_to(resolved_home.parent)
                is_under_home_parent = True
            except ValueError:
                is_under_home_parent = False

            if not is_under_home_parent:
                # Completely outside the user's directory tree —
                # allow only known temp directory (e.g. /tmp on Linux,
                # /private/tmp on macOS — resolve() normalises the symlink).
                import tempfile
                tmp_resolved = Path(tempfile.gettempdir()).resolve()
                try:
                    resolved.relative_to(tmp_resolved)
                except ValueError:
                    return True, f"'{path_str}' is outside the home/temp directory hierarchy"
            else:
                # Under home.parent — but might be a sibling user's directory.
                # Allow only paths that are under home itself, OR under tmp.
                import tempfile
                tmp_resolved = Path(tempfile.gettempdir()).resolve()
                under_home = False
                under_tmp  = False
                try:
                    resolved.relative_to(resolved_home)
                    under_home = True
                except ValueError:
                    pass
                try:
                    resolved.relative_to(tmp_resolved)
                    under_tmp = True
                except ValueError:
                    pass
                if not under_home and not under_tmp:
                    return True, (
                        f"'{path_str}' is not inside your home directory or temp directory"
                    )

            # Never touch home root or filesystem root
            if resolved == resolved_home.parent or str(resolved) == "/":
                return True, f"'{path_str}' is a root directory"

            # User-defined ignored paths (exact prefix match on resolved path)
            for ignored in self._ignored_paths:
                try:
                    resolved.relative_to(ignored)
                    return True, f"'{path_str}' is inside a user-protected path ({ignored})"
                except ValueError:
                    pass

            # Protected path-component names — use the resolved path to prevent tricks
            for comp in self.PROTECTED_COMPONENTS:
                if is_path_component_match(str(resolved), comp):
                    return True, f"'{path_str}' contains protected component '{comp}'"

            return False, ""

        except Exception as exc:
            # Fail-safe: block on any unexpected error rather than silently permitting
            return True, f"Safety check error for '{path_str}': {exc}"

    # ── command handler ───────────────────────────────────────────────────────

    def _handle_command(self, item: CacheItem) -> CleanResult:
        if not item.cleanup_command:
            return CleanResult(False, 0, "No command specified.", dry_run=self.dry_run)

        first_line = item.cleanup_command.splitlines()[0]
        try:
            cmd_parts = shlex.split(first_line)
        except ValueError:
            cmd_parts = first_line.split()

        tool      = cmd_parts[0]
        tool_path = shutil.which(tool)
        checks: List[str] = []

        if self.dry_run:
            if tool_path:
                checks.append(f"✓ Tool found: {tool_path}")
            else:
                checks.append(f"✗ Tool not found in PATH: '{tool}'")

            path_obj = Path(item.path) if "internal" not in item.path.lower() else None
            if path_obj:
                if path_obj.exists():
                    size = self._dir_size_iterative(path_obj) if path_obj.is_dir() \
                           else path_obj.stat().st_size
                    checks.append(f"✓ Path exists: {item.path}")
                    checks.append(f"  Estimated reclaimable: {fmt_bytes(size)}")
                else:
                    size = item.size_bytes
                    checks.append(f"⚠ Path not found (tool may manage storage internally)")
            else:
                size = item.size_bytes
                checks.append("ℹ Storage is managed internally by the tool")

            if tool_path:
                checks.append(f"✓ Would run: {first_line}")
                return CleanResult(True, size,
                    f"Preflight OK — '{tool}' available, ~{fmt_bytes(size)} reclaimable.",
                    dry_run=True, checks=checks)
            elif path_obj and path_obj.exists():
                checks.append("  Fallback: would remove directory contents directly")
                return CleanResult(True, item.size_bytes,
                    f"Tool '{tool}' missing; directory fallback would reclaim ~{fmt_bytes(item.size_bytes)}.",
                    dry_run=True, checks=checks)
            else:
                checks.append("✗ Neither tool nor directory accessible — cleanup would fail")
                return CleanResult(False, 0,
                    f"Tool '{tool}' not available and path inaccessible.",
                    dry_run=True, checks=checks)

        # Real run
        if not tool_path:
            logger.warning(f"'{tool}' not found — falling back to directory removal")
            return self._handle_directory(item)

        try:
            proc = subprocess.run(
                cmd_parts,
                capture_output=True, text=True,
                timeout=120, shell=False,   # explicit shell=False
            )
            if proc.returncode == 0:
                return CleanResult(True, item.size_bytes,
                                   f"Command succeeded: {first_line}")
            return CleanResult(False, 0,
                f"Command failed (exit {proc.returncode}): {proc.stderr[:200]}",
                error=proc.stderr[:500])
        except subprocess.TimeoutExpired:
            return CleanResult(False, 0, "Command timed out (120 s).", "timeout")
        except FileNotFoundError:
            logger.warning(f"'{tool}' disappeared — falling back to directory removal")
            return self._handle_directory(item)

    # ── directory handler ─────────────────────────────────────────────────────

    def _handle_directory(self, item: CacheItem) -> CleanResult:
        path    = Path(item.path)
        checks: List[str] = []

        # ── Content analysis — runs in BOTH dry-run and real mode ─────────────
        cw_list = []
        if path.exists() and path.is_dir():
            try:
                ca = _get_content_analyzer()
                cw_list = ca.analyze_directory(str(path), item.id)
            except Exception as exc:
                logger.warning(f"Content analysis failed for {item.id}: {exc}")

        if self.dry_run:
            if not path.exists():
                checks.append(f"⚠ Path does not exist: {path}")
                return CleanResult(True, 0, "Path does not exist (already clean).",
                                   dry_run=True, checks=checks)
            if not path.is_dir():
                checks.append(f"✗ Not a directory: {path}")
                return CleanResult(False, 0, f"Not a directory: {path}",
                                   dry_run=True, checks=checks)

            size        = self._dir_size_iterative(path)
            child_count = sum(1 for _ in path.iterdir())
            writable    = os.access(str(path), os.W_OK)

            checks.append(f"✓ Path accessible: {path}")
            checks.append(f"  Contents: {child_count} top-level item(s), ~{fmt_bytes(size)}")
            checks.append(
                f"{'✓' if writable else '✗'} Write permission: "
                f"{'yes' if writable else 'no — some files may be skipped'}"
            )
            checks.append("  Would remove contents, keeping the directory itself")

            if cw_list:
                checks.append("")
                checks.append(f"⚠ {len(cw_list)} configuration file(s) detected — will be preserved:")
                for w in cw_list:
                    checks.append(f"  {w.icon} {w.relative}  ({w.label})")

            return CleanResult(True, size,
                f"Preflight OK — ~{fmt_bytes(size)} reclaimable.",
                dry_run=True, checks=checks, content_warnings=cw_list)

        if not path.exists():
            return CleanResult(True, 0, "Already clean (path not found).")
        if path.is_symlink():
            return CleanResult(False, 0,
                f"Refused: target path is a symlink — will not follow: {path}",
                "symlink_target")
        if not path.is_dir():
            return CleanResult(False, 0, f"Not a directory: {path}", "not_a_dir")

        # Build set of absolute paths to skip (flagged by content analysis)
        protected_abs: set[str] = {w.file_path for w in cw_list}
        preserved: List[str] = []

        removed, errors = 0, []
        for child in list(path.iterdir()):
            try:
                if child.is_dir() and not child.is_symlink():
                    r, p = self._remove_tree_counted_skipping(child, protected_abs)
                    removed   += r
                    preserved += p
                elif child.is_file() or child.is_symlink():
                    if str(child.resolve()) in protected_abs or str(child) in protected_abs:
                        preserved.append(str(child))
                        continue
                    try:
                        removed += child.stat().st_size
                    except OSError:
                        pass
                    child.unlink(missing_ok=True)
            except (OSError, PermissionError) as exc:
                errors.append(str(exc))

        if preserved:
            for fp in preserved:
                checks.append(f"🛡 Preserved: {Path(fp).name}  (configuration file — not deleted)")

        msg = f"Removed contents of {path}."
        if preserved:
            msg += f" {len(preserved)} config file(s) preserved."
        if errors:
            msg += f" ({len(errors)} item(s) skipped — permission denied)"
        return CleanResult(True, removed, msg,
                           content_warnings=cw_list, preserved_files=preserved,
                           checks=checks)

    # ── iterative tree operations (no recursion limit risk) ───────────────────

    def _remove_tree_counted_skipping(
        self, root: Path, protected_abs: set[str]
    ) -> tuple[int, list[str]]:
        """
        Iterative post-order directory removal that SKIPS files in protected_abs.
        Returns (bytes_removed, list_of_preserved_paths).
        """
        total     = 0
        preserved: list[str] = []
        dirs_to_remove: List[Path] = []
        stack = [root]

        while stack:
            current = stack.pop()
            dirs_to_remove.append(current)
            try:
                with os.scandir(current) as it:
                    for entry in it:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(Path(entry.path))
                            else:
                                ep = entry.path
                                if ep in protected_abs:
                                    preserved.append(ep)
                                    continue
                                try:
                                    total += entry.stat(follow_symlinks=False).st_size
                                except OSError:
                                    pass
                                try:
                                    os.unlink(ep)
                                except (OSError, PermissionError):
                                    pass
                        except (OSError, PermissionError):
                            pass
            except (OSError, PermissionError):
                pass

        # Remove dirs bottom-up — skip any that still contain preserved files
        for d in reversed(dirs_to_remove):
            try:
                os.rmdir(d)   # fails gracefully if dir not empty (preserved files)
            except (OSError, PermissionError):
                pass

        return total, preserved

    def _remove_tree_counted_iterative(self, root: Path) -> int:
        """
        Iterative post-order directory removal.
        Collects all dirs bottom-up then removes them in reverse order.
        Returns total bytes freed.  Never hits Python recursion limit.
        """
        total = 0
        dirs_to_remove: List[Path] = []
        stack = [root]

        while stack:
            current = stack.pop()
            dirs_to_remove.append(current)
            try:
                with os.scandir(current) as it:
                    for entry in it:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(Path(entry.path))
                            else:
                                try:
                                    total += entry.stat(follow_symlinks=False).st_size
                                except OSError:
                                    pass
                                try:
                                    os.unlink(entry.path)
                                except (OSError, PermissionError):
                                    pass
                        except (OSError, PermissionError):
                            pass
            except (OSError, PermissionError):
                pass

        # Remove directories bottom-up (reversed = deepest first)
        for d in reversed(dirs_to_remove):
            try:
                os.rmdir(d)
            except (OSError, PermissionError):
                pass

        return total

    def _dir_size_iterative(self, root: Path) -> int:
        """Iterative os.scandir size walk — no recursion limit risk."""
        total = 0
        stack = [root]
        while stack:
            current = stack.pop()
            try:
                with os.scandir(current) as it:
                    for entry in it:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(Path(entry.path))
                            elif entry.is_file(follow_symlinks=False):
                                total += entry.stat(follow_symlinks=False).st_size
                        except (OSError, PermissionError):
                            pass
            except (OSError, PermissionError):
                pass
        return total
