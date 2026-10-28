#!/usr/bin/env python3
import asyncio
import json
import os
import pickle
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent
TOKEN_DIR = ROOT / "data" / "youtube_tokens"
SLOT_2_SECRETS = TOKEN_DIR / "client_secrets_slot_2.json"
OAUTH_POOL_FILE = TOKEN_DIR / "oauth_pool.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

auth_response_url = None

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_response_url
        auth_response_url = f"http://localhost:{self.server.server_port}{self.path}"
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body><h1>Authentication successful!</h1><p>You can close this tab now.</p></body></html>")

    def log_message(self, format, *args):
        pass  # Quiet logs

def main():
    global auth_response_url
    
    # 1. Bind ephemeral port
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    
    server = HTTPServer(("127.0.0.1", port), OAuthCallbackHandler)
    server_thread = Thread(target=server.handle_request, daemon=True)
    server_thread.start()
    
    redirect_uri = f"http://localhost:{port}/"
    print(f"[*] Started local callback server on {redirect_uri}")

    # 2. Setup Flow
    client_config = json.loads(SLOT_2_SECRETS.read_text(encoding="utf-8"))
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    print(f"[*] Auth URL generated: {auth_url[:80]}...")

    # 3. Playwright browser navigation
    async def run_playwright():
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]
            page = await context.new_page()
            
            print("[*] Navigating to OAuth Consent URL...")
            await page.goto(auth_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            await page.screenshot(path="output/songx_oauth_1.png")
            print(f"[*] Step 1 URL: {page.url}")

            # Check if account selection appears
            account_btn = page.locator("text=alexytcreative@gmail.com").first
            if await account_btn.count() > 0:
                print("[*] Clicking alexytcreative@gmail.com...")
                await account_btn.click()
                await page.wait_for_timeout(3000)
                await page.screenshot(path="output/songx_oauth_2.png")
                print(f"[*] Step 2 URL: {page.url}")

            # Check for unverified app warning ("Advanced" -> "Go to ... (unsafe)")
            adv_btn = page.locator("a:has-text('Advanced'), button:has-text('Advanced'), [aria-label*='Advanced']")
            if await adv_btn.count() > 0:
                print("[*] Clicking Advanced...")
                await adv_btn.first.click()
                await page.wait_for_timeout(1500)
                await page.screenshot(path="output/songx_oauth_2_adv.png")
                
                unsafe_link = page.locator("a:has-text('Go to'), a:has-text('unsafe')")
                if await unsafe_link.count() > 0:
                    print("[*] Clicking Go to project (unsafe)...")
                    await unsafe_link.first.click()
                    await page.wait_for_timeout(3000)
                    await page.screenshot(path="output/songx_oauth_3.png")

            # Check for scope checkboxes
            checkboxes = page.locator("input[type='checkbox']")
            cb_count = await checkboxes.count()
            if cb_count > 0:
                print(f"[*] Found {cb_count} checkboxes. Selecting all...")
                for i in range(cb_count):
                    cb = checkboxes.nth(i)
                    if not await cb.is_checked():
                        await cb.check()
                await page.wait_for_timeout(1000)
                await page.screenshot(path="output/songx_oauth_4_checked.png")

            # Click Continue or Allow
            continue_btn = page.locator("button:has-text('Continue'), button:has-text('Allow'), div[role='button']:has-text('Continue'), div[role='button']:has-text('Allow')")
            if await continue_btn.count() > 0:
                print("[*] Clicking Continue / Allow button...")
                await continue_btn.last.click()
                await page.wait_for_timeout(5000)
                await page.screenshot(path="output/songx_oauth_5_done.png")
                print(f"[*] Step 5 URL: {page.url}")

            await page.close()

    asyncio.run(run_playwright())

    # Wait for callback server to capture response
    server_thread.join(timeout=10)
    if not auth_response_url:
        print("[!] Error: Did not receive callback at local server!")
        return

    print(f"[*] Received OAuth callback: {auth_response_url[:60]}...")
    
    # 4. Exchange code for credentials
    # OAuthLib requires https URL for token exchange
    fetch_url = auth_response_url.replace("http://", "https://")
    flow.fetch_token(authorization_response=fetch_url)
    creds = flow.credentials
    print("[✓] Successfully fetched credentials!")
    print(f"    Client ID: {creds.client_id}")
    print(f"    Refresh Token: {creds.refresh_token[:15]}... (length: {len(creds.refresh_token)})")

    # 5. Verify against YouTube API
    yt = build("youtube", "v3", credentials=creds)
    ch_resp = yt.channels().list(part="snippet", mine=True).execute()
    for item in ch_resp.get("items", []):
        print(f"[✓] Verified YouTube Channel: {item['snippet']['title']} (ID: {item['id']})")

    # 6. Save pickle
    pickle_path = TOKEN_DIR / "youtube_token_slot_2.pickle"
    with open(pickle_path, "wb") as f:
        pickle.dump(creds, f)
    print(f"[✓] Saved pickle to {pickle_path}")

    # 7. Update oauth_pool.json
    pool = []
    if OAUTH_POOL_FILE.exists():
        try:
            pool = json.loads(OAUTH_POOL_FILE.read_text(encoding="utf-8"))
        except Exception:
            pool = []

    slot_2_entry = {
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token,
        "_src": "slot_2:songx-62245"
    }

    # Remove existing entry with same client_id if any, then append
    pool = [s for s in pool if s.get("client_id") != slot_2_entry["client_id"]]
    pool.append(slot_2_entry)

    OAUTH_POOL_FILE.write_text(json.dumps(pool, indent=2), encoding="utf-8")
    print(f"[✓] Updated {OAUTH_POOL_FILE} (Total Active Slots: {len(pool)})")

if __name__ == "__main__":
    main()
