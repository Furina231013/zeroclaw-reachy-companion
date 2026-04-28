from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuntimeState:
    """Small mutable state shared across companion turns."""

    quiet_mode: bool = False
