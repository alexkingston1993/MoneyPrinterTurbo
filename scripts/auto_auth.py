#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

ROOT = Path(__file__).resolve().parent.parent
TOKEN_DIR = ROOT / "data" / "youtube_tokens"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

def authorize(secret_path: Path, slot_num: int):
    if not secret_path.exists():
        print(f"Error: {secret_path} does not exist.")
        sys.exit(1)

    print(f"Loading config from {secret_path.name}...")
    client_config = json.loads(secret_path.read_text(encoding="utf-8"))
    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    
    print(f"Starting local server and launching browser for Slot {slot_num}...")
    creds = flow.run_local_server(port=0, prompt="consent", open_browser=True)
    
    # Save pickle
    import pickle
    pickle_path = TOKEN_DIR / "youtube_token_en.pickle"
    with open(pickle_path, "wb") as f:
        pickle.dump(creds, f)
    print(f"✓ Saved pickle to: {pickle_path}")

    # Save to pool cache
    pool_cache = TOKEN_DIR / "oauth_pool.json"
    cache = []
    if pool_cache.exists():
        try:
            cache = json.loads(pool_cache.read_text())
        except Exception:
            cache = []

    slot_data = {
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token,
        "_src": f"slot_{slot_num}",
    }
    cache = [s for s in cache if s.get("client_id") != slot_data["client_id"]]
    cache.append(slot_data)
    pool_cache.write_text(json.dumps(cache, indent=2))
    print(f"✓ Saved slot {slot_num} to {pool_cache} (total: {len(cache)} slots)")

if __name__ == "__main__":
    slot = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    if slot == 1:
        path = TOKEN_DIR / "client_secrets_en.json"
    else:
        path = TOKEN_DIR / f"client_secrets_slot_{slot}.json"
    authorize(path, slot)
