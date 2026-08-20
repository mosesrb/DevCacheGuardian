import importlib
import pkgutil
from typing import List, Type

from .base_scanner import BaseScanner
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

# Dynamically import all scanner modules in this package
for _, module_name, _ in pkgutil.iter_modules(__path__):
    if module_name != "base_scanner":
        try:
            importlib.import_module(f"{__name__}.{module_name}")
        except Exception:
            pass

# Auto-discover all subclasses of BaseScanner while preserving deterministic order
_discovered: List[Type[BaseScanner]] = []
_seen = set()

_preferred_order = [
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

for sc in _preferred_order:
    if issubclass(sc, BaseScanner) and sc not in _seen:
        _discovered.append(sc)
        _seen.add(sc)

for sc in BaseScanner.__subclasses__():
    if sc not in _seen:
        _discovered.append(sc)
        _seen.add(sc)

ALL_SCANNERS: List[Type[BaseScanner]] = _discovered

__all__ = [
    "ALL_SCANNERS",
    "BaseScanner",
    "PipScanner", "UvScanner", "NpmScanner",
    "HuggingFaceScanner", "AIExtendedScanner", "DuplicateModelScanner",
    "DevEcosystemScanner", "DockerScanner", "TempScanner", "VenvScanner",
]
