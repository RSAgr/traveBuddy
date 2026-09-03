from pathlib import Path
import sys
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
# Scripts run outside FastAPI, so explicitly load the backend configuration.
load_dotenv(BACKEND_DIR / ".env")
from store.db import DATABASE

def main():
    migration_dir = BACKEND_DIR / "migrations"
    try:
        with DATABASE.connection() as conn, conn.cursor() as cur:
            for migration in sorted(migration_dir.glob("*.sql")):
                cur.execute(migration.read_text(encoding="utf-8"))
            conn.commit()
        print("PostgreSQL schema is ready.")
    finally:
        DATABASE.close()

if __name__ == "__main__":
    main()
