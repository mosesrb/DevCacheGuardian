"""
eco_colors.py

Shared categorical colors for ecosystem tags (Python, Node.js, Docker, ...).
These are *categorical*, not accent colors — they identify a category at a
glance and stay the same across every accent palette, the same way a
legend's colors don't change when you re-skin an app.

Previously this map was duplicated independently in cache_table_widget.py,
dashboard_widget.py and timeline_widget.py with drifting values; this is
the single source all three now import.
"""

ECO_COLORS = {
    "Python":        "#7396b8",
    "Node.js":       "#6fa888",
    "AI/ML":         "#a98bc4",
    "Docker":        "#5b9bb0",
    "System":        "#8a93a0",
    "Build Systems": "#b8916f",
}

DEFAULT_ECO_COLOR = "#8a93a0"


def eco_color(ecosystem: str) -> str:
    return ECO_COLORS.get(ecosystem, DEFAULT_ECO_COLOR)
