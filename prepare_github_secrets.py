"""
EVERSKIN — GITHUB SECRETS HELPER
Run this locally ONCE after setup.py to get the values
you need to paste into GitHub repository secrets.
"""

import os
import json
from colorama import init, Fore, Style
init(autoreset=True)

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE  = os.path.join(BASE_DIR, "credentials", "token.json")
CONFIG_FILE = os.path.join(BASE_DIR, "data", "gbp_config.json")
API_KEYS    = os.path.join(BASE_DIR, "credentials", "api_keys.json")

def print_secret(name, value):
    print(f"\n{Fore.CYAN}{'─'*55}")
    print(f"Secret Name  : {Fore.YELLOW}{name}")
    print(f"{Fore.CYAN}Secret Value :{Style.RESET_ALL}")
    print(value)
    print(f"{Fore.CYAN}{'─'*55}{Style.RESET_ALL}")

print(f"\n{Fore.MAGENTA}{'='*55}")
print("   EVERSKIN — GitHub Secrets Preparation")
print(f"{'='*55}{Style.RESET_ALL}")
print("\nCopy each value below into your GitHub repo secrets.")
print("Go to: GitHub Repo → Settings → Secrets → Actions → New secret\n")

# ── Secret 1: GBP Token ───────────────────────────────────────────────────────
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "r") as f:
        token_content = f.read().strip()
    print_secret("GBP_TOKEN_JSON", token_content)
else:
    print(f"{Fore.RED}❌ token.json not found. Run setup.py first.{Style.RESET_ALL}")

# ── Secret 2: GBP Config ─────────────────────────────────────────────────────
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config_content = f.read().strip()
    print_secret("GBP_CONFIG_JSON", config_content)
else:
    print(f"{Fore.RED}❌ gbp_config.json not found. Run setup.py first.{Style.RESET_ALL}")

# ── Secret 3: Anthropic API Key ──────────────────────────────────────────────
if os.path.exists(API_KEYS):
    with open(API_KEYS, "r") as f:
        keys = json.load(f)
    api_key = keys.get("anthropic_api_key", "")
    if api_key and api_key != "sk-ant-YOUR_KEY_HERE":
        print_secret("ANTHROPIC_API_KEY", api_key)
    else:
        print(f"{Fore.RED}❌ Anthropic API key not set in credentials/api_keys.json{Style.RESET_ALL}")
else:
    print(f"{Fore.RED}❌ api_keys.json not found.{Style.RESET_ALL}")

print(f"\n{Fore.GREEN}{'='*55}")
print("  Paste all 3 secrets into GitHub, then push your code.")
print(f"{'='*55}{Style.RESET_ALL}\n")
