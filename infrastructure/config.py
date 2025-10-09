import json
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(__file__).parent.parent
CONFIG_FILE = CONFIG_DIR / "config.json"


class ConfigManager:
    @classmethod
    def load_root_path(cls) -> Optional[Path]:
        """Load root_path from config file if exists."""
        CONFIG_DIR.mkdir(exist_ok=True)
        if not CONFIG_FILE.exists():
            return None
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                root_str = data.get("root_path")
                if root_str:
                    return Path(root_str)
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    @classmethod
    def save_root_path(cls, root_path: Path):
        """Save root_path to config file."""
        CONFIG_DIR.mkdir(exist_ok=True)
        data = {"root_path": str(root_path)}
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
