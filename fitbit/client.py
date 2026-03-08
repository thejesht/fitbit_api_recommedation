"""
Fitbit API Client
Fetches activity, heart rate, and sleep data.
"""

import json
from datetime import date, timedelta

import requests

from fitbit.auth import get_valid_access_token, load_tokens, refresh_access_token

BASE_URL    = "https://api.fitbit.com/1/user/-"
BASE_URL_12 = "https://api.fitbit.com/1.2/user/-"


class FitbitClient:
    def __init__(self):
        self._access_token = get_valid_access_token()

    # ── Internal request helper ────────────────────────────────────────────────

    def _get(self, endpoint: str, base: str = BASE_URL) -> dict:
        """Make an authenticated GET request, auto-refreshing on 401."""
        url = f"{base}{endpoint}"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        response = requests.get(url, headers=headers)

        if response.status_code == 401:
            print("Access token expired — refreshing...")
            tokens = load_tokens()
            new_tokens = refresh_access_token(tokens["refresh_token"])
            self._access_token = new_tokens["access_token"]
            headers["Authorization"] = f"Bearer {self._access_token}"
            response = requests.get(url, headers=headers)

        response.raise_for_status()
        return response.json()

    def _get_v12(self, endpoint: str) -> dict:
        """Shorthand for v1.2 API calls (used by sleep)."""
        return self._get(endpoint, base=BASE_URL_12)

    # ── Activity ───────────────────────────────────────────────────────────────

    def get_daily_activity_summary(self, activity_date: str = "today") -> dict:
        """
        Get a full activity summary for a given date.

        Args:
            activity_date: 'today', 'yesterday', or 'YYYY-MM-DD'

        Returns:
            dict with keys: steps, distance_km, calories, floors
        """
        if activity_date == "today":
            activity_date = date.today().strftime("%Y-%m-%d")
        elif activity_date == "yesterday":
            activity_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

        data = self._get(f"/activities/date/{activity_date}.json")
        summary = data.get("summary", {})

        return {
            "date": activity_date,
            "steps": summary.get("steps", 0),
            "distance_km": round(
                sum(d["distance"] for d in summary.get("distances", [])
                    if d["activity"] == "total"), 2
            ),
            "calories": summary.get("caloriesOut", 0),
            "floors": summary.get("floors", 0),
        }

    def get_activity_timeseries(
        self,
        resource: str,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """
        Get daily values for one activity metric over a date range.

        Args:
            resource:   'steps' | 'distance' | 'calories' | 'floors'
            start_date: 'YYYY-MM-DD'
            end_date:   'YYYY-MM-DD'

        Returns:
            List of {date, value} dicts ordered by date.
        """
        _resource_map = {
            "steps":    "activities/steps",
            "distance": "activities/distance",
            "calories": "activities/calories",
            "floors":   "activities/floors",
        }
        if resource not in _resource_map:
            raise ValueError(f"resource must be one of {list(_resource_map)}")

        endpoint = f"/{_resource_map[resource]}/date/{start_date}/{end_date}.json"
        data = self._get(endpoint)
        key = list(data.keys())[0]
        return [{"date": entry["dateTime"], "value": float(entry["value"])}
                for entry in data[key]]

    def get_intraday(
        self,
        resource: str,
        activity_date: str = "today",
        detail_level: str = "15min",
    ) -> list[dict]:
        """
        Get intraday (within-day) data at 1min or 15min granularity.
        Requires a Personal app registered on dev.fitbit.com.

        Args:
            resource:      'steps' | 'distance' | 'calories' | 'floors'
            activity_date: 'today', 'yesterday', or 'YYYY-MM-DD'
            detail_level:  '1min' or '15min'

        Returns:
            List of {time, value} dicts for the day.
        """
        _resource_map = {
            "steps":    "activities/steps",
            "distance": "activities/distance",
            "calories": "activities/calories",
            "floors":   "activities/floors",
        }
        if resource not in _resource_map:
            raise ValueError(f"resource must be one of {list(_resource_map)}")

        if activity_date == "today":
            activity_date = date.today().strftime("%Y-%m-%d")
        elif activity_date == "yesterday":
            activity_date = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

        endpoint = f"/{_resource_map[resource]}/date/{activity_date}/1d/{detail_level}.json"
        data = self._get(endpoint)
        intraday_key = f"activities-{resource}-intraday"
        dataset = data.get(intraday_key, {}).get("dataset", [])
        return [{"time": entry["time"], "value": entry["value"]} for entry in dataset]

    def get_last_n_days(self, days: int = 7) -> list[dict]:
        """
        Get full daily summaries for the last N days.

        Returns:
            List of daily summary dicts, oldest first.
        """
        today = date.today()
        return [
            self.get_daily_activity_summary(
                (today - timedelta(days=i)).strftime("%Y-%m-%d")
            )
            for i in range(days - 1, -1, -1)
        ]

    # ── Heart rate ─────────────────────────────────────────────────────────────

    def get_heartrate_timeseries(self, start_date: str, end_date: str) -> list[dict]:
        """
        Get daily resting heart rate and HR zone minutes/calories for a date range.
        Max range per call: 1 year (365 days).

        Returns:
            List of dicts with resting_hr and all four zone breakdowns.
        """
        data = self._get(f"/activities/heart/date/{start_date}/{end_date}.json")
        records = []
        for entry in data.get("activities-heart", []):
            val = entry.get("value", {})
            zones = {z["name"]: z for z in val.get("heartRateZones", [])}

            def _z(name, field, default=0):
                return zones.get(name, {}).get(field, default)

            records.append({
                "date":                   entry["dateTime"],
                "resting_hr":             val.get("restingHeartRate"),
                "out_of_range_minutes":   int(_z("Out of Range", "minutes")),
                "fat_burn_minutes":       int(_z("Fat Burn",     "minutes")),
                "cardio_minutes":         int(_z("Cardio",       "minutes")),
                "peak_minutes":           int(_z("Peak",         "minutes")),
                "out_of_range_calories":  round(_z("Out of Range", "caloriesOut", 0.0), 2),
                "fat_burn_calories":      round(_z("Fat Burn",     "caloriesOut", 0.0), 2),
                "cardio_calories":        round(_z("Cardio",       "caloriesOut", 0.0), 2),
                "peak_calories":          round(_z("Peak",         "caloriesOut", 0.0), 2),
            })
        return records

    # ── Sleep ──────────────────────────────────────────────────────────────────

    def get_sleep_range(self, start_date: str, end_date: str) -> list[dict]:
        """
        Get nightly sleep summaries including stages for a date range.
        Uses the v1.2 API. Max range per call: 100 days.

        Returns:
            List of dicts with duration, efficiency, stage minutes, and 30-day averages.
        """
        data = self._get_v12(f"/sleep/date/{start_date}/{end_date}.json")
        records = []
        seen_dates = set()

        for entry in data.get("sleep", []):
            if not entry.get("isMainSleep", False):
                continue

            sleep_date = entry.get("dateOfSleep")
            if sleep_date in seen_dates:
                continue
            seen_dates.add(sleep_date)

            levels  = entry.get("levels", {})
            summary = levels.get("summary", {})

            def _stage(name, field, default=0):
                return summary.get(name, {}).get(field, default)

            records.append({
                "date":                   sleep_date,
                "start_time":             entry.get("startTime"),
                "end_time":               entry.get("endTime"),
                "duration_ms":            entry.get("duration", 0),
                "time_in_bed":            entry.get("timeInBed", 0),
                "minutes_asleep":         entry.get("minutesAsleep", 0),
                "minutes_awake":          entry.get("minutesAwake", 0),
                "minutes_to_fall_asleep": entry.get("minutesToFallAsleep", 0),
                "efficiency":             entry.get("efficiency", 0),
                "awakenings_count":       entry.get("awakeningsCount", 0),
                "deep_minutes":           int(_stage("deep",  "minutes")),
                "light_minutes":          int(_stage("light", "minutes")),
                "rem_minutes":            int(_stage("rem",   "minutes")),
                "wake_minutes":           int(_stage("wake",  "minutes")),
                "deep_30day_avg":         int(_stage("deep",  "thirtyDayAvgMinutes")),
                "light_30day_avg":        int(_stage("light", "thirtyDayAvgMinutes")),
                "rem_30day_avg":          int(_stage("rem",   "thirtyDayAvgMinutes")),
                "wake_30day_avg":         int(_stage("wake",  "thirtyDayAvgMinutes")),
            })
        return records
