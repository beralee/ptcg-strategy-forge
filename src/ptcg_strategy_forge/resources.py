"""Resolve the reviewed snapshot from a source checkout or an installed wheel."""
from pathlib import Path


def resource_root() -> Path:
    bundle = Path(__file__).resolve().parent / "_bundle"
    return bundle if bundle.is_dir() else Path(__file__).resolve().parents[2]
