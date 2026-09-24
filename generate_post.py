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

    # GFC/PRP are injectable, doctor-administered treatments — Priyanka isn't named for these
    doctor_only = any(kw in service["name"].upper() for kw in ("GFC", "PRP"))

    if doctor_only:
        practitioner_details = f"- Doctor: {clinic['doctor']} — expert cosmetologist and trichologist"
        practitioner_instruction = (
            f'4. Name "{clinic["doctor"]}" once, described as an expert cosmetologist and trichologist. '
            f'Do NOT mention "{clinic["co_owner"]}" in this post — this treatment is administered by the doctor only'
        )
    else:
        practitioner_details = (
            f"- Doctor: {clinic['doctor']} — expert cosmetologist and trichologist\n"
            f"- Co-owner: {clinic['co_owner']} — expert cosmetologist and trichologist"
        )
        practitioner_instruction = (
            f'4. Name "{clinic["doctor"]}" once and "{clinic["co_owner"]}" once, each described as an expert '
            f'cosmetologist and trichologist — naturally, they don\'t need to be in the same sentence'
        )

    prompt = f"""You are writing a Google Business Profile (GBP) update post for {clinic['name']}, a single-location aesthetic skin and hair clinic in Pimple Saudagar, Pune, India.

CLINIC DETAILS
- Name: {clinic['name']}
{practitioner_details}
- Location: {clinic['location']} (one clinic only, no branches)
- Nearby areas clients travel from: {areas_served}

TODAY'S SERVICE
- Service (primary keyword): {service['name']}
- Category: {service['category']}
- Concerns it addresses (secondary keywords): {service.get('treats') or 'not specified'}
- Related treatments also offered: {service.get('related_treatments') or 'none — do not mention any'}

CONTEXT
- Day: {day_name}
- Month: {month_name}
- Season: {season}

CONTENT
1. Write one post about this service only
2. The first line is the hook (a question, relatable problem or bold statement) and stays under about 90 characters, because Google shows only the first line or two before "More". Work a concern from the list into the hook where it fits naturally
3. Explain what the service is, who it's good for, and how it helps — give 3–4 genuine benefits in plain language, with enough substance that it reads like a short, useful explainer rather than an ad
{practitioner_instruction}
5. Add a seasonal or day-related angle only if it is genuinely relevant to this service
6. Close with a soft invitation: appointments can be made by calling (the "Call Now" button is attached separately) or by booking online at {clinic['website']} — mention the website once, as plain text, not as a clickable-looking link

SEO (maximum relevance, zero stuffing — every keyword must sit inside a natural sentence, and never as a list)
- Use the primary keyword "{service['name']}" within the first two sentences, and 3–4 times in total across the post — never more, and never back-to-back
- Use the exact phrase "{service['name']} in Pimple Saudagar, Pune" (or a close natural variant) exactly once. Service + location together matches how people actually search
- Mention "{clinic['name']}" once
- Weave in all of the concerns from the secondary keyword list that genuinely fit, each at most once, phrased the way a patient would describe them — don't skip ones that fit just to keep the post short
- Mention up to two related treatments from the list, only where they add real value (e.g. "often paired with X for Y")
- Add one sentence saying the clinic is easy to reach from up to three of the nearby areas (e.g. "Easily accessible from Wakad, Rahatani and Pimple Gurav"). Never write "Also serving: X | Y | Z" or anything implying branches there
- Never list keywords separated by commas or pipes, never repeat the same phrase twice, and never add a keyword that doesn't serve the reader — length comes from genuinely useful detail, not from stuffing

ACCURACY AND COMPLIANCE
- Do not promise or guarantee results. Avoid "permanent", "painless", "guaranteed", "100%", "best clinic" and "world-class"
- Do not invent statistics, session counts, prices, offers, equipment brands or approvals (e.g. "FDA-approved")
- NEVER use the word "dermatologist" or "pharmacist"
- Do not include a phone number in the post text — Google's post policy disallows phone numbers in the body, and the Call Now button already handles this

FORMAT
- Use as much of the space as the content genuinely supports: aim for 260–320 words, and 1,350–1,480 characters total. Google's hard limit is 1,500 characters — never exceed it, and never pad with filler just to hit the count
- Short paragraphs separated by line breaks
- 3–4 emojis total, spread out, not clustered
- No hashtags, no ALL CAPS
- Use British/Indian English spelling (e.g. "personalised")
- The post must feel fresh and informative, not like a template or an ad

Output only the post text."""

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
            "action_type": "CALL"
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
