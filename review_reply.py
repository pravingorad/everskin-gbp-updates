"""
EVERSKIN GBP — AUTOMATIC REVIEW REPLY
Fetches unanswered Google reviews, generates SEO-friendly
personalised replies via Claude, and posts them via GBP API.
Runs every 6 hours via GitHub Actions.
"""

import os
import sys
import json
import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import requests
import anthropic
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from colorama import init, Fore, Style

init(autoreset=True)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE      = os.path.join(BASE_DIR, "credentials", "token.json")
CONFIG_FILE     = os.path.join(BASE_DIR, "data", "gbp_config.json")
API_KEYS_FILE   = os.path.join(BASE_DIR, "credentials", "api_keys.json")
REPLY_LOG_FILE  = os.path.join(BASE_DIR, "data", "review_reply_log.json")

SCOPES = ["https://www.googleapis.com/auth/business.manage"]

# ── Clinic Context for SEO ────────────────────────────────────────────────────
CLINIC = {
    "name":         "Everskin — The Aesthetic Skin Clinic",
    "doctor":       "Dr. Manisha Kolekar (BHMS, PGDCC)",
    "location":     "Pimple Saudagar, Pune",
    "areas":        "Pimple Saudagar, Wakad, Baner, Aundh, Rahatani, Hinjewadi",
    "phone":        "+91-9561296699",
    "website":      "everskin.co.in",
    "booking":      "everskin.co.in/book-appointment",
    "specialties":  "skin treatments, laser hair removal, HydraFacial, acne treatment, "
                    "pigmentation, melasma, RF microneedling, HIFU facelift, PRP, GFC hair treatment"
}

# ── Auth ──────────────────────────────────────────────────────────────────────
def get_credentials():
    token_json = os.environ.get("GBP_TOKEN_JSON", "")
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    elif os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    else:
        raise FileNotFoundError("GBP token not found. Run setup.py or set GBP_TOKEN_JSON secret.")

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            if os.path.exists(TOKEN_FILE):
                with open(TOKEN_FILE, "w") as f:
                    f.write(creds.to_json())
        else:
            raise Exception("Token expired. Re-run setup.py.")
    return creds

def load_config():
    config_json = os.environ.get("GBP_CONFIG_JSON", "")
    if config_json:
        return json.loads(config_json)
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def load_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key and key.startswith("sk-ant-"):
        return key
    if os.path.exists(API_KEYS_FILE):
        with open(API_KEYS_FILE, "r") as f:
            keys = json.load(f)
        key = keys.get("anthropic_api_key", "")
        if key and key != "sk-ant-YOUR_KEY_HERE":
            return key
    raise ValueError("Anthropic API key not found.")

# ── Load Reply Log ────────────────────────────────────────────────────────────
def load_reply_log():
    if os.path.exists(REPLY_LOG_FILE):
        with open(REPLY_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"replied_review_ids": [], "replies": []}

def save_reply_log(log):
    with open(REPLY_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

# ── Fetch Reviews ─────────────────────────────────────────────────────────────
def fetch_reviews(creds, location_name: str) -> list:
    """Fetches all reviews from GBP."""
    url     = f"https://mybusiness.googleapis.com/v4/{location_name}/reviews"
    headers = {"Authorization": f"Bearer {creds.token}"}
    params  = {"pageSize": 50, "orderBy": "updateTime desc"}

    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        raise Exception(f"Failed to fetch reviews: {response.status_code} — {response.text}")

    data    = response.json()
    reviews = data.get("reviews", [])
    print(f"{Fore.CYAN}▶ Fetched {len(reviews)} reviews{Style.RESET_ALL}")
    return reviews

# ── Filter Unanswered ─────────────────────────────────────────────────────────
def get_unanswered(reviews: list, log: dict) -> list:
    """Returns reviews that have no reply yet and haven't been processed."""
    already_replied = set(log.get("replied_review_ids", []))
    unanswered = []

    for review in reviews:
        review_id    = review.get("reviewId", "")
        has_reply    = bool(review.get("reviewReply"))
        already_done = review_id in already_replied

        if not has_reply and not already_done:
            unanswered.append(review)

    print(f"{Fore.CYAN}▶ Unanswered reviews: {len(unanswered)}{Style.RESET_ALL}")
    return unanswered

# ── Generate SEO Reply ────────────────────────────────────────────────────────
def generate_reply(review: dict) -> str:
    """
    Uses Claude to generate an SEO-friendly, personalised review reply.
    """
    api_key  = load_api_key()
    client   = anthropic.Anthropic(api_key=api_key)

    # Extract review details
    reviewer     = review.get("reviewer", {}).get("displayName", "there")
    star_rating  = review.get("starRating", "FIVE")   # ONE, TWO, THREE, FOUR, FIVE
    review_text  = review.get("comment", "").strip()
    star_num     = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}.get(star_rating, 5)

    # Tone instructions based on rating
    if star_num == 5:
        tone_guide = (
            "Warm, grateful, and enthusiastic. "
            "Reinforce the specific result or service they mentioned. "
            "Invite them back."
        )
    elif star_num == 4:
        tone_guide = (
            "Warm and appreciative. "
            "Acknowledge any mild concern or suggestion they raised. "
            "Reassure and invite them back."
        )
    elif star_num == 3:
        tone_guide = (
            "Empathetic and professional. "
            "Acknowledge their experience without being defensive. "
            "Offer to discuss further and improve. "
            "Provide contact details."
        )
    else:  # 1-2 stars
        tone_guide = (
            "Calm, professional, and empathetic — never defensive or dismissive. "
            "Sincerely apologise for the experience. "
            "Take ownership and offer to resolve personally. "
            "Provide direct contact. "
            "Show that this matters to the clinic."
        )

    prompt = f"""You are writing a Google review reply on behalf of an aesthetic skin clinic in Pune, India.

CLINIC DETAILS:
- Name: {CLINIC['name']}
- Doctor: {CLINIC['doctor']}
- Location: {CLINIC['location']}
- Serves: {CLINIC['areas']}
- Website: {CLINIC['website']}
- Specialties: {CLINIC['specialties']}

REVIEW DETAILS:
- Reviewer name: {reviewer}
- Star rating: {star_num}/5
- Review text: "{review_text if review_text else '[No text — rating only]'}"

TONE: {tone_guide}

SEO REQUIREMENTS (apply naturally — never force keywords):
- Mention the clinic name "{CLINIC['name']}" at least once
- Mention "Pimple Saudagar" or "Pune" at least once
- If the reviewer mentions a specific treatment, use that treatment name in your reply
- Naturally include 1–2 relevant service keywords (e.g. "skin treatment", "laser treatment", "HydraFacial") only if they fit contextually
- Do not stuff keywords — the reply must read as genuine and human

STRICT RULES:
- Address reviewer by first name if available (use "{reviewer.split()[0]}" )
- Length: 60–120 words (concise — long replies look automated)
- No bullet points, no numbered lists
- No hashtags
- No ALL CAPS
- End with clinic name on the last line
- Do not repeat the same phrases used in other replies
- Sound like a real person, not a template

Write only the reply text. No intro, no explanation."""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=250,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text.strip()

# ── Post Reply ────────────────────────────────────────────────────────────────
def post_reply(creds, review_name: str, reply_text: str) -> bool:
    """Posts the reply to a specific review."""
    url     = f"https://mybusiness.googleapis.com/v4/{review_name}/reply"
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type":  "application/json"
    }
    payload = {"comment": reply_text}

    response = requests.put(url, headers=headers, json=payload)

    if response.status_code in (200, 201):
        print(f"{Fore.GREEN}  ✅ Reply posted successfully{Style.RESET_ALL}")
        return True
    else:
        print(f"{Fore.RED}  ❌ Failed to post reply: {response.status_code}{Style.RESET_ALL}")
        print(f"     {response.text}")
        return False

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n{Fore.MAGENTA}{'='*55}")
    print("  EVERSKIN — REVIEW AUTO-REPLY")
    print(f"  {datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')}")
    print(f"{'='*55}{Style.RESET_ALL}\n")

    creds   = get_credentials()
    config  = load_config()
    log     = load_reply_log()

    location_name = config["location_name"]

    # Fetch + filter
    reviews    = fetch_reviews(creds, location_name)
    unanswered = get_unanswered(reviews, log)

    if not unanswered:
        print(f"{Fore.GREEN}✅ All reviews already have replies. Nothing to do.{Style.RESET_ALL}")
        return

    replied_count = 0
    failed_count  = 0

    for review in unanswered:
        review_id   = review.get("reviewId", "")
        review_name = review.get("name", "")
        reviewer    = review.get("reviewer", {}).get("displayName", "Anonymous")
        stars       = review.get("starRating", "?")
        text        = review.get("comment", "")[:80] or "[No text]"

        print(f"\n{Fore.CYAN}{'─'*55}{Style.RESET_ALL}")
        print(f"  Reviewer : {reviewer}")
        print(f"  Rating   : {stars}")
        print(f"  Preview  : {text}...")
        print(f"{Fore.CYAN}{'─'*55}{Style.RESET_ALL}")

        # Generate reply
        print(f"{Fore.CYAN}  ▶ Generating SEO reply...{Style.RESET_ALL}")
        try:
            reply_text = generate_reply(review)
            print(f"\n  Reply preview:\n  {reply_text[:120]}...\n")
        except Exception as e:
            print(f"{Fore.RED}  ❌ Claude error: {e}{Style.RESET_ALL}")
            failed_count += 1
            continue

        # Post reply
        success = post_reply(creds, review_name, reply_text)

        # Log result
        log["replied_review_ids"].append(review_id)
        log["replies"].append({
            "timestamp":    datetime.datetime.now().isoformat(),
            "review_id":    review_id,
            "reviewer":     reviewer,
            "star_rating":  stars,
            "review_text":  review.get("comment", "")[:200],
            "reply_text":   reply_text,
            "status":       "success" if success else "failed"
        })
        save_reply_log(log)

        if success:
            replied_count += 1
        else:
            failed_count += 1

    # Summary
    print(f"\n{Fore.MAGENTA}{'='*55}")
    print(f"  DONE — Replied: {replied_count} | Failed: {failed_count}")
    print(f"{'='*55}{Style.RESET_ALL}\n")

if __name__ == "__main__":
    main()
