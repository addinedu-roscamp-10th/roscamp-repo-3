from pathlib import Path
import sys

UI_DIR = Path(__file__).resolve().parents[2]
BASE_DIR = UI_DIR
PROJECT_ROOT = UI_DIR.parent
STYLE_PATH = UI_DIR / "utils" / "styles" / "main.qss"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
