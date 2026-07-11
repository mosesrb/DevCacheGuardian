"""
AIExtendedScanner (v7) — full AI ecosystem coverage per roadmap:

Local LLM runners:      LM Studio, Open WebUI, KoboldCPP, Text Generation WebUI
Image generation:       ComfyUI, Automatic1111, ForgeUI, Stable Diffusion (general)
AI dev tools:           Cursor cache, Claude Desktop cache, VS Code AI cache
"""
import os
import platform
from pathlib import Path
from typing import List

from app.models import CacheItem, RiskLevel, CleanupMethod
from .base_scanner import BaseScanner, ScanResult, get_dir_size, expand_path

_SYSTEM = platform.system()
_HOME   = Path.home()


def _win(rel): return Path(expand_path(f"%USERPROFILE%\\{rel}"))
def _applocal(rel):
    if _SYSTEM == "Windows": return Path(expand_path(f"%LOCALAPPDATA%\\{rel}"))
    if _SYSTEM == "Darwin":  return _HOME / "Library" / "Caches" / rel
    xdg = os.environ.get("XDG_CACHE_HOME", str(_HOME / ".cache"))
    return Path(xdg) / rel
def _appdata(rel):
    if _SYSTEM == "Windows": return Path(expand_path(f"%APPDATA%\\{rel}"))
    if _SYSTEM == "Darwin":  return _HOME / "Library" / "Application Support" / rel
    return _HOME / ".config" / rel


class AIExtendedScanner(BaseScanner):
    name      = "AI Tools (Extended)"
    ecosystem = "AI/ML"
    icon      = "brain"

    def scan(self) -> ScanResult:
        items: List[CacheItem] = []
        self._scan_lm_studio(items)
        self._scan_open_webui(items)
        self._scan_koboldcpp(items)
        self._scan_tgwui(items)
        self._scan_comfyui(items)
        self._scan_a1111(items)
        self._scan_forge(items)
        self._scan_sd_general(items)
        self._scan_cursor(items)
        self._scan_claude_desktop(items)
        self._scan_vscode_ai(items)
        return self._make_result(items)

    # ── LM Studio ─────────────────────────────────────────────────────────────
    def _scan_lm_studio(self, items):
        candidates = [
            _HOME / ".cache" / "lm-studio" / "models",
            _appdata("LM Studio") / "models",
        ]
        if _SYSTEM == "Windows":
            candidates += [_win(".cache\\lm-studio\\models"),
                           _win("AppData\\Local\\LM-Studio\\models")]
        for p in candidates:
            if p.exists():
                size = get_dir_size(str(p), stop_event=self._stop)
                if size > 0:
                    count = sum(1 for _ in p.rglob("*.gguf"))
                    items.append(CacheItem(
                        id="lm_studio_models", name="LM Studio models",
                        ecosystem=self.ecosystem, path=str(p), size_bytes=size,
                        risk_level=RiskLevel.REVIEW,
                        description=f"LM Studio downloaded models ({count} GGUF files)",
                        long_description=(
                            f"LM Studio stores {count} local model files here. "
                            "Large GGUF quantized models, re-downloadable from Hugging Face Hub. "
                            "Remove individual models from within LM Studio for safest cleanup."
                        ),
                        cleanup_method=CleanupMethod.NONE, icon_name="brain",
                    ))
                    break

    # ── Open WebUI ────────────────────────────────────────────────────────────
    def _scan_open_webui(self, items):
        # Open WebUI stores its data (including uploaded/cached models) in
        # a configurable DATA_DIR, defaulting to ~/.local/share/open-webui
        # or a Docker volume. We check the common non-Docker path.
        candidates = [
            _HOME / ".local" / "share" / "open-webui",
            _HOME / ".open-webui",
            _appdata("open-webui"),
        ]
        if _SYSTEM == "Windows":
            candidates.append(_win("AppData\\Local\\open-webui"))
        for p in candidates:
            if p.exists():
                size = get_dir_size(str(p), stop_event=self._stop)
                if size > 0:
                    items.append(CacheItem(
                        id="open_webui_data", name="Open WebUI data",
                        ecosystem=self.ecosystem, path=str(p), size_bytes=size,
                        risk_level=RiskLevel.REVIEW,
                        description="Open WebUI application data and model cache",
                        long_description=(
                            "Open WebUI stores its database, uploaded files, and cached "
                            "model data here. The models subdirectory may contain large "
                            "GGUF files if models were downloaded through the WebUI. "
                            "Do not delete if you have active users or important conversation history."
                        ),
                        cleanup_method=CleanupMethod.NONE, icon_name="brain",
                    ))
                    break

    # ── KoboldCPP ─────────────────────────────────────────────────────────────
    def _scan_koboldcpp(self, items):
        candidates = [
            _HOME / "koboldcpp" / "models",
            _HOME / "KoboldCPP" / "models",
            _HOME / ".koboldcpp" / "models",
        ]
        for p in candidates:
            if p.exists():
                size = get_dir_size(str(p), stop_event=self._stop)
                if size > 0:
                    items.append(CacheItem(
                        id="koboldcpp_models", name="KoboldCPP models",
                        ecosystem=self.ecosystem, path=str(p), size_bytes=size,
                        risk_level=RiskLevel.REVIEW,
                        description="KoboldCPP local LLM model files",
                        long_description=(
                            "GGUF model files used by KoboldCPP for local LLM inference. "
                            "Re-downloadable from Hugging Face Hub."
                        ),
                        cleanup_method=CleanupMethod.NONE, icon_name="brain",
                    ))
                    break

    # ── Text Generation WebUI (oobabooga) ─────────────────────────────────────
    def _scan_tgwui(self, items):
        candidates = [
            _HOME / "text-generation-webui" / "models",
            _HOME / "oobabooga" / "text-generation-webui" / "models",
            _HOME / "textgen-webui" / "models",
        ]
        for p in candidates:
            if p.exists():
                size = get_dir_size(str(p), stop_event=self._stop)
                if size > 0:
                    items.append(CacheItem(
                        id="tgwui_models", name="Text Generation WebUI models",
                        ecosystem=self.ecosystem, path=str(p), size_bytes=size,
                        risk_level=RiskLevel.REVIEW,
                        description="oobabooga Text Generation WebUI model files",
                        long_description=(
                            "Models downloaded for the oobabooga Text Generation WebUI. "
                            "Supports GGUF, GPTQ, AWQ, and full-precision models. "
                            "Re-downloadable from Hugging Face Hub."
                        ),
                        cleanup_method=CleanupMethod.NONE, icon_name="brain",
                    ))
                    break

    # ── ComfyUI ────────────────────────────────────────────────────────────────
    def _scan_comfyui(self, items):
        candidates = [
            _HOME / "ComfyUI" / "models",
            _HOME / "comfyui" / "models",
        ]
        if _SYSTEM == "Windows":
            candidates += [_win("ComfyUI\\models"), _win("comfyui\\models")]
        for p in candidates:
            if p.exists():
                size = get_dir_size(str(p), stop_event=self._stop)
                if size > 0:
                    items.append(CacheItem(
                        id="comfyui_models", name="ComfyUI models",
                        ecosystem=self.ecosystem, path=str(p), size_bytes=size,
                        risk_level=RiskLevel.REVIEW,
                        description="ComfyUI Stable Diffusion model files",
                        long_description=(
                            "ComfyUI models directory containing checkpoints, LoRAs, VAEs, "
                            "ControlNets, and other model files. Re-downloadable from "
                            "Civitai or Hugging Face."
                        ),
                        cleanup_method=CleanupMethod.NONE, icon_name="photo",
                    ))
                    break

    # ── Automatic1111 ─────────────────────────────────────────────────────────
    def _scan_a1111(self, items):
        candidates = [
            _HOME / "stable-diffusion-webui" / "models" / "Stable-diffusion",
            _HOME / "sd-webui" / "models" / "Stable-diffusion",
        ]
        for p in candidates:
            if p.exists():
                size = get_dir_size(str(p), stop_event=self._stop)
                if size > 0:
                    items.append(CacheItem(
                        id="a1111_models", name="Automatic1111 WebUI models",
                        ecosystem=self.ecosystem, path=str(p), size_bytes=size,
                        risk_level=RiskLevel.REVIEW,
                        description="Stable Diffusion WebUI checkpoint files",
                        long_description=(
                            "Model checkpoints for Automatic1111 Stable Diffusion WebUI. "
                            "Typically 2-7 GB each. Remove unused checkpoints manually "
                            "from the models/Stable-diffusion folder."
                        ),
                        cleanup_method=CleanupMethod.NONE, icon_name="photo",
                    ))
                    break

    # ── ForgeUI (separate from A1111) ─────────────────────────────────────────
    def _scan_forge(self, items):
        candidates = [
            _HOME / "stable-diffusion-webui-forge" / "models" / "Stable-diffusion",
            _HOME / "sd-webui-forge" / "models" / "Stable-diffusion",
            _HOME / "forge" / "models" / "Stable-diffusion",
        ]
        for p in candidates:
            if p.exists():
                size = get_dir_size(str(p), stop_event=self._stop)
                if size > 0:
                    items.append(CacheItem(
                        id="forge_models", name="ForgeUI models",
                        ecosystem=self.ecosystem, path=str(p), size_bytes=size,
                        risk_level=RiskLevel.REVIEW,
                        description="Stable Diffusion ForgeUI checkpoint files",
                        long_description=(
                            "Model checkpoints for ForgeUI (the Forge fork of Automatic1111). "
                            "Typically 2-7 GB each. Separate install from Automatic1111."
                        ),
                        cleanup_method=CleanupMethod.NONE, icon_name="photo",
                    ))
                    break

    # ── Stable Diffusion general model directory ───────────────────────────────
    def _scan_sd_general(self, items):
        """Catch-all for standalone SD model folders not tied to a specific WebUI."""
        candidates = [
            _HOME / "stable-diffusion" / "models",
            _HOME / "StableDiffusion" / "models",
            _HOME / "sd_models",
            _HOME / ".sd_models",
        ]
        for p in candidates:
            if p.exists():
                size = get_dir_size(str(p), stop_event=self._stop)
                if size > 0:
                    items.append(CacheItem(
                        id="sd_models_general", name="Stable Diffusion models (standalone)",
                        ecosystem=self.ecosystem, path=str(p), size_bytes=size,
                        risk_level=RiskLevel.REVIEW,
                        description="Standalone Stable Diffusion model checkpoint files",
                        long_description=(
                            "Stable Diffusion model checkpoints stored outside of a specific "
                            "WebUI installation. Typically .safetensors or .ckpt files. "
                            "Re-downloadable from Civitai or Hugging Face."
                        ),
                        cleanup_method=CleanupMethod.NONE, icon_name="photo",
                    ))
                    break

    # ── Cursor IDE cache ───────────────────────────────────────────────────────
    def _scan_cursor(self, items):
        p = _appdata("Cursor") / "Cache"
        if _SYSTEM == "Darwin": p = _HOME / "Library" / "Caches" / "Cursor"
        if p.exists():
            size = get_dir_size(str(p), stop_event=self._stop)
            if size > 0:
                items.append(CacheItem(
                    id="cursor_cache", name="Cursor IDE cache",
                    ecosystem=self.ecosystem, path=str(p), size_bytes=size,
                    risk_level=RiskLevel.SAFE,
                    description="Cursor AI IDE application cache",
                    long_description=(
                        "Application cache for the Cursor AI-powered IDE. "
                        "Safe to delete — Cursor rebuilds on next launch."
                    ),
                    cleanup_method=CleanupMethod.DIRECTORY, icon_name="code",
                ))

    # ── Claude Desktop cache ───────────────────────────────────────────────────
    def _scan_claude_desktop(self, items):
        p = _appdata("Claude") / "Cache"
        if _SYSTEM == "Darwin": p = _HOME / "Library" / "Caches" / "Claude"
        if p.exists():
            size = get_dir_size(str(p), stop_event=self._stop)
            if size > 0:
                items.append(CacheItem(
                    id="claude_desktop_cache", name="Claude Desktop cache",
                    ecosystem=self.ecosystem, path=str(p), size_bytes=size,
                    risk_level=RiskLevel.SAFE,
                    description="Claude Desktop application cache (Anthropic)",
                    long_description=(
                        "Application cache for Claude Desktop by Anthropic. "
                        "Safe to clear — Claude Desktop rebuilds on next launch."
                    ),
                    cleanup_method=CleanupMethod.DIRECTORY, icon_name="brain",
                ))

    # ── VS Code AI extension cache ─────────────────────────────────────────────
    def _scan_vscode_ai(self, items):
        if _SYSTEM == "Darwin":
            p = _HOME / "Library" / "Application Support" / "Code" / "Cache"
        elif _SYSTEM == "Windows":
            p = _appdata("Code") / "Cache"
        else:
            p = _HOME / ".config" / "Code" / "Cache"
        if p.exists():
            size = get_dir_size(str(p), stop_event=self._stop)
            if size > 0:
                items.append(CacheItem(
                    id="vscode_ai_cache", name="VS Code AI extension cache",
                    ecosystem=self.ecosystem, path=str(p), size_bytes=size,
                    risk_level=RiskLevel.SAFE,
                    description="GitHub Copilot / Codeium / Continue.dev cache",
                    long_description=(
                        "Cache used by VS Code AI extensions including GitHub Copilot, "
                        "Codeium, Continue.dev, and similar. Safe to clear."
                    ),
                    cleanup_method=CleanupMethod.DIRECTORY, icon_name="code",
                ))
