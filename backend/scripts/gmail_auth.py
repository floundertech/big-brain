"""
One-time Gmail OAuth2 authorization script for headless servers.

Run from docker01 project root (/home/mrokern/big-brain):

  Step 1 — On docker01, remove any stale token:
    rm -rf gmail_token.json

  Step 2 — On your Mac, open an SSH tunnel (keep this terminal open):
    ssh -L 8090:localhost:8090 mrokern@docker01

  Step 3 — On docker01, run this script:
    docker compose run --rm \\
      -p 8090:8090 \\
      -v $(pwd)/credentials.json:/app/credentials.json \\
      -v $(pwd):/tokens \\
      -v $(pwd)/backend/scripts:/app/scripts \\
      backend python /app/scripts/gmail_auth.py

  Step 4 — Open the printed URL in your Mac browser, authorize, done.

Both credentials.json and gmail_token.json are gitignored.
"""
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# credentials.json is mounted at /app/credentials.json in the container.
# gmail_token.json is written to /tokens (project root bind-mounted) so it
# persists on the host after the container exits.
_CREDENTIALS = Path(os.environ.get("GMAIL_CREDENTIALS", "/app/credentials.json"))
_TOKEN = Path(os.environ.get("GMAIL_TOKEN", "/tokens/gmail_token.json"))
_PORT = int(os.environ.get("OAUTH_PORT", "8090"))

_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _run_oauth_flow(credentials_file):
    """
    Run the OAuth flow using a custom callback server bound to 0.0.0.0.

    run_local_server() binds to localhost (127.0.0.1) inside the container.
    Docker's port mapping routes to the container's eth0 IP, not its loopback,
    so traffic from the SSH tunnel is dropped. Binding to 0.0.0.0 fixes this.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_file),
        scopes=_SCOPES,
        redirect_uri=f"http://localhost:{_PORT}",
    )
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")

    print(f"\nOpen this URL in your Mac browser:\n\n  {auth_url}\n")
    print(f"Waiting for OAuth callback on port {_PORT}...")
    print(f"(SSH tunnel must be active: ssh -L {_PORT}:localhost:{_PORT} mrokern@docker01)\n")

    received = {}

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            params = parse_qs(urlparse(self.path).query)
            if "code" in params:
                received["code"] = params["code"][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Authorization successful! You can close this tab.")
            else:
                self.send_response(400)
                self.end_headers()
                error = params.get("error", ["unknown"])[0]
                self.wfile.write(f"Authorization failed: {error}".encode())

        def log_message(self, fmt, *args):
            pass  # suppress request noise

    HTTPServer(("0.0.0.0", _PORT), _Handler).handle_request()

    if "code" not in received:
        print("No authorization code received.")
        sys.exit(1)

    flow.fetch_token(code=received["code"])
    return flow.credentials


def main():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        print("Missing dependencies. Run: pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    if not _CREDENTIALS.exists():
        print(f"credentials.json not found at {_CREDENTIALS}")
        print("Download it from Google Cloud Console → APIs & Services → Credentials")
        sys.exit(1)

    creds = None
    if _TOKEN.exists() and _TOKEN.stat().st_size > 0:
        creds = Credentials.from_authorized_user_file(str(_TOKEN), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing existing token...")
            creds.refresh(Request())
        else:
            creds = _run_oauth_flow(_CREDENTIALS)

        _TOKEN.write_text(creds.to_json())
        print(f"\nToken saved to {_TOKEN}")
    else:
        print(f"Token already valid at {_TOKEN}")

    # Quick sanity check
    try:
        from googleapiclient.discovery import build
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        profile = service.users().getProfile(userId="me").execute()
        print(f"Authorized as: {profile['emailAddress']}")
        print("Gmail connector is ready. Start the app and apply the 'big-brain' label to any email to ingest it.")
    except Exception as e:
        print(f"Auth succeeded but profile check failed: {e}")


if __name__ == "__main__":
    main()
