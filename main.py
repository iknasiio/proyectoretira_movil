import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.main import RamaMobileApp


if __name__ == "__main__":
    RamaMobileApp().run()
