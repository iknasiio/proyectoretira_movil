from pathlib import Path

from kivy.lang import Builder


KV_DIR = Path(__file__).resolve().parents[1] / "kv"
KV_FILES = (
    "components.kv",
    "root.kv",
    "login.kv",
    "recovery.kv",
    "citizen.kv",
    "admin.kv",
    "dashboard.kv",
    "worker.kv",
)


def load_kv_files() -> None:
    for filename in KV_FILES:
        Builder.load_file(str(KV_DIR / filename))
