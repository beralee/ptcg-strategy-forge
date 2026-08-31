"""PTCG Strategy Forge developer toolkit."""

from typing import TYPE_CHECKING, Any

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

__version__ = "0.2.0"

__all__ = [
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
    if name in {"StrategyWorkspace", "WorkspaceError", "WorkspaceMode", "WorkspaceModel"}:
        from . import sdk

        return getattr(sdk, name)
    raise AttributeError(name)
