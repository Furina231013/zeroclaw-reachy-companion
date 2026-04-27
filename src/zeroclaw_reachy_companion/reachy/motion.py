from __future__ import annotations


def validate_head_pose(yaw: float, pitch: float, roll: float, duration: float) -> None:
    """Validate a compact head-pose command for Reachy Mini."""
    for name, value in {"yaw": yaw, "pitch": pitch, "roll": roll}.items():
        if not -60.0 <= float(value) <= 60.0:
            raise ValueError(f"{name} must be between -60 and 60 degrees")
    if not 0.1 <= float(duration) <= 10.0:
        raise ValueError("duration must be between 0.1 and 10.0 seconds")


def direction_to_pose(direction: str) -> tuple[float, float, float]:
    """Map common natural-language directions to yaw/pitch/roll degrees."""
    directions = {
        "left": (18.0, 0.0, 0.0),
        "right": (-18.0, 0.0, 0.0),
        "up": (0.0, -12.0, 0.0),
        "down": (0.0, 12.0, 0.0),
        "front": (0.0, 0.0, 0.0),
    }
    return directions.get(direction, directions["front"])

