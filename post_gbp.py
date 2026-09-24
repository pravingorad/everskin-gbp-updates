"""
EVERSKIN GBP AUTO-POST — GBP API POSTER
Handles OAuth refresh, optional photo upload, and post publishing.
"""

import os
import json
import base64
import datetime
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from colorama import init, Fore, Style

init(autoreset=True)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE  = os.path.join(BASE_DIR, "credentials", "token.json")
CONFIG_FILE = os.path.join(BASE_DIR, "data", "gbp_config.json")
LOG_FILE    = os.path.join(BASE_DIR, "data", "posts_log.json")

SCOPES = ["https://www.googleapis.com/auth/business.manage"]

GBP_POSTS_URL  = "https://mybusiness.googleapis.com/v4/{location_name}/localPosts"
GBP_MEDIA_URL  = "https://mybusiness.googleapis.com/v4/{location_name}/media"

# ── Auth ──────────────────────────────────────────────────────────────────────
def get_valid_credentials():
    # 1. Check environment variable (GitHub Actions)
    token_json = os.environ.get("GBP_TOKEN_JSON", "")
    if token_json:
        import io
        creds = Credentials.from_authorized_user_info(
            json.loads(token_json), SCOPES
        )
    # 2. Fall back to local file (Windows local run)
    elif os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    else:
        raise FileNotFoundError(
            f"Token not found: {TOKEN_FILE}\n"
            "LOCAL: Run setup.py first.\n"
            "GITHUB: Add GBP_TOKEN_JSON to repository secrets."
        )

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print(f"{Fore.YELLOW}ℹ  Refreshing token...{Style.RESET_ALL}")
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
            print(f"{Fore.GREEN}✅ Token refreshed.{Style.RESET_ALL}")
        else:
            raise Exception(
                "Token expired and cannot be refreshed.\n"
                "Run setup.py again to re-authenticate."
            )
    return creds

# ── Load Config ───────────────────────────────────────────────────────────────
def load_config():
    # 1. Check environment variable (GitHub Actions)
    config_json = os.environ.get("GBP_CONFIG_JSON", "")
    if config_json:
        return json.loads(config_json)

    # 2. Fall back to local file (Windows local run)
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(
            f"Config not found: {CONFIG_FILE}\n"
            "LOCAL: Run setup.py first.\n"
            "GITHUB: Add GBP_CONFIG_JSON to repository secrets."
        )
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

# ── Upload Photo ──────────────────────────────────────────────────────────────
def upload_photo(creds, location_name: str, photo_path: str) -> str | None:
    """
    Uploads a photo to GBP and returns the media name for attaching to post.
    Returns None if upload fails (post will continue without photo).
    """
    if not photo_path or not os.path.exists(photo_path):
        return None

    ext       = os.path.splitext(photo_path)[1].lower()
    mime_map  = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png", ".webp": "image/webp"}
    mime_type = mime_map.get(ext, "image/jpeg")

    print(f"{Fore.CYAN}▶ Uploading photo: {os.path.basename(photo_path)}{Style.RESET_ALL}")

    url     = GBP_MEDIA_URL.format(location_name=location_name)
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json"
    }

    # Step 1: Start resumable upload
    payload = {
        "mediaFormat": "PHOTO",
        "locationAssociation": {"category": "INTERIOR"}
    }

    # Use simple upload for small images
    with open(photo_path, "rb") as f:
        image_data = f.read()

    upload_url = f"{url}:startUpload"
    r = requests.post(upload_url, headers=headers, json=payload)

    if r.status_code not in (200, 201):
        print(f"{Fore.YELLOW}⚠  Photo upload skipped (API error {r.status_code}). Posting text only.{Style.RESET_ALL}")
        return None

    upload_info = r.json()
    upload_uri  = upload_info.get("uploadUri", "")

    if not upload_uri:
        print(f"{Fore.YELLOW}⚠  No upload URI returned. Posting text only.{Style.RESET_ALL}")
        return None

    # Step 2: Upload the actual bytes
    upload_headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": mime_type
    }
    r2 = requests.post(upload_uri, headers=upload_headers, data=image_data)

    if r2.status_code in (200, 201):
        print(f"{Fore.GREEN}✅ Photo uploaded successfully.{Style.RESET_ALL}")
        return upload_info.get("name", "")
    else:
        print(f"{Fore.YELLOW}⚠  Photo bytes upload failed ({r2.status_code}). Posting text only.{Style.RESET_ALL}")
        return None

# ── Post to GBP ───────────────────────────────────────────────────────────────
def post_to_gbp(post_content: dict) -> dict:
    """
    Publishes post to GBP. Attaches photo if available.

    Args:
        post_content: dict with keys: summary, photo_path, call_to_action
    Returns:
        GBP API response dict
    """
    creds         = get_valid_credentials()
    config        = load_config()
    location_name = f"{config['account_name']}/{config['location_name']}"

    # Build post payload
    action_type = post_content["call_to_action"]["action_type"]
    call_to_action = {"actionType": action_type}
    if action_type != "CALL":
        call_to_action["url"] = post_content["call_to_action"]["url"]

    payload = {
        "languageCode": "en-IN",
        "summary":      post_content["summary"],
        "topicType":    "STANDARD",
        "callToAction": call_to_action
    }

    # Attach photo if available
    photo_path  = post_content.get("photo_path")
    media_name  = upload_photo(creds, location_name, photo_path)
    if media_name:
        payload["media"] = [{"mediaFormat": "PHOTO", "name": media_name}]

    # Publish the post
    url     = GBP_POSTS_URL.format(location_name=location_name)
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type":  "application/json"
    }

    print(f"{Fore.CYAN}▶ Publishing post to GBP...{Style.RESET_ALL}")
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code in (200, 201):
        result = response.json()
        print(f"{Fore.GREEN}✅ Post published successfully!{Style.RESET_ALL}")
        print(f"   Post ID: {result.get('name', 'N/A')}")
        return result
    else:
        print(f"{Fore.RED}❌ Failed — Status: {response.status_code}{Style.RESET_ALL}")
        print(response.text)
        raise Exception(f"GBP API Error {response.status_code}: {response.text}")

# ── Log Result ────────────────────────────────────────────────────────────────
def log_result(post_content: dict, api_response: dict = None, error: str = None):
    log = {}
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            log = json.load(f)

    if "posted" not in log:
        log["posted"] = []

    entry = {
        "timestamp":      datetime.datetime.now().isoformat(),
        "date":           datetime.date.today().isoformat(),
        "service":        post_content.get("service_name", "Unknown"),
        "category":       post_content.get("category", "Unknown"),
        "summary_preview": post_content["summary"][:100] + "...",
        "photo_used":     bool(post_content.get("photo_path")),
        "status":         "success" if api_response else "failed",
        "post_id":        api_response.get("name", "") if api_response else "",
        "error":          error or ""
    }

    log["posted"].append(entry)

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
