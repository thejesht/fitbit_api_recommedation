"""Quick check: latest data dates in Supabase."""

from fitbit.supabase_db import get_conn

TABLES = ["daily_activity", "daily_heartrate", "daily_sleep", "sync_log"]

with get_conn() as conn:
    cur = conn.cursor()
    for table in TABLES:
        try:
            if table == "sync_log":
                cur.execute("SELECT MAX(synced_at), status FROM sync_log GROUP BY status ORDER BY MAX(synced_at) DESC LIMIT 3")
                rows = cur.fetchall()
                print(f"\n{'sync_log':-<40}")
                for ts, status in rows:
                    print(f"  {status:<12} last at {ts}")
            else:
                cur.execute(f"SELECT MAX(date), MIN(date), COUNT(*) FROM {table}")
                mx, mn, cnt = cur.fetchone()
                print(f"\n{table:-<40}")
                print(f"  rows: {cnt}  |  from: {mn}  |  to: {mx}")
        except Exception as e:
            print(f"\n{table:-<40}")
            print(f"  error: {e}")
            conn.rollback()
