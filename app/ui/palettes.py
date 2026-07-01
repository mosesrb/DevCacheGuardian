"""
palettes.py

Color tokens for the Slate & Rust UI system.

Design principle: layout and typography never change. Only the *accent*
tokens differ between palettes — neutrals (backgrounds, borders, body
text) and semantics (success/warning/danger) are shared by every
palette so the app always reads as the same tool, just re-tinted.
"""
from __future__ import annotations

# ── Shared neutrals (never change between palettes) ───────────────────────
NEUTRAL = {
    "bg_page":        "#14171b",
    "bg_sidebar":     "#0f1216",
    "bg_card":        "#191d22",
    "bg_card_alt":    "#15181d",
    "bg_hover":       "#1e2329",
    "bg_input":       "#181c21",
    "border":         "#1c2025",
    "border_strong":  "#262b31",
    "border_stronger":"#333a42",
    "text_primary":   "#e9ecef",
    "text_secondary": "#aab2bc",
    "text_muted":     "#7d8794",
    "text_faint":     "#5a6470",
    "text_disabled":  "#3d434b",
}

# ── Shared semantics (status meaning, independent of accent) ──────────────
SEMANTIC = {
    "success":     "#5fae74",
    "success_bg":  "#16241c",
    "success_border": "#1f3a28",
    "success_solid": "#2f6b46",
    "warning":     "#c9a227",
    "warning_bg":  "#2a230f",
    "warning_border": "#3d3315",
    "warning_solid": "#7a5e1c",
    "danger":      "#c1564b",
    "danger_bg":   "#271513",
    "danger_border": "#3d211d",
    "danger_solid": "#7a352f",
    "neutral_solid": "#2a2f36",
}

# ── Fonts (bundled, shared by every palette) ───────────────────────────────
FONT_SANS = "'IBM Plex Sans', 'Segoe UI', 'Helvetica Neue', sans-serif"
FONT_MONO = "'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace"

# ── Accent palettes — this is the only thing the user switches ────────────
ACCENTS = {
    "rust": {
        "label":        "Rust",
        "accent":       "#c1652f",
        "accent_hover": "#d9763c",
        "accent_pressed": "#a8551f",
        "accent_text":  "#e3936a",
        "on_accent":    "#1a0f08",
    },
    "verdigris": {
        "label":        "Verdigris",
        "accent":       "#4f9e8c",
        "accent_hover": "#62b29f",
        "accent_pressed": "#3f8273",
        "accent_text":  "#7fc4b3",
        "on_accent":    "#08231d",
    },
    "violet": {
        "label":        "Violet",
        "accent":       "#8b6fae",
        "accent_hover": "#9c83bb",
        "accent_pressed": "#74599a",
        "accent_text":  "#b39bd0",
        "on_accent":    "#1c1426",
    },
    "phosphor": {
        "label":        "Phosphor",
        "accent":       "#52b878",
        "accent_hover": "#67c98a",
        "accent_pressed": "#439c64",
        "accent_text":  "#8fe0a8",
        "on_accent":    "#08210f",
    },
    "amber": {
        "label":        "Amber",
        "accent":       "#d99a3d",
        "accent_hover": "#e0a440",
        "accent_pressed": "#c0852e",
        "accent_text":  "#f0c068",
        "on_accent":    "#2b1c08",
    },
}

# ── Health-score grade scale (fixed, semantic — not accent-dependent) ─────
GRADE_COLORS = {
    "A": "#5fae74",
    "B": "#8fbf7a",
    "C": "#c9a227",
    "D": "#c98a3a",
    "F": "#c1564b",
}

PALETTE_ORDER = ["rust", "verdigris", "violet", "phosphor", "amber"]
DEFAULT_PALETTE = "rust"


def get_palette(key: str) -> dict:
    """Return the full flat token dict (neutral + semantic + accent + fonts)
    for a given palette key, falling back to the default if unknown."""
    accent = ACCENTS.get(key, ACCENTS[DEFAULT_PALETTE])
    tokens = {}
    tokens.update(NEUTRAL)
    tokens.update(SEMANTIC)
    tokens.update(accent)
    tokens["font_sans"] = FONT_SANS
    tokens["font_mono"] = FONT_MONO
    tokens["key"] = key if key in ACCENTS else DEFAULT_PALETTE
    return tokens
