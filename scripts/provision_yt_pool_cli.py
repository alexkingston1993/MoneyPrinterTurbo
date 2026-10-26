#!/usr/bin/env python3
"""
Provision & sync the Multi-Project YouTube OAuth Quota Rotator pool, 100% via CLI.

Usage:
  python3 scripts/provision_yt_pool_cli.py --audit
      Scan disk/env for every OAuth slot (pickles, client_secret*.json,
      YOUTUBE_TOKEN_*_BASE64, numbered YT_* vars) and print a table.

  python3 scripts/provision_yt_pool_cli.py --verify
      Live-test every slot's refresh_token against oauth2.googleapis.com/token.

  python3 scripts/provision_yt_pool_cli.py --bundle
      Build YT_OAUTH_POOL_JSON (verified slots only) + numbered env maps and
      cache them at data/youtube_tokens/oauth_pool.json.

  python3 scripts/provision_yt_pool_cli.py --sync [--repo OWNER/NAME] [--profile the-bull-print]
      Push YT_OAUTH_POOL_JSON + YT_CLIENT_ID_N / YT_CLIENT_SECRET_N /
      YT_REFRESH_TOKEN_N to GitHub Actions Secrets (gh secret set) and
      Vercel Production (vercel env add, via npx vercel).

  python3 scripts/provision_yt_pool_cli.py --bootstrap {en,ta,hi}
      Run InstalledAppFlow.run_local_server() against data/youtube_tokens/
      client_secrets_{lang}.json (one browser consent click), mint a fresh
      refresh_token, and append the new slot to the pool.

Combine freely:  --verify --bundle --sync
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pickle
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN_DIR = ROOT / "data" / "youtube_tokens"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
TOKEN_URL = "https://oauth2.googleapis.com/token"

# gitignore'd canonical local pool cache (never commit secret values)
POOL_CACHE = TOKEN_DIR / "oauth_pool.json"


# ---------------------------------------------------------------- discount helpers
def load_client_secret_json(path: Path) -> dict:
    j = json.loads(path.read_text(encoding="utf-8"))
    for k in ("installed", "web"):
        if k in j:
            d = j[k]
            return {
                "client_id": d.get("client_id", ""),
                "client_secret": d.get("client_secret", ""),
                "redirect_uris": d.get("redirect_uris", []),
            }
    return {}


def creds_from_pickle_bytes(raw: bytes):
    try:
        obj = pickle.loads(raw)
    except Exception:
        return None
    if isinstance(obj, dict) and "credentials" in obj:
        obj = obj["credentials"]
    if obj is None or isinstance(obj, (str, bytes)):
        return None
    g = lambda attr, dflt="": getattr(obj, attr, None) or (obj.get(attr, dflt) if isinstance(obj, dict) else dflt)
    return {"client_id": g("client_id"), "client_secret": g("client_secret"), "refresh_token": g("refresh_token")}


def env_slot(suffix: str) -> dict | None:
    candidates = [f"YT_CLIENT_ID{suffix}", f"YT_CLIENT_ID_{suffix}".replace("__", "_")]
    cid = next((os.getenv(c) for c in candidates if os.getenv(c)), None)
    cse = next((os.getenv(c) for c in [("YT_CLIENT_SECRET" + suffix), ("YT_CLIENT_SECRET_" + suffix.lstrip("_"))] if os.getenv(c)), None)
    rt = next((os.getenv(c) for c in [("YT_REFRESH_TOKEN" + suffix), ("YT_REFRESH_TOKEN_" + suffix.lstrip("_"))] if os.getenv(c)), None)
    if cid and cse and rt:
        return {"client_id": cid, "client_secret": cse, "refresh_token": rt}
    return None


def dedupe(slots: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in slots:
        key = s.get("client_id") or (s.get("refresh_token") or "")[:20]
        if key and key not in seen and s.get("refresh_token"):
            seen.add(key)
            out.append(s)
    return out


# ---------------------------------------------------------------- collection
def collect_slots(include_pickle_junk_failures: bool = False) -> tuple[list[dict], list[str]]:
    """Return (slot list, human notes). Secrets stay in memory / cached file only."""
    notes: list[str] = []
    slots: list[dict] = []

    secret_files = sorted(ROOT.glob("client_secret*.json")) + sorted(TOKEN_DIR.glob("client_secrets*.json"))
    secrets_by_id: dict[str, Path] = {}
    for p in secret_files:
        try:
            info = load_client_secret_json(p)
            if info.get("client_id") and info.get("client_id") not in secrets_by_id:
                secrets_by_id[info["client_id"]] = p
        except Exception as e:
            notes.append(f"unreadable secret json {p.name}: {e}")

    # 1) raw pickles on disk
    for p in sorted(TOKEN_DIR.glob("youtube_token_*.pickle")):
        creds = creds_from_pickle_bytes(p.read_bytes())
        if not creds:
            notes.append((f"unpicklable {p.name}"))
            continue
        if not creds.get("client_secret") and creds.get("client_id") in secrets_by_id:
            creds["client_secret"] = load_client_secret_json(secrets_by_id[creds["client_id"]])["client_secret"]
            notes.append(f"paired {p.name} ↦ {secrets_by_id[creds['client_id']].name}")
        creds["_src"] = f"pickle:{p.name}"
        slots.append(creds)

    # 2) base64 pickle envs (local shell or CI export)
    for name in sorted(os.environ):
        if name.startswith("YOUTUBE_TOKEN_") and name.endswith("_BASE64"):
            try:
                creds = creds_from_pickle_bytes(base64.b64decode(os.environ[name]))
                if creds and creds.get("refresh_token"):
                    creds["_src"] = f"env:{name}"
                    slots.append(creds)
            except Exception as e:
                notes.append(f"env {name}: decode failed ({e})")

    # 3) numbered + raw YT_* env vars
    for suffix in ("", "1", "2", "3", "4", "5", "6"):
        s = env_slot(suffix)
        if s:
            s["_src"] = "env:YT_CLIENT_ID" + (suffix or "")
            slots.append(s)

        # 4) pool cache extended by --bootstrap runs
    if POOL_CACHE.exists():
        try:
            for s in json.loads(POOL_CACHE.read_text()):
                if s.get("refresh_token"):
                    slots.append({**s, "_src": f"cache:{POOL_CACHE.name}"})
        except Exception as e:
            notes.append(f"pool cache corrupt: {e}")

    filled = dedupe(slots)
    for f in filled:
        if not f.get("client_secret") and f.get("client_id") in secrets_by_id:
            f["client_secret"] = load_client_secret_json(secrets_by_id[f["client_id"]])["client_secret"]
            notes.append(f"paired {f.get('_src')} ↦ {secrets_by_id[f['client_id']].name}")
    return filled, notes


# ---------------------------------------------------------------- verification
def verify_refresh_token(slot: dict, timeout: int = 20) -> tuple[bool, str]:
    if not slot.get("refresh_token"):
        return False, "no refresh_token"
    if not slot.get("client_secret"):
        return False, "no client_secret"
    body = urllib.parse.urlencode(
        {
            "client_id": slot["client_id"],
            "client_secret": slot["client_secret"],
            "refresh_token": slot["refresh_token"],
            "grant_type": "refresh_token",
        }
    ).encode()
    req = urllib.request.Request(TOKEN_URL, body, {"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
            return bool(data.get("access_token")), "mints access_token"
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} (invalid_grant/revoked)"
    except Exception as e:
        return False, f"{type(e).__name__}"


# ---------------------------------------------------------------- sync targets
def sync_gh(pool_json: str, numbered: dict, repo: str) -> bool:
    print(f"\n→ GitHub Actions secrets ({repo})")
    rc = True
    try:
        subprocess.run(["gh", "secret", "set", "YT_OAUTH_POOL_JSON", f"-R={repo}", "-b", pool_json], check=True)
        print("  ✓ gh secret set YT_OAUTH_POOL_JSON")
    except Exception as e:
        print(f"  ✗ YT_OAUTH_POOL_JSON: {e}")
        rc = False
    for name, value in numbered.items():
        try:
            subprocess.run(["gh", "secret", "set", name, f"-R={repo}", "-b", value], check=True)
            print(f"  ✓ gh secret set {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            rc = False
    return rc


def sync_vercel(pool_json: str, numbered: dict, profile: str) -> bool:
    print(f"\n→ Vercel Production env ({profile})")
    rc = True
    cmd = ["npx", "--yes", "vercel@latest"]

    def upsert(name: str, value: str) -> bool:
        try:
            subprocess.run(cmd + ["env", "rm", name, "production", "yes"], check=True, capture_output=True)
        except Exception:
            pass
        try:
            subprocess.run(cmd + ["env", "add", name, "production"], input=f"{value}\n", check=True, capture_output=True, text=True)
            print(f"  ✓ vercel env add {name}")
            return True
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            return False

    rc &= upsert("YT_OAUTH_POOL_JSON", pool_json)
    for name, value in numbered.items():
        rc &= upsert(name, value)
    return rc


# ---------------------------------------------------------------- bootstrap
def bootstrap_slot(lang_or_slot: str | int) -> dict | None:
    """Interactive consent (required by Google for NEW refresh tokens)."""
    target_str = str(lang_or_slot)
    candidates = [
        TOKEN_DIR / f"client_secrets_slot_{target_str}.json",
        TOKEN_DIR / f"client_secrets_{target_str}.json",
        TOKEN_DIR / f"client_secret_{target_str}.json",
    ]
    secret_path = None
    for c in candidates:
        if c.exists():
            secret_path = c
            break

    if not secret_path or not secret_path.exists():
        fallbacks = sorted(TOKEN_DIR.glob("client_secrets*.json")) + sorted(ROOT.glob("client_secret*.json"))
        if fallbacks:
            secret_path = fallbacks[0]
        else:
            print(f"✗ no client_secret config for '{lang_or_slot}'")
            return None

    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_config(
        json.loads(secret_path.read_text(encoding="utf-8")), scopes=SCOPES
    )
    print(f"Opening browser consent for slot '{lang_or_slot}' (config {secret_path.name})…")
    creds = flow.run_local_server(port=0, prompt="consent")
    return {
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "refresh_token": creds.refresh_token,
        "_src": f"bootstrap:slot_{target_str}",
    }


# ---------------------------------------------------------------- main
def main() -> int:
    import shutil
    ap = argparse.ArgumentParser(description="Provision the YT OAuth quota-rotation pool.")
    ap.add_argument("--audit", action="store_true", help="Scan disk/env and print table")
    ap.add_argument("--verify", action="store_true", help="Live-test refresh tokens")
    ap.add_argument("--bundle", action="store_true", help="Build YT_OAUTH_POOL_JSON + numbered map")
    ap.add_argument("--sync", action="store_true", help="gh secret set + vercel env add")
    ap.add_argument("--add-client-secret", metavar="PATH", help="Register a downloaded client_secret.json as a slot")
    ap.add_argument("--slot", type=int, default=0, help="Slot number (e.g. 2 or 3)")
    ap.add_argument("--authorize", action="store_true", help="Authorize a slot via interactive browser consent")
    ap.add_argument("--bootstrap", metavar="LANG", help="en|ta|hi|slot number — interactive consent for a NEW slot")
    ap.add_argument("--repo", default="alexkingston1993/MoneyPrinterTurbo")
    ap.add_argument("--profile", default="the-bull-print")
    args = ap.parse_args()

    if args.add_client_secret:
        src = Path(args.add_client_secret).expanduser().resolve()
        if not src.exists():
            print(f"✗ File not found: {src}")
            return 1
        slot_num = args.slot or 2
        dest = TOKEN_DIR / f"client_secrets_slot_{slot_num}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        info = load_client_secret_json(dest)
        print(f"✓ Registered Slot {slot_num} client secret at: {dest}")
        print(f"  Client ID: …{str(info.get('client_id'))[-25:]}")
        if not args.authorize:
            print(f"\nNext step: run browser authorization to mint refresh token:")
            print(f"  python3 scripts/provision_yt_pool_cli.py --authorize --slot {slot_num}")
            return 0

    if args.authorize or args.bootstrap:
        target_slot = args.slot or args.bootstrap or 2
        cache = json.loads(POOL_CACHE.read_text()) if POOL_CACHE.exists() else []
        slot_data = bootstrap_slot(target_slot)
        if slot_data:
            cache = [s for s in cache if s.get("client_id") != slot_data.get("client_id")]
            cache.append(slot_data)
            POOL_CACHE.parent.mkdir(parents=True, exist_ok=True)
            POOL_CACHE.write_text(json.dumps(cache, indent=1))
            print(f"✓ Slot '{target_slot}' authorized & saved to {POOL_CACHE} ({len(cache)} slot(s) total)")
        return 0


    if not any([args.audit, args.verify, args.bundle, args.sync]):
        args.audit = True

    slots, notes = collect_slots()

    good: list[dict] = []
    if args.audit or args.verify:
        print("\n=== OAuth slot audit ===")
        for note in notes:
            print(f"  • {note}")
        for i, s in enumerate(slots, 1):
            status = ""
            if args.verify:
                ok, msg = verify_refresh_token(s)
                status = f"  {'✓' if ok else '✗'} {msg}"
                if ok:
                    good.append(s)
            print(f"  Slot {i} [{s.get('_src', 'unknown')}] id…{str(s.get('client_id'))[-14:]} "
                  f"secret={'Y' if s.get('client_secret') else 'N'} "
                  f"refresh={'Y' if s.get('refresh_token') else 'N'}{status}")
        if not slots:
            print("  (no slots found)")

    if args.bundle or args.sync:
        if not good:
            good = json.loads(POOL_CACHE.read_text()) if POOL_CACHE.exists() else []
            if good:
                print(f"\n(using {len(good)} previously verified slot(s) from {POOL_CACHE})")
            else:
                print("\n✗ nothing to bundle/sync: zero verified slots (run with --verify)")
                return 1

        verified = [s for s in good if verify_refresh_token(s)[0]]
        pool = [
            {"client_id": s["client_id"], "client_secret": s["client_secret"], "refresh_token": s["refresh_token"]}
            for s in verified
        ]
        pool_json = json.dumps(pool, separators=(",", ":"))
        numbered = {}
        for i, s in enumerate(verified):
            numbered[f"YT_CLIENT_ID_{i + 1}"] = s["client_id"]
            numbered[f"YT_CLIENT_SECRET_{i + 1}"] = s["client_secret"]
            numbered[f"YT_REFRESH_TOKEN_{i + 1}"] = s["refresh_token"]

        POOL_CACHE.parent.mkdir(parents=True, exist_ok=True)
        POOL_CACHE.write_text(json.dumps(verified, indent=1))
        print(f"\n🛠  bundled {len(verified)} verified slot(s) → {POOL_CACHE}")

        if args.sync:
            ok = sync_gh(pool_json, numbered, args.repo)
            ok &= sync_vercel(pool_json, numbered, args.profile)
            print("\n✔ sync complete" if ok else "\n✔ sync finished (some targets failed — see above)")
            return 0 if ok else 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
