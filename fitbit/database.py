"""
SQLite database layer for Fitbit activity, heart rate, and sleep data.
"""

import sqlite3
from contextlib import contextmanager

DB_FILE = "fitbit_data.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_activity (
                date        TEXT PRIMARY KEY,
                steps       INTEGER,
                distance_km REAL,
                calories    INTEGER,
                floors      INTEGER,
                fetched_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_heartrate (
                date                  TEXT PRIMARY KEY,
                resting_hr            INTEGER,
                out_of_range_minutes  INTEGER,
                fat_burn_minutes      INTEGER,
                cardio_minutes        INTEGER,
                peak_minutes          INTEGER,
                out_of_range_calories REAL,
                fat_burn_calories     REAL,
                cardio_calories       REAL,
                peak_calories         REAL,
                fetched_at            TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_sleep (
                date                    TEXT PRIMARY KEY,
                start_time              TEXT,
                end_time                TEXT,
                duration_ms             INTEGER,
                time_in_bed             INTEGER,
                minutes_asleep          INTEGER,
                minutes_awake           INTEGER,
                minutes_to_fall_asleep  INTEGER,
                efficiency              INTEGER,
                awakenings_count        INTEGER,
                deep_minutes            INTEGER,
                light_minutes           INTEGER,
                rem_minutes             INTEGER,
                wake_minutes            INTEGER,
                deep_30day_avg          INTEGER,
                light_30day_avg         INTEGER,
                rem_30day_avg           INTEGER,
                wake_30day_avg          INTEGER,
                fetched_at              TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                synced_at   TEXT DEFAULT (datetime('now')),
                data_type   TEXT,
                days_synced INTEGER,
                status      TEXT
            )
        """)
    print(f"Database ready: {DB_FILE}")


def upsert_daily_activity(records: list[dict]):
    """Insert or update a list of daily activity records."""
    with get_conn() as conn:
        conn.executemany("""
            INSERT INTO daily_activity (date, steps, distance_km, calories, floors)
            VALUES (:date, :steps, :distance_km, :calories, :floors)
            ON CONFLICT(date) DO UPDATE SET
                steps       = excluded.steps,
                distance_km = excluded.distance_km,
                calories    = excluded.calories,
                floors      = excluded.floors,
                fetched_at  = datetime('now')
        """, records)


def upsert_daily_heartrate(records: list[dict]):
    """Insert or update heart rate records."""
    with get_conn() as conn:
        conn.executemany("""
            INSERT INTO daily_heartrate (
                date, resting_hr,
                out_of_range_minutes, fat_burn_minutes, cardio_minutes, peak_minutes,
                out_of_range_calories, fat_burn_calories, cardio_calories, peak_calories
            )
            VALUES (
                :date, :resting_hr,
                :out_of_range_minutes, :fat_burn_minutes, :cardio_minutes, :peak_minutes,
                :out_of_range_calories, :fat_burn_calories, :cardio_calories, :peak_calories
            )
            ON CONFLICT(date) DO UPDATE SET
                resting_hr            = excluded.resting_hr,
                out_of_range_minutes  = excluded.out_of_range_minutes,
                fat_burn_minutes      = excluded.fat_burn_minutes,
                cardio_minutes        = excluded.cardio_minutes,
                peak_minutes          = excluded.peak_minutes,
                out_of_range_calories = excluded.out_of_range_calories,
                fat_burn_calories     = excluded.fat_burn_calories,
                cardio_calories       = excluded.cardio_calories,
                peak_calories         = excluded.peak_calories,
                fetched_at            = datetime('now')
        """, records)


def upsert_daily_sleep(records: list[dict]):
    """Insert or update sleep records."""
    with get_conn() as conn:
        conn.executemany("""
            INSERT INTO daily_sleep (
                date, start_time, end_time, duration_ms, time_in_bed,
                minutes_asleep, minutes_awake, minutes_to_fall_asleep,
                efficiency, awakenings_count,
                deep_minutes, light_minutes, rem_minutes, wake_minutes,
                deep_30day_avg, light_30day_avg, rem_30day_avg, wake_30day_avg
            )
            VALUES (
                :date, :start_time, :end_time, :duration_ms, :time_in_bed,
                :minutes_asleep, :minutes_awake, :minutes_to_fall_asleep,
                :efficiency, :awakenings_count,
                :deep_minutes, :light_minutes, :rem_minutes, :wake_minutes,
                :deep_30day_avg, :light_30day_avg, :rem_30day_avg, :wake_30day_avg
            )
            ON CONFLICT(date) DO UPDATE SET
                start_time             = excluded.start_time,
                end_time               = excluded.end_time,
                duration_ms            = excluded.duration_ms,
                time_in_bed            = excluded.time_in_bed,
                minutes_asleep         = excluded.minutes_asleep,
                minutes_awake          = excluded.minutes_awake,
                minutes_to_fall_asleep = excluded.minutes_to_fall_asleep,
                efficiency             = excluded.efficiency,
                awakenings_count       = excluded.awakenings_count,
                deep_minutes           = excluded.deep_minutes,
                light_minutes          = excluded.light_minutes,
                rem_minutes            = excluded.rem_minutes,
                wake_minutes           = excluded.wake_minutes,
                deep_30day_avg         = excluded.deep_30day_avg,
                light_30day_avg        = excluded.light_30day_avg,
                rem_30day_avg          = excluded.rem_30day_avg,
                wake_30day_avg         = excluded.wake_30day_avg,
                fetched_at             = datetime('now')
        """, records)


def log_sync(data_type: str, days_synced: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sync_log (data_type, days_synced, status) VALUES (?, ?, ?)",
            (data_type, days_synced, status)
        )


def get_latest_stored_date(table: str = "daily_activity") -> str | None:
    """Return the most recent date already stored for a given table."""
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT MAX(date) as latest FROM {table}"
        ).fetchone()
        return row["latest"]


def get_all_activity() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_activity ORDER BY date"
        ).fetchall()
        return [dict(r) for r in rows]


def get_activity_range(start_date: str, end_date: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_activity WHERE date BETWEEN ? AND ? ORDER BY date",
            (start_date, end_date)
        ).fetchall()
        return [dict(r) for r in rows]
