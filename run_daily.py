"""
EVERSKIN GBP AUTO-POST — DAILY RUNNER
This is the script Windows Task Scheduler calls every day.
It generates today's post and publishes it to Google Business Profile.
"""

import os
import sys
import datetime
from colorama import init, Fore, Style

# Force UTF-8 output on Windows (handles emojis in posts)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

init(autoreset=True)

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR  = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ── File Logging (for Task Scheduler — no terminal) ───────────────────────────
import logging

log_filename = os.path.join(
    LOG_DIR,
    f"gbp_post_{datetime.date.today().isoformat()}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    logger.info("=" * 55)
    logger.info("  EVERSKIN GBP AUTO-POST — DAILY RUN")
    logger.info(f"  Date: {datetime.date.today().strftime('%A, %d %B %Y')}")
    logger.info("=" * 55)

    # ── Step 1: Generate post ─────────────────────────────────────────────────
    try:
        sys.path.insert(0, BASE_DIR)
        from generate_post import get_next_post
        from post_gbp import post_to_gbp, log_result

        post = get_next_post()
        logger.info(f"Service  : {post['service_name']}")
        logger.info(f"Category : {post['category']}")
        logger.info(f"Rotation : {post['rotation_info']['position']}")
        logger.info(f"Preview  : {post['summary'][:100]}...")

    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        sys.exit(1)

    # ── Step 2: Publish to GBP ────────────────────────────────────────────────
    try:
        response = post_to_gbp(post)
        log_result(post, api_response=response)
        logger.info("Post published successfully.")
        logger.info(f"GBP Post Name: {response.get('name', 'N/A')}")

    except Exception as e:
        logger.error(f"GBP posting failed: {e}")
        log_result(post, error=str(e))
        sys.exit(1)

    logger.info("=" * 55)
    logger.info("  DONE. See logs folder for history.")
    logger.info("=" * 55)

if __name__ == "__main__":
    main()
