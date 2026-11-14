import os
import site
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
site.addsitedir(str(root / ".venv" / "lib" / python_version / "site-packages"))
sys.path.insert(0, str(root))
os.environ["AIRFARE_HTTPS"] = "1"

from app import app as application
