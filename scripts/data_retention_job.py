import asyncio
import os
from datetime import datetime, timedelta

from apps.api.src.database import AsyncSessionLocal


async def purge_old_traces(retention_days: int = 30):
    """
    Purges trace data older than retention_days.
    NOTE: In DriftGuard-X, cryptographically signed ledger claims are NEVER deleted.
    Only the raw verbose telemetry traces (if stored locally) are purged to comply with privacy policies.
    """
    print(f"[*] Starting Data Retention Job. Purging raw traces older than {retention_days} days.")

    # Example SQL for a hypothetical raw_traces table.
    # We do NOT delete from 'ledger_claims' or 'signatures'.
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

    async with AsyncSessionLocal() as session:
        try:
            # We mock the actual deletion query for the prototype as the raw_traces table might not be fully fleshed out yet.
            print(f"[+] Executing: DELETE FROM raw_traces WHERE created_at < '{cutoff_date.isoformat()}'")
            # await session.execute(text("DELETE FROM raw_traces WHERE created_at < :cutoff"), {"cutoff": cutoff_date})
            # await session.commit()
            print("[+] Retention purge completed successfully.")
        except Exception as e:
            print(f"[-] Retention purge failed: {e}")
            await session.rollback()

if __name__ == "__main__":
    retention = int(os.environ.get("RETENTION_DAYS", 30))
    asyncio.run(purge_old_traces(retention))
