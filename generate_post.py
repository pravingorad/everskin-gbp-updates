"""
EVERSKIN GBP AUTO-POST — AI CONTENT GENERATOR
Uses Claude API to write a unique, fresh GBP post every day.
Rotates through all 26 services. Never repeats.
Also picks a matching clinic photo for the post.
"""

import os
import sys
import json
import datetime
import random

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import anthropic
from colorama import init, Fore, Style
init(autoreset=True)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CALENDAR_FILE = os.path.join(BASE_DIR, "data", "content_calendar.json")
LOG_FILE      = os.path.join(BASE_DIR, "data", "posts_log.json")
PHOTOS_DIR    = os.path.join(BASE_DIR, "data", "clinic_photos")
API_KEYS_FILE = os.path.join(BASE_DIR, "credentials", "api_keys.json")

# ── Load API Key ──────────────────────────────────────────────────────────────
def load_api_key():
    # 1. Check environment variable first (GitHub Actions / any CI)
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key and key.startswith("sk-ant-"):
        return key

    # 2. Fall back to local credentials file (Windows local run)
    if os.path.exists(API_KEYS_FILE):
        with open(API_KEYS_FILE, "r") as f:
            keys = json.load(f)
        key = keys.get("anthropic_api_key", "")
        if key and key != "sk-ant-YOUR_KEY_HERE":
            return key

    raise ValueError(
        "Anthropic API key not found.\n"
        "LOCAL: Edit credentials/api_keys.json and add your key.\n"
        "GITHUB: Add ANTHROPIC_API_KEY to repository secrets."
    )

# ── Load Data ─────────────────────────────────────────────────────────────────
def load_calendar():
    with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_log():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"posted": [], "last_service_index": -1}

def save_log(log):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

# ── Service Rotation ──────────────────────────────────────────────────────────
def get_next_service():
    """Picks the next service in rotation. Cycles through all 26 sequentially."""
    calendar = load_calendar()
    log      = load_log()
    services = calendar["services"]

    last_idx = log.get("last_service_index", -1)
    next_idx = (last_idx + 1) % len(services)

    service = services[next_idx]

    # Save rotation position
    log["last_service_index"] = next_idx
    save_log(log)

    return service, calendar["clinic"], next_idx, len(services)

# ── Photo Picker ──────────────────────────────────────────────────────────────
def get_matching_photo(service_name: str, category: str) -> str | None:
    """
    Returns path to a matching clinic photo.
    Looks for category-named subfolders first, then falls back to general pool.
    Returns None if no photos available.
    """
    if not os.path.exists(PHOTOS_DIR):
        return None

    supported = (".jpg", ".jpeg", ".png", ".webp")

    # Try category subfolder first (e.g. data/clinic_photos/Laser Treatments/)
    category_folder = os.path.join(PHOTOS_DIR, category)
    if os.path.isdir(category_folder):
        photos = [
            os.path.join(category_folder, f)
            for f in os.listdir(category_folder)
            if f.lower().endswith(supported)
        ]
        if photos:
            return random.choice(photos)

    # Fallback: any photo in the general pool
    all_photos = [
        os.path.join(PHOTOS_DIR, f)
        for f in os.listdir(PHOTOS_DIR)
        if f.lower().endswith(supported)
    ]
    return random.choice(all_photos) if all_photos else None

# ── Claude AI Post Generator ──────────────────────────────────────────────────
def generate_post_with_claude(service: dict, clinic: dict) -> str:
    """
    Calls Claude API to write a unique GBP post for the given service.
    """
    api_key = load_api_key()
    client  = anthropic.Anthropic(api_key=api_key)

    today        = datetime.date.today()
    day_name     = today.strftime("%A")
    month_name   = today.strftime("%B")
    season       = get_season(today.month)
    areas_served = clinic["areas_served"]

    prompt = f"""You are writing a Google Business Profile (GBP) post for a premium aesthetic skin clinic in Pune, India.

CLINIC DETAILS:
- Name: {clinic['name']}
- Doctor: {clinic['doctor']}
- Location: {clinic['location']}
- Phone: {clinic['phone']}
- Website: {clinic['website']}
- Areas served: {areas_served}

TODAY'S SERVICE TO FEATURE:
- Service: {service['name']}
- Category: {service['category']}

CONTEXT:
- Day: {day_name}
- Month: {month_name}
- Season: {season}

INSTRUCTIONS:
1. Write ONE compelling GBP post about this service
2. Length: 150–250 words
3. Tone: warm, professional, trustworthy — not salesy
4. Start with a hook (question, bold statement, or relatable problem)
5. Mention the service benefits naturally (2–3 key points)
6. Include the doctor's name and credentials once
7. End with location + phone + website on separate lines
8. Use 2–3 relevant emojis naturally (not excessive)
9. Include a subtle seasonal or day-relevant angle if it fits naturally
10. Format with line breaks for readability
11. Do NOT use hashtags
12. Do NOT use ALL CAPS
13. The post must feel fresh and different — avoid generic phrases like "best clinic" or "world-class"

Write only the post content. No intro, no explanation."""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text.strip()

# ── Season Helper ─────────────────────────────────────────────────────────────
def get_season(month: int) -> str:
    if month in (3, 4, 5):
        return "Summer (hot, humid — skin needs extra care)"
    elif month in (6, 7, 8, 9):
        return "Monsoon (humidity, fungal issues, pigmentation flares)"
    elif month in (10, 11):
        return "Post-monsoon / Festive season (weddings, events)"
    else:
        return "Winter (dry skin, good time for laser treatments)"

# ── Main Entry Point ──────────────────────────────────────────────────────────
def get_next_post() -> dict:
    """
    Main function called by run_daily.py.
    Returns a post dict ready for GBP API.
    """
    service, clinic, idx, total = get_next_service()

    print(f"{Fore.CYAN}▶ Generating post for: {service['name']} ({idx+1}/{total}){Style.RESET_ALL}")

    # Generate post text via Claude
    post_text = generate_post_with_claude(service, clinic)

    # Pick matching photo
    photo_path = get_matching_photo(service["name"], service["category"])
    if photo_path:
        print(f"{Fore.GREEN}📷 Photo selected: {os.path.basename(photo_path)}{Style.RESET_ALL}")
    else:
        print(f"{Fore.YELLOW}⚠  No photos found in data/clinic_photos/ — posting text only.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}   Add clinic photos to: {PHOTOS_DIR}{Style.RESET_ALL}")

    return {
        "service_name": service["name"],
        "category":     service["category"],
        "summary":      post_text,
        "photo_path":   photo_path,
        "call_to_action": {
            "action_type": "BOOK",
            "url": clinic["booking_url"]
        },
        "rotation_info": {
            "service_index": idx,
            "position": f"{idx+1}/{total}"
        }
    }

# ── Preview Mode ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{Fore.MAGENTA}{'='*55}")
    print("   EVERSKIN — AI POST GENERATOR PREVIEW")
    print(f"{'='*55}{Style.RESET_ALL}\n")

    post = get_next_post()

    print(f"\n{'='*55}")
    print(f"SERVICE  : {post['service_name']}")
    print(f"CATEGORY : {post['category']}")
    print(f"ROTATION : {post['rotation_info']['position']}")
    print(f"PHOTO    : {post['photo_path'] or 'None (text-only post)'}")
    print(f"{'='*55}")
    print("\nGENERATED POST:")
    print("-"*55)
    print(post["summary"])
    print("-"*55)
    print(f"\nCTA: {post['call_to_action']['action_type']} → {post['call_to_action']['url']}\n")
