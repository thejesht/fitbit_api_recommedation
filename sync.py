"""
Sync engine — backfills full history on first run,
then fetches only new days on subsequent runs.
Handles: activity, heart rate, sleep.
"""

import time
import warnings
warnings.filterwarnings("ignore")

from datetime import date, timedelta

from fitbit.client import FitbitClient
from fitbit.supabase_db import (
    init_db,
    upsert_daily_activity,
    upsert_daily_heartrate,
    upsert_daily_sleep,
    log_sync,
    get_latest_stored_date,
)

# API max windows per request
ACTIVITY_CHUNK = 365   # activity timeseries: up to 1 year
HR_CHUNK       = 30    # heart rate: kept small to avoid Fitbit 500 errors
SLEEP_CHUNK    = 100   # sleep range endpoint: up to 100 days


def _date_chunks(start: date, end: date, chunk: int):
    """Yield (start, end) date pairs in windows of `chunk` days."""
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=chunk - 1), end)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def _earliest_date(client: FitbitClient) -> date:
    """Ask the API for the first day of recorded step data."""
    data = client._get("/activities/steps/date/today/max.json")
    earliest_str = data["activities-steps"][0]["dateTime"]
    return date.fromisoformat(earliest_str)


# ── Per-type sync functions ────────────────────────────────────────────────────

def _sync_activity(client: FitbitClient, start: date, today: date) -> int:
    total = 0
    for s, e in _date_chunks(start, today, ACTIVITY_CHUNK):
        print(f"  [activity]    {s} to {e} ...", end=" ", flush=True)
        s_str, e_str = s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")

        steps    = {r["date"]: r["value"] for r in client.get_activity_timeseries("steps",    s_str, e_str)}
        distance = {r["date"]: r["value"] for r in client.get_activity_timeseries("distance", s_str, e_str)}
        calories = {r["date"]: r["value"] for r in client.get_activity_timeseries("calories", s_str, e_str)}
        floors   = {r["date"]: r["value"] for r in client.get_activity_timeseries("floors",   s_str, e_str)}

        all_dates = sorted(set(steps) | set(distance) | set(calories) | set(floors))
        records = [
            {
                "date":        d,
                "steps":       int(steps.get(d, 0)),
                "distance_km": round(float(distance.get(d, 0)), 2),
                "calories":    int(calories.get(d, 0)),
                "floors":      int(floors.get(d, 0)),
            }
            for d in all_dates
        ]
        upsert_daily_activity(records)
        total += len(records)
        print(f"{len(records)} days saved.")
    return total


def _sync_heartrate(client: FitbitClient, start: date, today: date) -> int:
    total = 0
    for s, e in _date_chunks(start, today, HR_CHUNK):
        print(f"  [heart rate]  {s} to {e} ...", end=" ", flush=True)
        for attempt in range(3):
            try:
                records = client.get_heartrate_timeseries(
                    s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")
                )
                break
            except Exception as exc:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    print(f"SKIPPED (error: {exc})")
                    records = []
        upsert_daily_heartrate(records)
        total += len(records)
        print(f"{len(records)} days saved.")
    return total


def _sync_sleep(client: FitbitClient, start: date, today: date) -> int:
    total = 0
    for s, e in _date_chunks(start, today, SLEEP_CHUNK):
        print(f"  [sleep]       {s} to {e} ...", end=" ", flush=True)
        records = client.get_sleep_range(
            s.strftime("%Y-%m-%d"), e.strftime("%Y-%m-%d")
        )
        upsert_daily_sleep(records)
        total += len(records)
        print(f"{len(records)} nights saved.")
    return total


# ── Main entry ─────────────────────────────────────────────────────────────────

def run_sync():
    init_db()
    client  = FitbitClient()
    today   = date.today()

    print("\n========================================")
    print(" Fitbit Sync")
    print("========================================\n")

    for data_type, table, sync_fn in [
        ("activity",   "daily_activity",   _sync_activity),
        ("heart_rate", "daily_heartrate",  _sync_heartrate),
        ("sleep",      "daily_sleep",      _sync_sleep),
    ]:
        latest = get_latest_stored_date(table)

        if latest is None:
            start = _earliest_date(client)
            mode  = "backfill"
        else:
            start = date.fromisoformat(latest) + timedelta(days=1)
            mode  = "incremental"

        if start > today:
            print(f"[{data_type}] Already up to date.")
            log_sync(data_type, 0, "up_to_date")
            continue

        print(f"[{data_type}] mode={mode}  from={start} to={today}")
        count = sync_fn(client, start, today)
        log_sync(data_type, count, "success")
        print(f"[{data_type}] Done. {count} records stored.\n")

    print("All syncs complete.")


if __name__ == "__main__":
    run_sync()
