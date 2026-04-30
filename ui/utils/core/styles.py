from pathlib import Path

from ui.utils.core.paths import STYLE_PATH


STYLE_ASSET_PLACEHOLDER = "__STYLE_ASSET_DIR__"


def load_stylesheet(style_path: Path = STYLE_PATH) -> str:
    try:
        stylesheet = style_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""

    asset_dir = (style_path.parent / "assets").resolve().as_posix()
    return stylesheet.replace(STYLE_ASSET_PLACEHOLDER, asset_dir)
