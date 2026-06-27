import subprocess
import json
from pathlib import Path

from app.models import CacheItem, RiskLevel, CleanupMethod
from .base_scanner import BaseScanner, ScanResult, get_dir_size


class DockerScanner(BaseScanner):
    name = "Docker"
    ecosystem = "Docker"
    icon = "docker"

    def scan(self) -> ScanResult:
        items = []
        errors = []

        if not self._docker_available():
            return self._make_result(items, errors)

        # Build cache
        build_cache = self._get_build_cache_size()
        if build_cache > 0:
            items.append(CacheItem(
                id="docker_build_cache",
                name="Docker build cache",
                ecosystem=self.ecosystem,
                path="Docker internal (BuildKit cache)",
                size_bytes=build_cache,
                risk_level=RiskLevel.SAFE,
                description="Docker layer and BuildKit build cache",
                long_description=(
                    "Intermediate image layers cached by Docker BuildKit to speed up repeated builds. "
                    "Safe to prune — your next build will just take a bit longer as layers are rebuilt."
                ),
                cleanup_method=CleanupMethod.COMMAND,
                cleanup_command="docker builder prune -f",
                icon_name="docker",
            ))

        # Dangling images
        dangling = self._get_dangling_images()
        if dangling["size"] > 0:
            items.append(CacheItem(
                id="docker_dangling",
                name="Dangling Docker images",
                ecosystem=self.ecosystem,
                path=f"Docker images ({dangling['count']} untagged)",
                size_bytes=dangling["size"],
                risk_level=RiskLevel.SAFE,
                description=f"{dangling['count']} untagged/dangling image layers",
                long_description=(
                    "Dangling images are untagged layers left over from previous builds. "
                    "They are not referenced by any container and can be safely removed."
                ),
                cleanup_method=CleanupMethod.COMMAND,
                cleanup_command="docker image prune -f",
                icon_name="docker",
            ))

        # Stopped containers
        stopped = self._get_stopped_containers()
        if stopped["count"] > 0:
            items.append(CacheItem(
                id="docker_stopped",
                name="Stopped containers",
                ecosystem=self.ecosystem,
                path=f"{stopped['count']} stopped container(s)",
                size_bytes=stopped["size"],
                risk_level=RiskLevel.REVIEW,
                description=f"{stopped['count']} stopped containers consuming disk",
                long_description=(
                    "Stopped (exited) containers still occupy disk space. "
                    "Safe to remove if you no longer need their filesystem state or logs."
                ),
                cleanup_method=CleanupMethod.COMMAND,
                cleanup_command="docker container prune -f",
                icon_name="docker",
            ))

        return self._make_result(items, errors)

    def _docker_available(self) -> bool:
        try:
            r = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
            return r.returncode == 0
        except Exception:
            return False

    def _get_build_cache_size(self) -> int:
        try:
            r = subprocess.run(
                ["docker", "system", "df", "--format", "{{json .}}"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                for line in r.stdout.strip().splitlines():
                    try:
                        obj = json.loads(line)
                        if obj.get("Type") == "Build Cache":
                            return self._parse_size(obj.get("Size", "0B"))
                    except Exception:
                        pass
        except Exception:
            pass
        return 0

    def _get_dangling_images(self) -> dict:
        try:
            r = subprocess.run(
                ["docker", "images", "-f", "dangling=true", "--format", "{{.Size}}"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                sizes = [self._parse_size(s.strip()) for s in r.stdout.splitlines() if s.strip()]
                return {"count": len(sizes), "size": sum(sizes)}
        except Exception:
            pass
        return {"count": 0, "size": 0}

    def _get_stopped_containers(self) -> dict:
        try:
            r = subprocess.run(
                ["docker", "ps", "-a", "-f", "status=exited", "--format", "{{.Size}}"],
                capture_output=True, text=True, timeout=15
            )
            if r.returncode == 0:
                lines = [l.strip() for l in r.stdout.splitlines() if l.strip()]
                # format is "Xkb (virtual Ykb)"
                sizes = []
                for l in lines:
                    part = l.split("(")[0].strip()
                    sizes.append(self._parse_size(part))
                return {"count": len(sizes), "size": sum(sizes)}
        except Exception:
            pass
        return {"count": 0, "size": 0}

    def _parse_size(self, s: str) -> int:
        """Parse Docker size strings like '1.2GB', '500MB', '2kB' to bytes."""
        s = s.strip().upper().replace(" ", "")
        if not s or s == "0B":
            return 0
        multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4,
                       "KIB": 1024, "MIB": 1024**2, "GIB": 1024**3}
        for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
            if s.endswith(suffix):
                try:
                    return int(float(s[:-len(suffix)]) * mult)
                except ValueError:
                    return 0
        try:
            return int(float(s))
        except ValueError:
            return 0
