"""
One-time Gmail OAuth2 authorization script.

Usage (from project root):
    docker compose run --rm \\
      -v $(pwd)/credentials.json:/app/credentials.json \\
      -v $(pwd):/tokens \\
      backend python scripts/gmail_auth.py

Prerequisites:
    1. Create a Google Cloud project at https://console.cloud.google.com
    2. Enable the Gmail API (APIs & Services → Library → Gmail API)
    3. Create OAuth 2.0 credentials (APIs & Services → Credentials → Create → OAuth client ID)
       - Application type: Desktop app
       - Download the JSON and save it as credentials.json in the project root
    4. Run this script — it will print a URL to open in your browser
    5. Authorize in the browser, copy the code, paste it back into the terminal
    6. gmail_token.json is written to the project root

Both credentials.json and gmail_token.json are gitignored.
"""
import os
import sys
from pathlib import Path

# credentials.json is mounted at /app/credentials.json in the container.
# gmail_token.json is written to /tokens (project root bind-mounted) so it
# persists on the host after the container exits.
_CREDENTIALS = Path(os.environ.get("GMAIL_CREDENTIALS", "/app/credentials.json"))
_TOKEN = Path(os.environ.get("GMAIL_TOKEN", "/tokens/gmail_token.json"))

_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
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
    if _TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing existing token...")
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(_CREDENTIALS), _SCOPES)
            creds = flow.run_console()

        _TOKEN.write_text(creds.to_json())
        print(f"Token saved to {_TOKEN}")
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
