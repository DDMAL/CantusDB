from typing import Optional


def int_param(value: Optional[str]) -> Optional[int]:
    """`value` as an integer, or None if it isn't one, so an edited URL (e.g.
    `?genre=abc` or `?month=²`) is ignored instead of causing an error (#1484)."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
