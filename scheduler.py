"""
Daily scheduler — runs sync.run_sync() once per day at a configured time.
Keep this process running in the background (e.g. as a Windows Task,
or just leave the terminal open).

Usage:
    python scheduler.py              # runs at 08:00 every day (default)
    python scheduler.py --time 22:30 # runs at 22:30 every day
"""

import time
import argparse
from datetime import datetime

from sync import run_sync

DEFAULT_RUN_TIME = "08:00"  # 24-hour HH:MM


def _wait_until(target_time: str):
    """Sleep until the next occurrence of HH:MM."""
    while True:
        now = datetime.now()
        target = datetime.strptime(
            f"{now.strftime('%Y-%m-%d')} {target_time}", "%Y-%m-%d %H:%M"
        )
        if now >= target:
            # Already past today's window — schedule for tomorrow
            target = target.replace(day=target.day + 1)

        seconds_to_wait = (target - now).total_seconds()
        print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Next sync at {target.strftime('%Y-%m-%d %H:%M')} "
              f"({int(seconds_to_wait // 3600)}h {int((seconds_to_wait % 3600) // 60)}m away)"
        )
        time.sleep(seconds_to_wait)
        break  # exit loop to trigger sync


def main():
    parser = argparse.ArgumentParser(description="Fitbit daily sync scheduler")
    parser.add_argument("--time", default=DEFAULT_RUN_TIME,
                        help="Time to run daily sync in HH:MM format (default: 08:00)")
    args = parser.parse_args()

    print(f"Scheduler started. Will sync Fitbit data daily at {args.time}.")
    print("Press Ctrl+C to stop.\n")

    while True:
        _wait_until(args.time)
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Running daily sync...")
        try:
            run_sync()
        except Exception as e:
            print(f"Sync failed: {e}")
        print()


if __name__ == "__main__":
    main()
