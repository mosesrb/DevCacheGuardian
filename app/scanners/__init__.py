from .pip_scanner             import PipScanner
from .uv_scanner              import UvScanner
from .npm_scanner             import NpmScanner
from .huggingface_scanner     import HuggingFaceScanner
from .ai_extended_scanner     import AIExtendedScanner
from .duplicate_model_scanner import DuplicateModelScanner
from .dev_ecosystem_scanner   import DevEcosystemScanner
from .docker_scanner          import DockerScanner
from .temp_scanner            import TempScanner
from .venv_scanner            import VenvScanner

ALL_SCANNERS = [
    PipScanner,
    UvScanner,
    NpmScanner,
    HuggingFaceScanner,
    AIExtendedScanner,
    DuplicateModelScanner,
    DevEcosystemScanner,
    DockerScanner,
    TempScanner,
    VenvScanner,
]

__all__ = [
    "ALL_SCANNERS",
    "PipScanner", "UvScanner", "NpmScanner",
    "HuggingFaceScanner", "AIExtendedScanner", "DuplicateModelScanner",
    "DevEcosystemScanner", "DockerScanner", "TempScanner", "VenvScanner",
]
