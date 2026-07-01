"""
icons.py

Thin wrapper around qtawesome so every file constructs icons the same way,
with sentence-case names mapped to a single consistent icon family
(Font Awesome 5 Solid / Brands), rather than emoji or ad-hoc glyphs.
"""
from __future__ import annotations

import qtawesome as qta

from app.ui.palettes import NEUTRAL
from app.ui.theme import theme_manager


def icon(name: str, color: str | None = None, color_key: str | None = None):
    """Build a QIcon. Pass an explicit `color` hex, or a `color_key` to pull
    from the active palette (e.g. "accent", "text_secondary", "danger").
    Defaults to the neutral secondary text color."""
    if color is None:
        if color_key:
            color = theme_manager.current_palette().get(color_key, NEUTRAL["text_secondary"])
        else:
            color = NEUTRAL["text_secondary"]
    return qta.icon(name, color=color)


def accent_icon(name: str) -> "object":
    """Icon tinted with the current accent color. Re-call after a palette
    change to get a fresh icon — QIcon does not update itself live."""
    return icon(name, color_key="accent")


def on_accent_icon(name: str) -> "object":
    """Icon meant to sit on a filled accent-colored button."""
    return icon(name, color_key="on_accent")
