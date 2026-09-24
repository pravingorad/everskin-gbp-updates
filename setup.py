"""
EVERSKIN GBP AUTO-POST — SETUP SCRIPT
Run this ONCE to authenticate and discover your GBP Location ID.
After this, run_daily.py handles everything automatically.
"""

import os
import json
import sys
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import requests
from colorama import init, Fore, Style

init(autoreset=True)

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
CREDS_DIR       = os.path.join(BASE_DIR, "credentials")
CLIENT_SECRET   = os.path.join(CREDS_DIR, "client_secret.json")
TOKEN_FILE      = os.path.join(CREDS_DIR, "token.json")
CONFIG_FILE     = os.path.join(BASE_DIR, "data", "gbp_config.json")

SCOPES = ["https://www.googleapis.com/auth/business.manage"]

# ── Helpers ───────────────────────────────────────────────────────────────────
def print_step(msg):
    print(f"\n{Fore.CYAN}▶ {msg}{Style.RESET_ALL}")

def print_ok(msg):
    print(f"{Fore.GREEN}✅ {msg}{Style.RESET_ALL}")

def print_err(msg):
    print(f"{Fore.RED}❌ {msg}{Style.RESET_ALL}")

def print_info(msg):
    print(f"{Fore.YELLOW}ℹ  {msg}{Style.RESET_ALL}")

# ── Step 1 — Authenticate ─────────────────────────────────────────────────────
def authenticate():
    print_step("Authenticating with Google...")

    if not os.path.exists(CLIENT_SECRET):
        print_err(f"client_secret.json not found in: {CREDS_DIR}")
        print_info("Steps to fix:")
        print("  1. Go to https://console.cloud.google.com")
        print("  2. APIs & Services → Credentials")
        print("  3. Download your OAuth 2.0 Client ID JSON")
        print(f"  4. Save it as:  {CLIENT_SECRET}")
        sys.exit(1)

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print_info("Refreshing existing token...")
            creds.refresh(Request())
        else:
            print_info("Opening browser for Google login...")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
            creds = flow.run_local_server(port=61772)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    print_ok("Authentication successful. Token saved.")
    return creds

# ── Step 2 — Discover Accounts ────────────────────────────────────────────────
def get_accounts(creds):
    print_step("Fetching your GBP Accounts...")

    url = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
    headers = {"Authorization": f"Bearer {creds.token}"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print_err(f"Failed to fetch accounts: {response.status_code}")
        print(response.text)
        sys.exit(1)

    data = response.json()
    accounts = data.get("accounts", [])

    if not accounts:
        print_err("No GBP accounts found for this Google account.")
        sys.exit(1)

    print_ok(f"Found {len(accounts)} account(s):")
    for i, acc in enumerate(accounts):
        print(f"  [{i}] {acc.get('name')} — {acc.get('accountName', 'N/A')}")

    if len(accounts) == 1:
        chosen = accounts[0]
    else:
        idx = int(input("\nEnter the number of your account: "))
        chosen = accounts[idx]

    print_ok(f"Using account: {chosen.get('accountName', chosen.get('name'))}")
    return chosen

# ── Step 3 — Discover Locations ───────────────────────────────────────────────
def get_locations(creds, account):
    print_step("Fetching your GBP Locations (clinic listings)...")

    account_name = account["name"]
    url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_name}/locations"
    params = {
        "readMask": "name,title,phoneNumbers,storefrontAddress,websiteUri"
    }
    headers = {"Authorization": f"Bearer {creds.token}"}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print_err(f"Failed to fetch locations: {response.status_code}")
        print(response.text)
        sys.exit(1)

    data = response.json()
    locations = data.get("locations", [])

    if not locations:
        print_err("No locations found under this account.")
        sys.exit(1)

    print_ok(f"Found {len(locations)} location(s):")
    for i, loc in enumerate(locations):
        title   = loc.get("title", "Unknown")
        address = loc.get("storefrontAddress", {})
        city    = address.get("locality", "")
        print(f"  [{i}] {title} — {city}")

    if len(locations) == 1:
        chosen = locations[0]
    else:
        idx = int(input("\nEnter the number of your clinic location: "))
        chosen = locations[idx]

    print_ok(f"Using location: {chosen.get('title', chosen.get('name'))}")
    return chosen

# ── Step 4 — Save Config ──────────────────────────────────────────────────────
def save_config(account, location):
    config = {
        "account_name": account["name"],
        "location_name": location["name"],
        "location_title": location.get("title", "Everskin"),
        "setup_complete": True
    }

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

    print_ok(f"Config saved to: {CONFIG_FILE}")
    print_info(f"  Account  : {config['account_name']}")
    print_info(f"  Location : {config['location_name']}")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{Fore.MAGENTA}{'='*55}")
    print("   EVERSKIN GBP AUTO-POST — ONE-TIME SETUP")
    print(f"{'='*55}{Style.RESET_ALL}")

    creds    = authenticate()
    account  = get_accounts(creds)
    location = get_locations(creds, account)
    save_config(account, location)

    print(f"\n{Fore.GREEN}{'='*55}")
    print("   SETUP COMPLETE!")
    print("   Run 'python run_daily.py' to post manually.")
    print("   Or use 'setup_scheduler.bat' to automate daily.")
    print(f"{'='*55}{Style.RESET_ALL}\n")
