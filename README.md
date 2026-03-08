# Fitbit Personal Recommendation App

A personal data pipeline that connects to the Fitbit API, stores your health history in a local SQLite database, and lays the groundwork for personalised activity recommendations.

---

## Project Structure

```
fitbit_api_recommendation/
├── fitbit/                  # Core library package
│   ├── __init__.py          # Exposes FitbitClient
│   ├── auth.py              # OAuth 2.0 flow & token management
│   ├── client.py            # Fitbit API client (activity, heart rate, sleep)
│   └── database.py          # SQLite read/write layer
├── sync.py                  # Entry point: run a full data sync
├── scheduler.py             # Entry point: daily background scheduler
├── .env                     # Your credentials (gitignored — never commit)
├── .env.example             # Safe credentials template
├── requirements.txt         # Python dependencies
├── fitbit_data.db           # Local SQLite database (gitignored, auto-created)
└── tokens.json              # OAuth tokens (gitignored, auto-created)
```

---

## Scopes & Data Collected

| Scope | Data stored |
|-------|-------------|
| `activity` | Steps, distance (km), calories, floors — daily |
| `heartrate` | Resting HR, HR zone minutes & calories (Out of Range / Fat Burn / Cardio / Peak) — daily |
| `sleep` | Sleep duration, efficiency, awakenings, deep / light / REM / wake stage minutes, 30-day averages — nightly |

---

## Database Schema

### `daily_activity`
| Column | Type | Description |
|--------|------|-------------|
| `date` | TEXT PK | YYYY-MM-DD |
| `steps` | INTEGER | Total steps |
| `distance_km` | REAL | Total distance in kilometres |
| `calories` | INTEGER | Total calories burned |
| `floors` | INTEGER | Floors climbed |

### `daily_heartrate`
| Column | Type | Description |
|--------|------|-------------|
| `date` | TEXT PK | YYYY-MM-DD |
| `resting_hr` | INTEGER | Resting heart rate (bpm) |
| `out_of_range_minutes` | INTEGER | Minutes in resting zone (< Fat Burn) |
| `fat_burn_minutes` | INTEGER | Minutes in fat burn zone |
| `cardio_minutes` | INTEGER | Minutes in cardio zone |
| `peak_minutes` | INTEGER | Minutes in peak zone |
| `out_of_range_calories` | REAL | Calories burned in each zone |
| `fat_burn_calories` | REAL | |
| `cardio_calories` | REAL | |
| `peak_calories` | REAL | |

### `daily_sleep`
| Column | Type | Description |
|--------|------|-------------|
| `date` | TEXT PK | Date of sleep (YYYY-MM-DD) |
| `start_time` | TEXT | Sleep start timestamp |
| `end_time` | TEXT | Sleep end timestamp |
| `duration_ms` | INTEGER | Total duration in milliseconds |
| `time_in_bed` | INTEGER | Total minutes in bed |
| `minutes_asleep` | INTEGER | Actual sleep time (minutes) |
| `minutes_awake` | INTEGER | Minutes awake during the night |
| `minutes_to_fall_asleep` | INTEGER | Sleep onset latency (minutes) |
| `efficiency` | INTEGER | Sleep efficiency score (0–100) |
| `awakenings_count` | INTEGER | Number of awakenings |
| `deep_minutes` | INTEGER | Deep sleep (minutes) |
| `light_minutes` | INTEGER | Light sleep (minutes) |
| `rem_minutes` | INTEGER | REM sleep (minutes) |
| `wake_minutes` | INTEGER | Wake time during sleep (minutes) |
| `deep_30day_avg` | INTEGER | 30-day rolling averages for each stage |
| `light_30day_avg` | INTEGER | |
| `rem_30day_avg` | INTEGER | |
| `wake_30day_avg` | INTEGER | |

---

## Setup

### 1. Register a Fitbit app

1. Go to [dev.fitbit.com](https://dev.fitbit.com) and log in
2. Click **Register an App**
3. Set **Application Type** to **Personal** (required for intraday data)
4. Set **Callback URL** to `http://localhost:8080/callback`
5. Copy your **Client ID** and **Client Secret**

### 2. Configure credentials

```bash
cp .env.example .env
# Edit .env and fill in your Client ID and Client Secret
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Authenticate

```bash
python -m fitbit.auth
```

Your browser will open, you'll approve Fitbit access, and `tokens.json` will be saved automatically.

### 5. Run the first sync (backfills full history)

```bash
python sync.py
```

On first run this backfills your entire history (up to 3 years). Subsequent runs only fetch new days.

### 6. Start the daily scheduler

```bash
python scheduler.py              # syncs at 08:00 every day
python scheduler.py --time 22:30 # or choose your own time
```

---

## Usage — Python API

```python
from fitbit import FitbitClient

client = FitbitClient()

# Today's activity
summary = client.get_daily_activity_summary("today")
# {'date': '2026-03-08', 'steps': 9367, 'distance_km': 6.92, 'calories': 2741, 'floors': 5}

# Last 7 days of activity
week = client.get_last_n_days(7)

# Steps time series for a date range
steps = client.get_activity_timeseries("steps", "2026-01-01", "2026-03-08")

# Intraday steps at 15-min resolution
intraday = client.get_intraday("steps", "today", "15min")

# Heart rate time series
hr = client.get_heartrate_timeseries("2026-01-01", "2026-03-08")

# Sleep summaries
sleep = client.get_sleep_range("2026-01-01", "2026-03-08")
```

---

## Token Refresh

Access tokens expire after **8 hours**. The client handles this automatically — on a 401 response it uses the stored refresh token to obtain a new access token and retries the request transparently.

---

## Roadmap

- [ ] Recommendation engine (correlate activity + sleep + heart rate)
- [ ] Personal goal tracking & alerts
- [ ] Trend visualisation
