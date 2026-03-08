"""
Supabase (PostgreSQL) database layer for Fitbit activity, heart rate, and sleep data.
Drop-in replacement for database.py — identical public API.
"""

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["SUPABASE_DB_URL"]

ALLOWED_TABLES = {"daily_activity", "daily_heartrate", "daily_sleep"}


@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Verify connectivity and ensure all tables exist."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_activity (
                    date        DATE PRIMARY KEY,
                    steps       INTEGER,
                    distance_km NUMERIC(8, 2),
                    calories    INTEGER,
                    floors      INTEGER,
                    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_heartrate (
                    date                    DATE PRIMARY KEY,
                    resting_hr              INTEGER,
                    out_of_range_minutes    INTEGER,
                    fat_burn_minutes        INTEGER,
                    cardio_minutes          INTEGER,
                    peak_minutes            INTEGER,
                    out_of_range_calories   NUMERIC(10, 2),
                    fat_burn_calories       NUMERIC(10, 2),
                    cardio_calories         NUMERIC(10, 2),
                    peak_calories           NUMERIC(10, 2),
                    fetched_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_sleep (
                    date                    DATE PRIMARY KEY,
                    start_time              TEXT,
                    end_time                TEXT,
                    duration_ms             BIGINT,
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
                    fetched_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sync_log (
                    id          SERIAL PRIMARY KEY,
                    synced_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    data_type   TEXT,
                    days_synced INTEGER,
                    status      TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    id            SERIAL PRIMARY KEY,
                    user_label    TEXT NOT NULL DEFAULT 'primary',
                    access_token  TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    token_type    TEXT,
                    expires_in    INTEGER,
                    scope         TEXT,
                    user_id       TEXT,
                    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS tokens_user_label_uidx
                ON tokens(user_label)
            """)
    print("Connected to Supabase. All tables ready.")


def upsert_daily_activity(records: list[dict]):
    """Insert or update a list of daily activity records."""
    if not records:
        return
    sql = """
        INSERT INTO daily_activity (date, steps, distance_km, calories, floors)
        VALUES (%(date)s, %(steps)s, %(distance_km)s, %(calories)s, %(floors)s)
        ON CONFLICT (date) DO UPDATE SET
            steps       = EXCLUDED.steps,
            distance_km = EXCLUDED.distance_km,
            calories    = EXCLUDED.calories,
            floors      = EXCLUDED.floors,
            fetched_at  = NOW()
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, records, page_size=200)


def upsert_daily_heartrate(records: list[dict]):
    """Insert or update heart rate records."""
    if not records:
        return
    sql = """
        INSERT INTO daily_heartrate (
            date, resting_hr,
            out_of_range_minutes, fat_burn_minutes, cardio_minutes, peak_minutes,
            out_of_range_calories, fat_burn_calories, cardio_calories, peak_calories
        )
        VALUES (
            %(date)s, %(resting_hr)s,
            %(out_of_range_minutes)s, %(fat_burn_minutes)s,
            %(cardio_minutes)s, %(peak_minutes)s,
            %(out_of_range_calories)s, %(fat_burn_calories)s,
            %(cardio_calories)s, %(peak_calories)s
        )
        ON CONFLICT (date) DO UPDATE SET
            resting_hr            = EXCLUDED.resting_hr,
            out_of_range_minutes  = EXCLUDED.out_of_range_minutes,
            fat_burn_minutes      = EXCLUDED.fat_burn_minutes,
            cardio_minutes        = EXCLUDED.cardio_minutes,
            peak_minutes          = EXCLUDED.peak_minutes,
            out_of_range_calories = EXCLUDED.out_of_range_calories,
            fat_burn_calories     = EXCLUDED.fat_burn_calories,
            cardio_calories       = EXCLUDED.cardio_calories,
            peak_calories         = EXCLUDED.peak_calories,
            fetched_at            = NOW()
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, records, page_size=200)


def upsert_daily_sleep(records: list[dict]):
    """Insert or update sleep records."""
    if not records:
        return
    sql = """
        INSERT INTO daily_sleep (
            date, start_time, end_time, duration_ms, time_in_bed,
            minutes_asleep, minutes_awake, minutes_to_fall_asleep,
            efficiency, awakenings_count,
            deep_minutes, light_minutes, rem_minutes, wake_minutes,
            deep_30day_avg, light_30day_avg, rem_30day_avg, wake_30day_avg
        )
        VALUES (
            %(date)s, %(start_time)s, %(end_time)s, %(duration_ms)s, %(time_in_bed)s,
            %(minutes_asleep)s, %(minutes_awake)s, %(minutes_to_fall_asleep)s,
            %(efficiency)s, %(awakenings_count)s,
            %(deep_minutes)s, %(light_minutes)s, %(rem_minutes)s, %(wake_minutes)s,
            %(deep_30day_avg)s, %(light_30day_avg)s, %(rem_30day_avg)s, %(wake_30day_avg)s
        )
        ON CONFLICT (date) DO UPDATE SET
            start_time             = EXCLUDED.start_time,
            end_time               = EXCLUDED.end_time,
            duration_ms            = EXCLUDED.duration_ms,
            time_in_bed            = EXCLUDED.time_in_bed,
            minutes_asleep         = EXCLUDED.minutes_asleep,
            minutes_awake          = EXCLUDED.minutes_awake,
            minutes_to_fall_asleep = EXCLUDED.minutes_to_fall_asleep,
            efficiency             = EXCLUDED.efficiency,
            awakenings_count       = EXCLUDED.awakenings_count,
            deep_minutes           = EXCLUDED.deep_minutes,
            light_minutes          = EXCLUDED.light_minutes,
            rem_minutes            = EXCLUDED.rem_minutes,
            wake_minutes           = EXCLUDED.wake_minutes,
            deep_30day_avg         = EXCLUDED.deep_30day_avg,
            light_30day_avg        = EXCLUDED.light_30day_avg,
            rem_30day_avg          = EXCLUDED.rem_30day_avg,
            wake_30day_avg         = EXCLUDED.wake_30day_avg,
            fetched_at             = NOW()
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, sql, records, page_size=200)


def log_sync(data_type: str, days_synced: int, status: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sync_log (data_type, days_synced, status) VALUES (%s, %s, %s)",
                (data_type, days_synced, status),
            )


def get_latest_stored_date(table: str = "daily_activity") -> str | None:
    """Return the most recent date already stored for a given table."""
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Unknown table: {table}")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT MAX(date) FROM {table}")
            result = cur.fetchone()[0]
            # psycopg2 returns datetime.date for DATE columns — convert to string
            return result.isoformat() if result else None


def get_all_activity() -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM daily_activity ORDER BY date")
            return [dict(r) for r in cur.fetchall()]


def get_activity_range(start_date: str, end_date: str) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM daily_activity WHERE date BETWEEN %s AND %s ORDER BY date",
                (start_date, end_date),
            )
            return [dict(r) for r in cur.fetchall()]
