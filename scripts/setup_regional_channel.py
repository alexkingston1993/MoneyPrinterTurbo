"""
Quick OAuth authentication helper for Regional YouTube Channels (Hindi & Tamil).

Usage:
    python scripts/setup_regional_channel.py --lang hi   # For The Compounder Hindi
    python scripts/setup_regional_channel.py --lang ta   # For The Compounder Tamil
"""

import argparse
import base64
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.youtube_uploader import get_uploader, _token_path


def main():
    parser = argparse.ArgumentParser(description="Authorize a regional YouTube channel.")
    parser.add_argument(
        "--lang",
        choices=["hi", "ta", "en"],
        required=True,
        help="Language code: 'hi' (Hindi) or 'ta' (Tamil)",
    )
    args = parser.parse_args()
    lang = args.lang

    channel_names = {
        "hi": "The Compounder Hindi",
        "ta": "The Compounder Tamil",
        "en": "The Compounder (English)",
    }

    print(f"\n========================================================")
    print(f"  Authorizing Channel: {channel_names.get(lang, lang)} ({lang})")
    print(f"========================================================\n")
    print(f"1. A browser window or console URL will prompt you to log into Google.")
    print(f"2. Select your Google account and choose your '{channel_names.get(lang, lang)}' Brand Account.")
    print(f"3. Grant YouTube upload permissions.\n")

    uploader = get_uploader()
    success = uploader.auth_setup(lang)

    if success:
        token_file = _token_path(lang)
        print(f"\n✓ Successfully authorized {channel_names.get(lang, lang)}!")
        print(f"✓ Token saved locally to: {token_file}\n")

        # Generate base64 string for GitHub Actions secret
        with open(token_file, "rb") as f:
            b64_token = base64.b64encode(f.read()).decode("utf-8")

        secret_name = f"YOUTUBE_TOKEN_{lang.upper()}"
        print(f"--- GITHUB ACTIONS CLOUD SECRET SETUP ---")
        print(f"Secret Name: {secret_name}")
        print(f"Secret Value (copy and paste into GitHub repo Settings -> Secrets):\n")
        print(b64_token)
        print(f"\n-----------------------------------------\n")
    else:
        print(f"\n❌ Authorization failed. Please check client secrets and try again.")


if __name__ == "__main__":
    main()
