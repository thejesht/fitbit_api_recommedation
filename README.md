# Fitbit Personal Data Pipeline & Recommendation Engine

A personal health data pipeline that syncs Fitbit activity, heart rate, and sleep data into Supabase (PostgreSQL), runs automated daily syncs via GitHub Actions, and produces sleep quality analysis with visualisations.

---

## Architecture Overview

```mermaid
graph LR
    subgraph Fitbit
        API["Fitbit Web API<br/>v1 & v1.2"]
    end

    subgraph Pipeline
        AUTH["auth.py<br/>OAuth 2.0"]
        CLIENT["client.py<br/>API Client"]
        SYNC["sync.py<br/>Sync Engine"]
    end

    subgraph Storage
        SUPA["Supabase<br/>PostgreSQL"]
        SQLITE["fitbit_data.db<br/>SQLite (local)"]
    end

    subgraph Automation
        GHA["GitHub Actions<br/>Daily Cron 01:00 UTC"]
        SCHED["scheduler.py<br/>Local Scheduler"]
    end

    subgraph Analysis
        SLEEP["sleep_analysis.py<br/>30-Day Sleep Charts"]
        WINDOW["sleep_window_analysis.py<br/>Readiness & Optimal Window"]
        OUT["output/<br/>PNG Charts"]
    end

    API -->|REST JSON| CLIENT
    AUTH -->|Access Token| CLIENT
    CLIENT --> SYNC
    SYNC -->|upsert| SUPA
    SYNC -->|upsert| SQLITE
    GHA -->|triggers| SYNC
    SCHED -->|triggers| SYNC
    SQLITE --> SLEEP
    SQLITE --> WINDOW
    SLEEP --> OUT
    WINDOW --> OUT
```

---

## Project Structure

```
fitbit_api_recommendation/
├── fitbit/                      # Core library package
│   ├── __init__.py              # Exposes FitbitClient
│   ├── auth.py                  # OAuth 2.0 flow & token management
│   ├── client.py                # Fitbit API client (activity, HR, sleep)
│   ├── database.py              # SQLite read/write layer (legacy, local)
│   └── supabase_db.py           # Supabase PostgreSQL layer (primary)
├── analysis/                    # Data analysis & visualisation
│   ├── sleep_analysis.py        # 30-day sleep charts (3 charts)
│   └── sleep_window_analysis.py # Sleep window & readiness (4 charts)
├── output/                      # Generated PNG charts (gitignored)
├── .github/workflows/
│   └── daily_sync.yml           # GitHub Actions daily sync at 01:00 UTC
├── sync.py                      # Entry point: run a full data sync
├── scheduler.py                 # Entry point: daily background scheduler
├── .env                         # Your credentials (gitignored)
├── .env.example                 # Safe credentials template
├── requirements.txt             # Python dependencies
└── fitbit_data.db               # Local SQLite database (gitignored)
```

---

## How It Works

### Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant AuthPy as auth.py
    participant Browser
    participant Fitbit as Fitbit OAuth
    participant Supabase as Supabase DB

    User->>AuthPy: python -m fitbit.auth
    AuthPy->>AuthPy: Start localhost:8080 callback server
    AuthPy->>Browser: Open authorization URL
    Browser->>Fitbit: User approves scopes (activity, heartrate, sleep)
    Fitbit->>Browser: Redirect to localhost:8080/callback?code=...
    Browser->>AuthPy: Authorization code received
    AuthPy->>Fitbit: Exchange code for tokens (Basic auth)
    Fitbit-->>AuthPy: access_token + refresh_token
    AuthPy->>Supabase: Upsert tokens into `tokens` table
    AuthPy-->>User: Authentication complete
```

- Tokens are stored in the `tokens` table in Supabase (keyed by `user_label = 'primary'`)
- Access tokens expire after **8 hours** — the client auto-refreshes on 401 responses
- In CI (GitHub Actions), tokens must already exist in Supabase; the interactive auth flow is skipped

### Sync Engine

```mermaid
flowchart TD
    START([sync.py]) --> INIT[init_db — ensure tables exist]
    INIT --> LOOP{For each data type:<br/>activity, heart_rate, sleep}

    LOOP --> CHECK[Query MAX date from table]
    CHECK --> DECIDE{Has data?}

    DECIDE -->|No| BACKFILL[Backfill mode:<br/>start = earliest date from API]
    DECIDE -->|Yes| INCREMENTAL[Incremental mode:<br/>start = last date + 1 day]

    BACKFILL --> UPTODATE{start > today?}
    INCREMENTAL --> UPTODATE

    UPTODATE -->|Yes| SKIP[Log 'up_to_date' — skip]
    UPTODATE -->|No| FETCH[Fetch in chunks from Fitbit API]

    FETCH --> UPSERT[Upsert records into Supabase]
    UPSERT --> LOG[Log sync result to sync_log]
    LOG --> LOOP

    SKIP --> LOOP
    LOOP -->|All done| DONE([All syncs complete])
```

The sync engine processes three data types in sequence, each with API-specific chunk sizes to avoid Fitbit rate limits and server errors:

| Data Type | API Endpoint | Chunk Size | Notes |
|-----------|-------------|------------|-------|
| Activity | `/activities/{resource}/date/{start}/{end}.json` | 365 days | Fetches steps, distance, calories, floors in parallel |
| Heart Rate | `/activities/heart/date/{start}/{end}.json` | 30 days | Kept small to avoid Fitbit 500 errors; retries with exponential backoff |
| Sleep | `/sleep/date/{start}/{end}.json` (v1.2) | 100 days | Filters to main sleep only; deduplicates by date |

### Daily Automation

```mermaid
flowchart LR
    subgraph GitHub Actions
        CRON["Cron: 0 1 * * *<br/>(01:00 UTC daily)"] --> CHECKOUT[Checkout repo]
        CHECKOUT --> SETUP[Setup Python 3.12]
        SETUP --> INSTALL[pip install -r requirements.txt]
        INSTALL --> RUN["python sync.py"]
        RUN --> SUPA[(Supabase)]
    end

    subgraph Local Alternative
        SCHED["python scheduler.py<br/>--time 08:00"] --> WAIT[Sleep until target time]
        WAIT --> SYNC["run_sync()"]
        SYNC --> SUPA2[(Supabase)]
        SYNC --> WAIT
    end
```

Two options for daily sync:
- **GitHub Actions** (recommended) — runs in the cloud, no machine needed; secrets stored in repo settings
- **Local scheduler** — `scheduler.py` runs as a background process, configurable via `--time HH:MM`

---

## Scopes & Data Collected

| Scope | Data Stored |
|-------|-------------|
| `activity` | Steps, distance (km), calories, floors — daily |
| `heartrate` | Resting HR, HR zone minutes & calories (Out of Range / Fat Burn / Cardio / Peak) — daily |
| `sleep` | Duration, efficiency, awakenings, deep / light / REM / wake stage minutes, 30-day stage averages — nightly |

---

## Database Schema

All tables use `date` as the primary key and include a `fetched_at` timestamp. The schema is identical between SQLite (`database.py`) and PostgreSQL (`supabase_db.py`).

```mermaid
erDiagram
    daily_activity {
        DATE date PK
        INTEGER steps
        NUMERIC distance_km
        INTEGER calories
        INTEGER floors
        TIMESTAMPTZ fetched_at
    }

    daily_heartrate {
        DATE date PK
        INTEGER resting_hr
        INTEGER out_of_range_minutes
        INTEGER fat_burn_minutes
        INTEGER cardio_minutes
        INTEGER peak_minutes
        NUMERIC out_of_range_calories
        NUMERIC fat_burn_calories
        NUMERIC cardio_calories
        NUMERIC peak_calories
        TIMESTAMPTZ fetched_at
    }

    daily_sleep {
        DATE date PK
        TEXT start_time
        TEXT end_time
        BIGINT duration_ms
        INTEGER time_in_bed
        INTEGER minutes_asleep
        INTEGER minutes_awake
        INTEGER minutes_to_fall_asleep
        INTEGER efficiency
        INTEGER awakenings_count
        INTEGER deep_minutes
        INTEGER light_minutes
        INTEGER rem_minutes
        INTEGER wake_minutes
        INTEGER deep_30day_avg
        INTEGER light_30day_avg
        INTEGER rem_30day_avg
        INTEGER wake_30day_avg
        TIMESTAMPTZ fetched_at
    }

    sync_log {
        SERIAL id PK
        TIMESTAMPTZ synced_at
        TEXT data_type
        INTEGER days_synced
        TEXT status
    }

    tokens {
        SERIAL id PK
        TEXT user_label
        TEXT access_token
        TEXT refresh_token
        TEXT token_type
        INTEGER expires_in
        TEXT scope
        TEXT user_id
        TIMESTAMPTZ updated_at
    }
```

---

## Analysis Scripts

### Sleep Analysis (`analysis/sleep_analysis.py`)

Reads the last 30 days from the local SQLite database and produces three charts:

```mermaid
flowchart TD
    DB[(fitbit_data.db)] --> LOAD[Load last 30 days of daily_sleep]
    LOAD --> FILL[Build full 30-day date range<br/>NaN for missing days]
    FILL --> C1["Chart 1: Time in Bed<br/>Bar chart vs 8-hr target<br/>Color: green ≥7h, amber 5-7h, red <5h"]
    FILL --> C2["Chart 2: Sleep Efficiency<br/>Line chart with 7-day rolling avg<br/>Bands: excellent ≥90%, good 85-90%, poor <85%"]
    FILL --> C3["Chart 3: Wake Minutes<br/>Bar chart with severity bands<br/>Thresholds: healthy ≤20min, elevated ≤45min"]
    C1 --> OUT1[output/time_in_bed.png]
    C2 --> OUT2[output/sleep_efficiency.png]
    C3 --> OUT3[output/wake_minutes.png]
```

Run it:
```bash
python analysis/sleep_analysis.py
```

### Sleep Window & Readiness Analysis (`analysis/sleep_window_analysis.py`)

Joins sleep data with next-day activity and heart rate to compute a composite readiness score and identify optimal sleep windows.

```mermaid
flowchart TD
    DB[(fitbit_data.db)] --> JOIN["SQL JOIN:<br/>daily_sleep + next-day daily_activity<br/>+ next-day daily_heartrate"]
    JOIN --> SCORE["Compute Readiness Score (0-100)<br/>40% Resting HR delta<br/>30% Sleep duration vs 8hr<br/>20% Deep sleep vs personal avg<br/>10% REM sleep vs personal avg"]
    JOIN --> C1["Chart 1: Duration vs Quality<br/>Deep/REM/efficiency/next-day steps<br/>by duration bucket"]
    JOIN --> C2["Chart 2: Bedtime vs Quality<br/>Bedtime & wake hour vs<br/>deep, REM, sleep hours"]
    JOIN --> C3["Chart 3: Optimal Sleep Window<br/>Visual timeline recommendation<br/>Bed 22:30-23:00, Wake 07:30-08:30"]
    SCORE --> C4["Chart 4: Sleep vs Readiness<br/>Scatter plots with correlation<br/>duration, deep, efficiency vs readiness"]
    C1 --> O1[output/sleep_duration_vs_quality.png]
    C2 --> O2[output/bedtime_vs_quality.png]
    C3 --> O3[output/optimal_sleep_window.png]
    C4 --> O4[output/sleep_vs_readiness.png]
```

Run it:
```bash
python analysis/sleep_window_analysis.py
```

---

## Setup

### 1. Register a Fitbit App

1. Go to [dev.fitbit.com](https://dev.fitbit.com) and log in
2. Click **Register an App**
3. Set **Application Type** to **Personal** (required for intraday data)
4. Set **Callback URL** to `http://localhost:8080/callback`
5. Copy your **Client ID** and **Client Secret**

### 2. Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a free project
2. Go to **Project Settings > Database > Connection Pooling**
3. Copy the **Connection string (URI)** — use the **pooler** URL (port 6543), not the direct connection

### 3. Configure Credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in:
```env
FITBIT_CLIENT_ID=your_client_id
FITBIT_CLIENT_SECRET=your_client_secret
FITBIT_REDIRECT_URL=http://localhost:8080/callback
FITBIT_AUTH_URI=https://www.fitbit.com/oauth2/authorize
FITBIT_TOKEN_URI=https://api.fitbit.com/oauth2/token
SUPABASE_DB_URL=postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

> **Important:** Use the pooler URL (`pooler.supabase.com:6543`) instead of the direct connection (`db.[ref].supabase.co:5432`). The direct host resolves to IPv6 only, which causes DNS failures in GitHub Actions and some cloud environments.

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Authenticate

```bash
python -m fitbit.auth
```

Your browser will open, you'll approve Fitbit access, and tokens will be saved to Supabase automatically.

### 6. Run the First Sync

```bash
python sync.py
```

On first run this backfills your entire history (up to 3 years). Subsequent runs only fetch new days.

### 7. Set Up GitHub Actions (Automated Daily Sync)

Add these secrets to your GitHub repo (**Settings > Secrets and variables > Actions**):

| Secret | Value |
|--------|-------|
| `FITBIT_CLIENT_ID` | Your Fitbit Client ID |
| `FITBIT_CLIENT_SECRET` | Your Fitbit Client Secret |
| `FITBIT_REDIRECT_URL` | `http://localhost:8080/callback` |
| `SUPABASE_DB_URL` | Your Supabase pooler connection string |

The workflow runs daily at 01:00 UTC. You can also trigger it manually from the **Actions** tab.

### 8. (Optional) Local Daily Scheduler

```bash
python scheduler.py              # syncs at 08:00 every day
python scheduler.py --time 22:30 # or choose your own time
```

---

## Python API Usage

```python
from fitbit import FitbitClient

client = FitbitClient()

# Today's activity summary
summary = client.get_daily_activity_summary("today")
# {'date': '2026-03-28', 'steps': 9367, 'distance_km': 6.92, 'calories': 2741, 'floors': 5}

# Last 7 days of activity
week = client.get_last_n_days(7)

# Steps time series for a date range
steps = client.get_activity_timeseries("steps", "2026-01-01", "2026-03-28")

# Intraday steps at 15-min resolution
intraday = client.get_intraday("steps", "today", "15min")

# Heart rate time series (resting HR + zones)
hr = client.get_heartrate_timeseries("2026-01-01", "2026-03-28")

# Sleep summaries with stage breakdowns
sleep = client.get_sleep_range("2026-01-01", "2026-03-28")
```

---

## Token Refresh

```mermaid
sequenceDiagram
    participant Client as FitbitClient
    participant API as Fitbit API
    participant Auth as auth.py
    participant DB as Supabase

    Client->>API: GET /activities/... (Bearer token)
    API-->>Client: 401 Unauthorized
    Client->>DB: Load refresh_token from tokens table
    Client->>Auth: refresh_access_token(refresh_token)
    Auth->>API: POST /oauth2/token (grant_type=refresh_token)
    API-->>Auth: New access_token + refresh_token
    Auth->>DB: Upsert new tokens
    Auth-->>Client: New access_token
    Client->>API: Retry original request with new token
    API-->>Client: 200 OK + data
```

Access tokens expire after **8 hours**. The client handles this transparently — on a 401 response it refreshes the token and retries the request without any manual intervention.

---

## Roadmap

- [x] Fitbit API client (activity, heart rate, sleep)
- [x] OAuth 2.0 with auto-refresh
- [x] Full history backfill + incremental daily sync
- [x] Supabase (PostgreSQL) storage with upsert semantics
- [x] GitHub Actions daily automation
- [x] Sleep quality analysis (30-day charts)
- [x] Sleep window & readiness score analysis
- [ ] Recommendation engine (correlate activity + sleep + HR patterns)
- [ ] Personal goal tracking & alerts
- [ ] Trend visualisation dashboard
