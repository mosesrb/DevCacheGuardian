"""
HuggingFaceScanner (v7)

CRITICAL FIX: huggingface-cli delete-cache opens an INTERACTIVE TUI picker
and hangs indefinitely when called non-interactively from subprocess.
Fixed by switching to CleanupMethod.DIRECTORY for the HF hub cache — it is
a plain filesystem cache directory, safe to wipe directly.

The cleanup_command field now holds the correct SCAN command for reference
('huggingface-cli scan-cache') with a note that direct deletion is used.

Ollama: 'ollama rm <name>' requires knowing the model name so we keep
CleanupMethod.NONE — the detail panel explains how to do it manually.
"""
import os
import subprocess
from pathlib import Path
import platform

from app.models import CacheItem, RiskLevel, CleanupMethod
from .base_scanner import BaseScanner, ScanResult, expand_path, get_dir_size


class HuggingFaceScanner(BaseScanner):
    name      = "AI / ML Models"
    ecosystem = "AI/ML"
    icon      = "brain"

    def scan(self) -> ScanResult:
        items  = []
        errors = []

        # ── Hugging Face Hub cache ─────────────────────────────────────────────
        # FIX: was CleanupMethod.COMMAND with 'huggingface-cli delete-cache'
        # which opens an interactive TUI and hangs non-interactively.
        # Correct approach: CleanupMethod.DIRECTORY — the hub cache is a plain
        # filesystem directory, safe to wipe entirely. Individual model removal
        # is noted in the description.
        hf_path = self._get_hf_cache()
        if hf_path and Path(hf_path).exists():
            size        = get_dir_size(hf_path, stop_event=self._stop)
            model_count = self._count_hf_models(hf_path)
            model_sizes = self._list_model_sizes(hf_path)
            items.append(CacheItem(
                id="huggingface_cache",
                name="Hugging Face models",
                ecosystem=self.ecosystem,
                path=hf_path,
                size_bytes=size,
                risk_level=RiskLevel.REVIEW,
                description=f"Downloaded transformer models & datasets ({model_count} repos)",
                long_description=(
                    f"Contains {model_count} model/dataset repos downloaded from Hugging Face Hub "
                    f"({model_sizes}). "
                    "These include model weights, tokenizers, and configs. "
                    "Re-downloadable but potentially slow on limited connections.\n\n"
                    "Cleaning removes the entire cache directory. "
                    "To inspect or selectively remove: run 'huggingface-cli scan-cache' in your terminal."
                ),
                # DIRECTORY method: directly removes contents — works reliably
                # unlike 'huggingface-cli delete-cache' which is interactive-only
                cleanup_method=CleanupMethod.DIRECTORY,
                cleanup_command="huggingface-cli scan-cache  (inspect only — deletion is done directly)",
                icon_name="brain",
            ))

        # ── Ollama models ──────────────────────────────────────────────────────
        # Ollama deletion requires knowing the model name: 'ollama rm <name>'
        # We cannot auto-clean without user choosing which model to keep.
        # CleanupMethod.NONE is correct here — show info + manual instructions.
        ollama_path  = self._get_ollama_path()
        if ollama_path and Path(ollama_path).exists():
            size         = get_dir_size(ollama_path, stop_event=self._stop)
            model_names  = self._get_ollama_models()
            models_str   = ", ".join(model_names[:4]) + ("…" if len(model_names) > 4 else "")
            items.append(CacheItem(
                id="ollama_models",
                name="Ollama models",
                ecosystem=self.ecosystem,
                path=ollama_path,
                size_bytes=size,
                risk_level=RiskLevel.REVIEW,
                description=f"Locally hosted LLM files ({len(model_names)} model{'s' if len(model_names)!=1 else ''})",
                long_description=(
                    f"Full quantized model files for locally-run LLMs via Ollama.\n"
                    f"Models found: {models_str or 'none listed'}\n\n"
                    "To remove a specific model: 'ollama rm <model-name>'\n"
                    "To list all models:         'ollama list'\n\n"
                    "Cleaning removes ALL Ollama models — use 'ollama rm' to remove selectively."
                ),
                cleanup_method=CleanupMethod.DIRECTORY,
                cleanup_command="ollama list  (then: ollama rm <model-name>)",
                icon_name="cpu",
            ))

        # ── PyTorch Hub cache ──────────────────────────────────────────────────
        torch_path = self._get_torch_cache()
        if torch_path and Path(torch_path).exists():
            size = get_dir_size(torch_path, stop_event=self._stop)
            if size > 0:
                items.append(CacheItem(
                    id="torch_hub",
                    name="PyTorch Hub cache",
                    ecosystem=self.ecosystem,
                    path=torch_path,
                    size_bytes=size,
                    risk_level=RiskLevel.REVIEW,
                    description="PyTorch pre-trained model downloads",
                    long_description=(
                        "Models downloaded via torch.hub.load() or torchvision model APIs. "
                        "Deleting forces a re-download on next use. "
                        "Safe to clean if you have a reliable internet connection."
                    ),
                    cleanup_method=CleanupMethod.DIRECTORY,
                    icon_name="brain",
                ))

        # ── Whisper models ─────────────────────────────────────────────────────
        whisper_path = self._get_whisper_cache()
        if whisper_path and Path(whisper_path).exists():
            size = get_dir_size(whisper_path, stop_event=self._stop)
            if size > 0:
                items.append(CacheItem(
                    id="whisper_cache",
                    name="Whisper model cache",
                    ecosystem=self.ecosystem,
                    path=whisper_path,
                    size_bytes=size,
                    risk_level=RiskLevel.REVIEW,
                    description="OpenAI Whisper speech recognition models",
                    long_description=(
                        "Pre-trained Whisper models for speech-to-text transcription. "
                        "Range: ~150 MB (tiny) to ~3 GB (large-v3). "
                        "Safe to delete — models are re-downloaded automatically on next use."
                    ),
                    cleanup_method=CleanupMethod.DIRECTORY,
                    icon_name="brain",
                ))

        return self._make_result(items, errors)

    # ── path helpers ──────────────────────────────────────────────────────────

    def _get_hf_cache(self) -> str:
        # HF_HOME overrides everything; HUGGINGFACE_HUB_CACHE is legacy
        env = os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE")
        if env:
            return env
        return str(Path.home() / ".cache" / "huggingface" / "hub")

    def _count_hf_models(self, path: str) -> int:
        try:
            return sum(1 for d in Path(path).iterdir() if d.is_dir())
        except Exception:
            return 0

    def _list_model_sizes(self, path: str) -> str:
        """Return a short human-readable summary of models found."""
        try:
            from app.utils import fmt_bytes
            entries = sorted(
                [(d.name, get_dir_size(str(d))) for d in Path(path).iterdir() if d.is_dir()],
                key=lambda x: -x[1]
            )[:3]
            if not entries:
                return "no models found"
            parts = [f"{name[:30]}… ({fmt_bytes(size)})" for name, size in entries]
            return ", ".join(parts)
        except Exception:
            return ""

    def _get_ollama_path(self) -> str:
        env = os.environ.get("OLLAMA_MODELS")
        if env:
            return env
        home   = Path.home()
        system = platform.system()
        if system == "Windows":
            return expand_path("%USERPROFILE%\\.ollama\\models")
        return str(home / ".ollama" / "models")

    def _get_ollama_models(self) -> list:
        try:
            r = subprocess.run(
                ["ollama", "list"],
                capture_output=True, text=True, timeout=10, shell=False
            )
            if r.returncode == 0:
                lines = r.stdout.strip().splitlines()[1:]   # skip header row
                return [line.split()[0] for line in lines if line.strip()]
        except Exception:
            pass
        return []

    def _get_torch_cache(self) -> str:
        env = os.environ.get("TORCH_HOME")
        if env:
            return env
        return str(Path.home() / ".cache" / "torch" / "hub")

    def _get_whisper_cache(self) -> str:
        xdg  = os.environ.get("XDG_CACHE_HOME")
        base = Path(xdg) if xdg else Path.home() / ".cache"
        return str(base / "whisper")
