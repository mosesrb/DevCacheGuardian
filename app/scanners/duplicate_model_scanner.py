"""
DuplicateModelScanner — flagship Tier 2 feature.

Finds identical AI model files stored in multiple locations
(e.g. the same Llama-3-8B.gguf in LM Studio, Ollama, and Open WebUI).

Detection strategy
------------------
1. Walk all known AI model directories
2. For files >= MIN_SIZE_BYTES (100 MB — skips configs/tokenizers),
   compute a fast fingerprint: first+last 64 KB of file + file size.
   This is O(1) I/O instead of full SHA256, fast enough for interactive use.
3. Group by fingerprint. Groups with >1 file are duplicates.
4. For each duplicate group, emit one CacheItem whose path shows all locations
   and whose size_bytes is (copies-1) * file_size (the recoverable amount).

Full SHA256 verification is offered as a second pass when the user requests
it (via the detail panel / dry-run), but the fast fingerprint is sufficient
for discovery.

Risk level: REVIEW — the user must decide which copy to keep.
No auto-deletion ever for these items.
"""
from __future__ import annotations

import hashlib
import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.models import CacheItem, RiskLevel, CleanupMethod
from app.utils import fmt_bytes as _fmt
from .base_scanner import BaseScanner, ScanResult

# Minimum file size to consider (skip tokenizer configs, small JSONs)
MIN_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB

# How many bytes to read from start + end for fast fingerprint
SAMPLE_BYTES = 64 * 1024  # 64 KB each end


@dataclass
class _ModelFile:
    path: str
    size: int
    tool: str   # which AI tool owns this path


def _fast_fingerprint(path: str, size: int) -> Optional[str]:
    """
    Read SAMPLE_BYTES from start and end of file plus the exact size.
    Returns a hex string. Fast enough for files of any size.
    Returns None on I/O error.
    """
    try:
        h = hashlib.sha256()
        h.update(struct.pack(">Q", size))   # include size in fingerprint
        with open(path, "rb") as f:
            head = f.read(SAMPLE_BYTES)
            h.update(head)
            if size > SAMPLE_BYTES * 2:
                f.seek(-SAMPLE_BYTES, 2)
                tail = f.read(SAMPLE_BYTES)
                h.update(tail)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


def _known_ai_dirs() -> List[tuple[str, str]]:
    """
    Return (directory_path, tool_name) for all known AI model directories.
    Only includes paths that actually exist on disk.
    """
    home = Path.home()
    import platform
    system = platform.system()

    def e(p: str) -> str:
        return str(Path(os.path.expandvars(os.path.expanduser(p))))

    candidates = [
        # Hugging Face Hub
        (e("~/.cache/huggingface/hub"),         "Hugging Face"),
        # Ollama
        (e("~/.ollama/models"),                  "Ollama"),
        # LM Studio
        (e("~/.cache/lm-studio/models"),         "LM Studio"),
        (e("~/.lmstudio/models"),                "LM Studio"),
        # Open WebUI
        (e("~/.local/share/open-webui"),         "Open WebUI"),
        (e("~/.open-webui"),                     "Open WebUI"),
        # KoboldCPP
        (e("~/koboldcpp/models"),                "KoboldCPP"),
        (e("~/KoboldCPP/models"),                "KoboldCPP"),
        # Text Generation WebUI
        (e("~/text-generation-webui/models"),    "Text Gen WebUI"),
        # ComfyUI
        (e("~/ComfyUI/models"),                  "ComfyUI"),
        (e("~/comfyui/models"),                  "ComfyUI"),
        # Automatic1111
        (e("~/stable-diffusion-webui/models"),   "Automatic1111"),
        # ForgeUI
        (e("~/stable-diffusion-webui-forge/models"), "ForgeUI"),
        # PyTorch hub
        (e("~/.cache/torch/hub"),                "PyTorch Hub"),
    ]

    if system == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        appdata = os.environ.get("APPDATA", "")
        if local:
            candidates += [
                (str(Path(local) / "LM-Studio" / "models"),   "LM Studio"),
                (str(Path(appdata) / "LM Studio" / "models"), "LM Studio") if appdata else None,
            ]
        # Windows Ollama
        candidates.append((e("%USERPROFILE%\\.ollama\\models"), "Ollama"))

    return [(p, t) for p, t in candidates if p and Path(p).exists()]


class DuplicateModelScanner(BaseScanner):
    name      = "Duplicate AI Models"
    ecosystem = "AI/ML"
    icon      = "copy"

    def scan(self) -> ScanResult:
        items = []
        errors = []

        # Collect all model files from all known dirs
        all_files: List[_ModelFile] = []
        seen_paths: set = set()

        for dir_path, tool_name in _known_ai_dirs():
            try:
                for root, _, fnames in os.walk(dir_path):
                    for fname in fnames:
                        fpath = os.path.join(root, fname)
                        if fpath in seen_paths:
                            continue
                        # Only scan known model file extensions
                        ext = Path(fname).suffix.lower()
                        if ext not in {".gguf", ".bin", ".safetensors", ".ckpt",
                                       ".pt", ".pth", ".ggml", ".q4_0", ".q8_0"}:
                            continue
                        try:
                            size = os.path.getsize(fpath)
                            if size >= MIN_SIZE_BYTES:
                                seen_paths.add(fpath)
                                all_files.append(_ModelFile(fpath, size, tool_name))
                        except OSError:
                            pass
            except (OSError, PermissionError) as exc:
                errors.append(f"{tool_name}: {exc}")

        if not all_files:
            return self._make_result([], errors)

        # Fingerprint and group
        fingerprint_map: Dict[str, List[_ModelFile]] = {}
        for mf in all_files:
            fp = _fast_fingerprint(mf.path, mf.size)
            if fp is None:
                continue
            fingerprint_map.setdefault(fp, []).append(mf)

        # Emit one CacheItem per duplicate group
        dup_id = 0
        for fp, group in fingerprint_map.items():
            if len(group) < 2:
                continue

            dup_id += 1
            fname       = Path(group[0].path).name
            file_size   = group[0].size
            recoverable = file_size * (len(group) - 1)
            tools       = sorted({m.tool for m in group})
            paths_desc  = "\n".join(f"  [{m.tool}]  {m.path}" for m in group)

            items.append(CacheItem(
                id=f"dup_model_{dup_id}",
                name=f"Duplicate: {fname}",
                ecosystem=self.ecosystem,
                path=group[0].path,          # primary path (best copy to keep)
                size_bytes=recoverable,
                risk_level=RiskLevel.REVIEW,
                description=(
                    f"{len(group)} identical copies in "
                    f"{', '.join(tools)} — {_fmt(recoverable)} recoverable"
                ),
                long_description=(
                    f"The model file '{fname}' ({_fmt(file_size)}) exists in "
                    f"{len(group)} locations:\n\n{paths_desc}\n\n"
                    f"Keeping one copy and removing the others would recover "
                    f"{_fmt(recoverable)}. "
                    f"Detected via fast fingerprint (file size + head/tail bytes). "
                    f"Verify before deleting — different quantization levels can "
                    f"have similar names but different content."
                ),
                cleanup_method=CleanupMethod.NONE,   # user must choose which to keep
                icon_name="copy",
            ))

        return self._make_result(items, errors)
