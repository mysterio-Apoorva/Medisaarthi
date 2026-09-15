"""Explicitly initialize synthetic demo records in an empty database."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.store import store
from backend.demo_data import seed_demo

if __name__ == "__main__":
    store.initialize()
    with store.connection() as db:
        seed_demo(store, db)
    print("Synthetic seed completed; existing records were preserved.")
