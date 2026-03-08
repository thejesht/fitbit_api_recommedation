"""
Fitbit OAuth 2.0 Authentication
Handles the full authorization code flow and token management.
"""

import os
import base64
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

import requests
from dotenv import load_dotenv

from fitbit.supabase_db import get_conn

load_dotenv()

CLIENT_ID = os.getenv("FITBIT_CLIENT_ID")
CLIENT_SECRET = os.getenv("FITBIT_CLIENT_SECRET")
REDIRECT_URL = os.getenv("FITBIT_REDIRECT_URL")
AUTH_URI = os.getenv("FITBIT_AUTH_URI")
TOKEN_URI = os.getenv("FITBIT_TOKEN_URI")

# Scopes focused on activity data
SCOPES = "activity heartrate sleep"


# ── Token storage ──────────────────────────────────────────────────────────────

def save_tokens(tokens: dict):
    sql = """
        INSERT INTO tokens (
            user_label, access_token, refresh_token,
            token_type, expires_in, scope, user_id, updated_at
        )
        VALUES ('primary', %(access_token)s, %(refresh_token)s,
                %(token_type)s, %(expires_in)s, %(scope)s, %(user_id)s, NOW())
        ON CONFLICT (user_label) DO UPDATE SET
            access_token  = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            token_type    = EXCLUDED.token_type,
            expires_in    = EXCLUDED.expires_in,
            scope         = EXCLUDED.scope,
            user_id       = EXCLUDED.user_id,
            updated_at    = NOW()
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "access_token":  tokens.get("access_token"),
                "refresh_token": tokens.get("refresh_token"),
                "token_type":    tokens.get("token_type"),
                "expires_in":    tokens.get("expires_in"),
                "scope":         tokens.get("scope"),
                "user_id":       tokens.get("user_id"),
            })
    print("Tokens saved to Supabase.")


def load_tokens() -> dict | None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT access_token, refresh_token, token_type,
                       expires_in, scope, user_id
                FROM tokens WHERE user_label = 'primary'
            """)
            row = cur.fetchone()
            if row is None:
                return None
            return {
                "access_token":  row[0],
                "refresh_token": row[1],
                "token_type":    row[2],
                "expires_in":    row[3],
                "scope":         row[4],
                "user_id":       row[5],
            }


# ── OAuth flow ─────────────────────────────────────────────────────────────────

# Shared variable to capture the auth code from the callback
_auth_code = None


class _CallbackHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler to capture the OAuth callback."""

    def do_GET(self):
        global _auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _auth_code = params["code"][0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>Authentication successful! You can close this tab.</h2>")
        else:
            error = params.get("error", ["unknown"])[0]
            self.send_response(400)
            self.end_headers()
            self.wfile.write(f"<h2>Authentication failed: {error}</h2>".encode())

    def log_message(self, format, *args):
        pass  # suppress server logs


def _start_callback_server(port: int = 8080) -> HTTPServer:
    server = HTTPServer(("localhost", port), _CallbackHandler)
    thread = Thread(target=server.handle_request)  # handle exactly one request
    thread.daemon = True
    thread.start()
    return server


def get_authorization_url() -> str:
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URL,
        "scope": SCOPES,
        "expires_in": "604800",  # 7 days token lifetime
    }
    return f"{AUTH_URI}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "client_id": CLIENT_ID,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URL,
        "code": code,
    }
    response = requests.post(TOKEN_URI, headers=headers, data=data)
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token: str) -> dict:
    """Use the refresh token to obtain a new access token."""
    credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    response = requests.post(TOKEN_URI, headers=headers, data=data)
    response.raise_for_status()
    tokens = response.json()
    save_tokens(tokens)
    return tokens


def get_valid_access_token() -> str:
    """
    Return a valid access token, refreshing automatically if needed.
    Runs the full auth flow if no tokens exist yet (local only — blocked in CI).
    """
    tokens = load_tokens()

    if tokens is None:
        if os.getenv("CI"):
            raise RuntimeError(
                "No tokens found in Supabase and running in CI. "
                "Run the auth flow locally first to seed tokens."
            )
        print("No tokens found — starting authorization flow...")
        tokens = run_auth_flow()

    # Try to use the existing token; refresh if the API returns 401
    return tokens["access_token"]


# ── Main auth flow ─────────────────────────────────────────────────────────────

def run_auth_flow() -> dict:
    """Open browser, capture callback, exchange code for tokens."""
    global _auth_code
    _auth_code = None

    print("Starting local callback server on port 8080...")
    _start_callback_server(port=8080)

    auth_url = get_authorization_url()
    print(f"\nOpening browser for Fitbit authorization...\n{auth_url}\n")
    webbrowser.open(auth_url)

    print("Waiting for Fitbit to redirect back...")
    import time
    for _ in range(60):          # wait up to 60 seconds
        if _auth_code:
            break
        time.sleep(1)

    if not _auth_code:
        raise TimeoutError("Did not receive authorization code within 60 seconds.")

    print("Authorization code received. Exchanging for tokens...")
    tokens = exchange_code_for_tokens(_auth_code)
    save_tokens(tokens)
    print("Authentication complete!")
    return tokens


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tokens = run_auth_flow()
    print(f"\nAccess token (first 20 chars): {tokens['access_token'][:20]}...")
    print(f"Token type : {tokens.get('token_type')}")
    print(f"Expires in : {tokens.get('expires_in')} seconds")
    print(f"Scope      : {tokens.get('scope')}")
