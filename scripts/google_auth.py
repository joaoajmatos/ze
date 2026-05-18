#!/usr/bin/env python
"""One-time Google OAuth2 flow. Prints the fly secrets set command for the refresh token.

Usage:
    1. Download client_secrets.json from Google Cloud Console (OAuth 2.0 Client ID, Desktop app).
    2. Enable Google Calendar API and Gmail API in your Cloud project.
    3. Add your Google account as a test user while the app is in testing mode.
    4. Run: python scripts/google_auth.py
    5. Authorise in the browser that opens.
    6. Copy and run the printed fly command.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
]

if __name__ == "__main__":
    flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n✓ Authorisation complete. Run the following to store the token:\n")
    print(f"fly secrets set GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
    print(f"\nAlso set client credentials if not already in Fly secrets:")
    print(f"fly secrets set GOOGLE_CLIENT_ID=<your-client-id>")
    print(f"fly secrets set GOOGLE_CLIENT_SECRET=<your-client-secret>")
