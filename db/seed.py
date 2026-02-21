"""Seed the database — convenience wrapper.

Delegates to db/seeds/clean.py (users only, no projects).
For other scenarios, run seed scripts directly:
  docker compose exec api .venv/bin/python db/seeds/clean.py
  docker compose exec api .venv/bin/python db/seeds/with_project.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "seeds"))

from clean import seed  # noqa: E402

if __name__ == "__main__":
    asyncio.run(seed())
