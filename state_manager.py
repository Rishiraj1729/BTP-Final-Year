"""
state_manager.py
----------------
Handles loading, saving, and versioning of AgentState.

Versions are stored as JSON files:
    prd_versions/v1.json
    prd_versions/v2.json
    ...

Also writes a human-readable snapshot alongside each version.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from state_schema import AgentState, PRDVersion

VERSION_DIR = Path(__file__).resolve().parent / "prd_versions"


def _ensure_dir() -> None:
    VERSION_DIR.mkdir(parents=True, exist_ok=True)


def save_version(state: AgentState) -> int:
    """
    Persist the current state as a new versioned JSON snapshot.
    Increments state.version before saving.
    Returns the new version number.
    """
    _ensure_dir()

    ts = datetime.now(timezone.utc).isoformat()

    # Record current PRD markdown in history
    if state.prd_markdown:
        snapshot = PRDVersion(
            version=state.version,
            timestamp=ts,
            content_md=state.prd_markdown,
            state_snapshot=state.to_dict(),
        )
        state.history.append(snapshot.__dict__)

    # Write JSON
    version_file = VERSION_DIR / f"v{state.version}.json"
    with open(version_file, "w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, indent=2)

    # Write Markdown alongside
    if state.prd_markdown:
        md_file = VERSION_DIR / f"v{state.version}.md"
        md_file.write_text(state.prd_markdown, encoding="utf-8")

    print(f"[StateManager] Saved version v{state.version} -> {version_file}")
    return state.version


def bump_version(state: AgentState) -> None:
    """Increment the version number in-place."""
    state.version += 1


def load_version(version: int) -> AgentState:
    """Load a specific version from disk."""
    _ensure_dir()
    version_file = VERSION_DIR / f"v{version}.json"
    if not version_file.exists():
        raise FileNotFoundError(f"Version v{version} not found at {version_file}")

    with open(version_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    state = AgentState.from_dict(data)
    print(f"[StateManager] Loaded version v{version} from {version_file}")
    return state


def list_versions() -> List[int]:
    """Return sorted list of all saved version numbers."""
    _ensure_dir()
    versions = []
    for p in VERSION_DIR.glob("v*.json"):
        try:
            n = int(p.stem[1:])
            versions.append(n)
        except ValueError:
            pass
    return sorted(versions)


def latest_version() -> Optional[int]:
    """Return the highest saved version number, or None if no versions exist."""
    vs = list_versions()
    return vs[-1] if vs else None


def load_latest() -> Optional[AgentState]:
    """Load the latest saved state, or None if nothing has been saved yet."""
    v = latest_version()
    if v is None:
        return None
    return load_version(v)

