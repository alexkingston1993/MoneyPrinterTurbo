"""
Automatic Colab launcher — uses Playwright to start Colab, run the GPU worker
notebook, and capture the ngrok tunnel URL.

Opens a fresh Chrome window (separate from your normal browser) and guides you
to sign into Google if needed. Once signed in, it fully automates:

  1. Opening colab.research.google.com
  2. Uploading the GPU worker notebook (with your ngrok token injected)
  3. Connecting to a GPU runtime
  4. Running all cells
  5. Capturing the ngrok tunnel URL
  6. Keeping the session alive with periodic pings

Usage:
    from app.services.colab_launcher import launch_colab
    url = launch_colab(timeout=600)
"""

import json
import os
import re
import sys
import time
import threading

NOTEBOOK_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "docs", "colab_gpu_worker.ipynb",
)


def _inject_into_notebook(token: str) -> str:
    """Inject NGROK_AUTH_TOKEN into a temp copy of the notebook."""
    with open(NOTEBOOK_PATH) as f:
        nb = json.load(f)

    for cell in nb.get("cells", []):
        source = cell.get("source", [])
        for i, line in enumerate(source):
            if line.strip().startswith("NGROK_AUTH_TOKEN ="):
                source[i] = f'NGROK_AUTH_TOKEN = "{token}"\n'
                break

    tmp = NOTEBOOK_PATH + ".injected"
    with open(tmp, "w") as f:
        json.dump(nb, f, indent=1)
    return tmp


def _keepalive(url: str, stop_event: threading.Event):
    """Ping Colac health endpoint every 90s so the runtime doesn't go idle."""
    import requests as req
    while not stop_event.is_set():
        try:
            req.get(f"{url}/health", timeout=10)
        except Exception:
            pass
        stop_event.wait(90)


def launch_colab(timeout: int = 600) -> str:
    """
    Launch Google Colab via Playwright, run the GPU worker notebook,
    and return the ngrok tunnel URL.

    Opens a visible Chrome window. If you aren't signed into Google, the window
    will stay on the login page — sign in and the automation continues.

    Args:
        timeout: Max seconds to wait for Colab to produce the ngrok URL.

    Returns:
        The Colab worker base URL (e.g. https://xxxx.ngrok-free.app).

    Raises:
        TimeoutError: Colab did not produce a URL within the timeout.
    """
    ngrok_token = os.environ.get("NGROK_AUTH_TOKEN", "")
    if not ngrok_token:
        print("[colab] ⚠️  NGROK_AUTH_TOKEN not set — ngrok will use free ephemeral")
        print("[colab]    tunnels (limited to 1 hour). Set the env var for unlimited.")

    notebook_path = _inject_into_notebook(ngrok_token) if ngrok_token else NOTEBOOK_PATH

    print("[colab] Opening a fresh Chrome window for Colab automation…")
    print("[colab] If Google sign-in appears, log in and the automation continues.\n")
    sys.stdout.flush()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-features=ChromeWhatsNewUI",
            ],
        )

        page = browser.new_page()

        # ── 1. Check Google sign-in status ──
        page.goto("https://www.google.com", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        # If the "Sign in" button exists, we are NOT signed in
        sign_in_btn = page.locator('a:has-text("Sign in")').first
        account_btn = page.locator('a[href*="myaccount"]').first
        is_signed_in = account_btn.count() > 0 and sign_in_btn.count() == 0
        if is_signed_in:
            print("[colab] ✅ Already signed into Google.")
        else:
            print("[colab] 🔑 Opening Google sign-in page…")
            page.goto(
                "https://accounts.google.com/signin/v2/identifier?continue="
                "https://colab.research.google.com",
                wait_until="domcontentloaded",
            )
            print("[colab]    Please log in in the Chrome window.")
            print("[colab]    Waiting up to 3 minutes…")
            sys.stdout.flush()
            # Wait until we land back on colab.google.com
            try:
                page.wait_for_url(
                    lambda u: "accounts.google.com" not in u
                    and "colab" in u.lower(),
                    timeout=180000,
                )
                page.wait_for_timeout(3000)
                print("[colab] ✅ Signed in. Continuing…")
            except Exception:
                raise RuntimeError(
                    "Google sign-in not completed within 3 minutes."
                )

        # ── 2. Navigate to Colab upload page ──
        # The /notebooks/upload endpoint has a direct file input
        page.goto(
            "https://colab.research.google.com/notebooks/upload",
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(4000)

        # ── 3. Upload the notebook via file input ──
        # Try multiple selector strategies
        print("[colab] Uploading GPU worker notebook…")
        sys.stdout.flush()

        upload_input = None
        strategies = [
            lambda: page.locator("input[type='file']").first,
            lambda: page.locator("input[accept='.ipynb']").first,
            lambda: page.locator('input[accept*="ipynb"]').first,
            lambda: page.evaluate(
                "() => document.querySelector('input[type=file]')"
            ),
        ]

        for strat in strategies:
            try:
                el = strat()
                if el is not None and (hasattr(el, "count") and el.count() > 0):
                    upload_input = el
                    break
                if el is not None and not hasattr(el, "count"):
                    # It's a JSHandle, convert to locator
                    break
            except Exception:
                continue

        if upload_input is None or (
            hasattr(upload_input, "count") and upload_input.count() == 0
        ):
            # Desperate measure: click anywhere to dismiss possible overlay
            page.mouse.click(100, 100)
            page.wait_for_timeout(2000)
            try:
                upload_input = page.locator("input[type='file']").first
                if upload_input.count() == 0:
                    # Inject a file input into the DOM with a known ID
                    page.evaluate(
                        """
                        () => {
                            if (!document.getElementById('_mpt_upload')) {
                                const inp = document.createElement('input');
                                inp.id = '_mpt_upload';
                                inp.type = 'file';
                                inp.accept = '.ipynb';
                                inp.style.display = 'block';
                                inp.style.position = 'fixed';
                                inp.style.top = '0';
                                inp.style.left = '0';
                                inp.style.zIndex = '99999';
                                document.body.appendChild(inp);
                            }
                        }
                        """
                    )
                    page.wait_for_timeout(1000)
                    upload_input = page.locator("#_mpt_upload")
            except Exception:
                pass

        if upload_input is None:
            raise RuntimeError(
                "Could not find Colab file-upload input. "
                "Try manually: File → Upload Notebook in the Colab window."
            )

        upload_input.set_input_files(notebook_path)
        print("[colab] Uploaded. Waiting for the notebook editor to load…")
        page.wait_for_timeout(10000)

        # ── 4. Dismiss any warning dialogs ──
        for btn_label in ("OK", "Run anyway", "Yes"):
            try:
                btn = page.get_by_role("button", name=btn_label).first
                if btn.count() > 0:
                    btn.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass

        # ── 5. Connect to a runtime ──
        connect_btn = page.locator("colab-connect-button").first
        if connect_btn.count() > 0:
            print("[colab] Connecting to GPU runtime…")
            connect_btn.click()
            page.wait_for_timeout(20000)
        else:
            alt = page.get_by_role("button", name="Connect")
            if alt.count() > 0:
                print("[colab] Connecting to GPU runtime…")
                alt.click()
                page.wait_for_timeout(20000)

        # ── 6. Run all cells ──
        import platform as _plat
        if _plat.system() == "Darwin":
            page.keyboard.press("Meta+Shift+F9")
        else:
            page.keyboard.press("Control+F9")

        print(f"[colab] ⏳ Running all cells — waiting up to {timeout}s for URL…")
        sys.stdout.flush()

        # ── 7. Poll cell outputs for the ngrok URL ──
        t0 = time.time()
        url = ""
        last_progress = 0

        while time.time() - t0 < timeout:
            page.wait_for_timeout(2000)

            try:
                outputs = page.locator(
                    ".output_text, .output_stdout, .output_stream, pre"
                )
                oc = outputs.count()
                for i in range(oc):
                    text = outputs.nth(i).text_content() or ""
                    m = re.search(r"COLAB WORKER URL:\s*(https?://\S+)", text)
                    if m:
                        url = m.group(1).strip().rstrip("/")
                        break
                    m = re.search(
                        r"(https://[a-zA-Z0-9\-]+\.ngrok-[a-z]+\.\S+)", text
                    )
                    if m:
                        raw = m.group(1).strip().rstrip(". ")
                        if "ngrok" in raw:
                            url = raw.rstrip("/")
                            break
                if url:
                    print(f"\n[colab] ✅ Worker URL: {url}")
                    break

                now = time.time()
                if now - last_progress > 30:
                    print(f"[colab]   Still running… ({now-t0:.0f}s)")
                    last_progress = now
            except Exception:
                pass

        if not url:
            try:
                errs = page.locator(".output_err, .traceback").text_content()
                if errs:
                    print(f"[colab] ❌ Notebook errors:\n{errs[:500]}")
            except Exception:
                pass
            raise TimeoutError(
                f"Colab did not produce a URL within {timeout}s. "
                "Check the Colab browser window for errors."
            )

        # ── 8. Save URL to file ──
        from app.services.colab_worker import COLAB_URL_FILE

        os.makedirs(os.path.dirname(COLAB_URL_FILE), exist_ok=True)
        with open(COLAB_URL_FILE, "w") as f:
            f.write(url + "\n")
        print(f"[colab] URL saved to {COLAB_URL_FILE}")

        # ── 9. Start keepalive daemon & leave browser open ──
        stop_ev = threading.Event()
        ka = threading.Thread(target=_keepalive, args=(url, stop_ev), daemon=True)
        ka.start()
        print("[colab] Keepalive thread running (pings every 90s).")
        print("[colab] The browser window stays open to prevent Colab idle timeout.")
        print("[colab] Close it when you're done.\n")

        # Clean up temp notebook
        if notebook_path != NOTEBOOK_PATH and os.path.exists(notebook_path):
            try:
                os.remove(notebook_path)
            except Exception:
                pass

        return url
