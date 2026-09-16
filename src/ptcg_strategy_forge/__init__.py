"""PTCG Strategy Forge developer toolkit."""

from typing import TYPE_CHECKING, Any
from pathlib import Path
from .resources import resource_root
import sys

# The pinned vendor snapshot retains its reviewed module layout.
_resource_root = resource_root()
if str(_resource_root) not in sys.path:
    sys.path.insert(0, str(_resource_root))

from .ucis_runtime import (
    PublicBattleFacts,
    SelectionWindow,
    SemanticOptionKey,
    UcisRuntimeError,
    option,
    semantic_key,
)
if TYPE_CHECKING:
    from .sdk import StrategyWorkspace, WorkspaceError, WorkspaceMode, WorkspaceModel

__version__ = "0.3.0"

__all__ = [
    "AccountStore",
    "ControlClient",
    "PublicBattleFacts",
    "SelectionWindow",
    "SemanticOptionKey",
    "StrategyWorkspace",
    "UcisRuntimeError",
    "WorkspaceError",
    "WorkspaceMode",
    "WorkspaceModel",
    "option",
    "semantic_key",
]


def __getattr__(name: str) -> Any:
    if name in {"AccountStore", "ControlClient"}:
        from . import control_client
        return getattr(control_client, name)
    if name in {"StrategyWorkspace", "WorkspaceError", "WorkspaceMode", "WorkspaceModel"}:
        from . import sdk

        return getattr(sdk, name)
    raise AttributeError(name)
