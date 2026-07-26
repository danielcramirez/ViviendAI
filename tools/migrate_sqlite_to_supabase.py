from __future__ import annotations

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from lead_service import _connection, init_db  # noqa: E402
from supabase_service import is_configured, upsert_lead  # noqa: E402


def main() -> int:
    init_db()
    if not is_configured():
        print(
            "Supabase no está configurado. Revisa SUPABASE_URL y "
            "SUPABASE_SECRET_KEY en .env."
        )
        return 2

    with _connection() as connection:
        rows = connection.execute(
            "SELECT * FROM META_LEADS_CAPTURE ORDER BY id"
        ).fetchall()

    migrated = 0
    for row in rows:
        lead = dict(row)
        try:
            upsert_lead(lead)
        except RuntimeError as error:
            print(f"ERROR {lead.get('lead_code')}: {error}")
            return 1
        migrated += 1
        print(f"OK {lead.get('lead_code')}")

    print(f"Migración terminada: {migrated} leads enviados a Supabase.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
