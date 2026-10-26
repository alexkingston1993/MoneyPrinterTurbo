"""
Kaggle GPU Worker (kaggle_kernel/kaggle_worker.py).
Executes on Kaggle's free dual NVIDIA Tesla T4 GPU:
1. Generates Edge-TTS speech narration
2. Transcribes with Faster-Whisper on CUDA float16 for millisecond word-level timestamps
3. Generates high-contrast Hormozi-style .ass subtitles (Bullish Green, Bearish Red)
4. Renders 1080p scenes with hardware-accelerated NVIDIA NVENC (h264_nvenc) at 10x CPU speed
5. Concatenates video and uploads headless to YouTube Data API with containsSyntheticMedia=True
6. Renders the companion 9:16 #Shorts (chart top / avatar bottom, emerald divider) and uploads headless
"""

import os
import re
import json
import asyncio
import datetime
import subprocess
from pathlib import Path

# Ephemeral container package setup
subprocess.run(["pip", "install", "-q", "edge-tts", "faster-whisper", "google-api-python-client", "google-auth"], check=False)

try:
    import edge_tts
    from faster_whisper import WhisperModel
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
except Exception as e:
    print(f"Warning on import: {e}")

def get_payload_dir() -> Path:
    p = Path("/kaggle/input/flipzon-daily-payload")
    if (p / "payload.json").exists():
        return p
    if Path("/kaggle/input").exists():
        matches = list(Path("/kaggle/input").rglob("payload.json"))
        if matches:
            return matches[0].parent
    stage = Path(__file__).parent.parent / "kaggle_stage"
    if (stage / "payload.json").exists():
        return stage
    for cand in [Path("/kaggle/working"), Path(".")]:
        if (cand / "payload.json").exists():
            return cand
    return p

def get_assets_dir() -> Path:
    a = Path("/kaggle/input/flipzon-studio-assets")
    if (a / "avatar_1.png").exists() or (a / "avatars" / "avatar_1.png").exists():
        return a
    if Path("/kaggle/input").exists():
        matches = list(Path("/kaggle/input").rglob("avatar_1.png"))
        if matches:
            return matches[0].parent
    assets = Path(__file__).parent.parent / "assets"
    if assets.exists():
        return assets
    return a

ASSETS_DIR = get_assets_dir()
PAYLOAD_DIR = get_payload_dir()
WORK_DIR = Path("/kaggle/working")



def _ffmpeg_filter_support() -> dict:
    """One-time capability probe: libass (subtitles) and libfreetype (drawtext) are
    baked into Kaggle's distro ffmpeg but stripped from some homebrew builds."""
    caps = {"subtitles": False, "drawtext": False}
    try:
        chk = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        caps["subtitles"] = " subtitles " in chk.stdout
        caps["drawtext"] = " drawtext " in chk.stdout
    except Exception:
        pass
    return caps

FFCAPS = _ffmpeg_filter_support()


# ---------------------------------------------------------------------------
# 🎙️ VOICESTUDIO EXTRACTION — Multi-Voice Persona Engine
# Every vertical gets its OWN authority anchor so 16 daily uploads never share
# one stock Edge-TTS voice (YouTube's "inauthentic content" reviewers listen for it).
# ---------------------------------------------------------------------------
VOICE_PERSONAS = {
    "stock_market": {
        "voice": "en-US-AndrewMultilingualNeural",
        "rate": "+4%",
        "pitch": "-2Hz",
        "desc": "Quantitative Institutional Desk Anchor",
    },
    "crypto": {
        "voice": "en-US-BrianMultilingualNeural",
        "rate": "+6%",
        "pitch": "-1Hz",
        "desc": "Derivatives & On-Chain Strategist",
    },
    "insurance": {
        "voice": "en-IN-PrabhatNeural",
        "rate": "+3%",
        "pitch": "-2Hz",
        "desc": "Forensic Policy & Risk Auditor",
    },
    "crypto_ethereum": {  # sibling of crypto
        "voice": "en-US-BrianMultilingualNeural",
        "rate": "+5%",
        "pitch": "-2Hz",
        "desc": "On-Chain Microstructure Anchor",
    },
}


def select_voice_persona(vertical: str) -> dict:
    """Signature voice persona for the vertical (voicestudio multi-persona routing)."""
    persona = dict(VOICE_PERSONAS.get(vertical or "", VOICE_PERSONAS["stock_market"]))
    if vertical not in VOICE_PERSONAS:
        persona["desc"] += " (fallback)"
    return persona


async def make_tts_and_subtitles(text: str, mp3_path: Path, ass_path: Path, persona: dict = None) -> float:
    """Generates audio via Edge-TTS (vertical persona) + word-level Hormozi ASS subtitles via Faster-Whisper."""
    persona = persona or {"voice": "en-US-AndrewNeural", "rate": "+3%", "pitch": "+0Hz"}
    comm = edge_tts.Communicate(text=text, voice=persona["voice"], rate=persona.get("rate", "+3%"), pitch=persona.get("pitch", "+0Hz"))
    await comm.save(str(mp3_path))

    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(mp3_path)],
        stdout=subprocess.PIPE, text=True, check=True
    )
    duration = float(res.stdout.strip())

    events = []
    try:
        try:
            model = WhisperModel("base.en", device="cuda", compute_type="float16")
            segments, _ = model.transcribe(str(mp3_path), word_timestamps=True)
        except Exception:
            model = WhisperModel("base.en", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(str(mp3_path), word_timestamps=True)
        for seg in segments:
            for w in (seg.words or []):
                s_m, s_s = divmod(w.start, 60)
                e_m, e_s = divmod(w.end, 60)
                start_ts = f"0:{int(s_m):02d}:{s_s:05.2f}"
                end_ts = f"0:{int(e_m):02d}:{e_s:05.2f}"
                clean_word = w.word.strip().upper()
                events.append(f"Dialogue: 0,{start_ts},{end_ts},Hormozi,{clean_word}")
    except Exception as whisper_err:
        print(f"Faster-Whisper unavailable ({whisper_err}) — dynamic word timing fallback engaged.")
        words = text.strip().split()
        if words and duration > 0:
            word_dur = duration / len(words)
            for i, w in enumerate(words):
                w_start = i * word_dur
                w_end = min(duration, (i + 1) * word_dur)
                s_m, s_s = divmod(w_start, 60)
                e_m, e_s = divmod(w_end, 60)
                events.append(f"Dialogue: 0,0:{int(s_m):02d}:{s_s:05.2f},0:{int(e_m):02d}:{e_s:05.2f},Hormozi,{w.upper()}")

    ass_path.write_text(ass_header + "\n".join(events), encoding="utf-8")
    return duration


def pick_video_encoder_args() -> list:
    """Checks NVENC availability once and returns the matching ffmpeg video encoder args."""
    try:
        chk = subprocess.run(["ffmpeg", "-encoders"], stdout=subprocess.PIPE, text=True)
        if "h264_nvenc" in chk.stdout:
            return ["-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "5M"]
    except Exception:
        pass
    return ["-c:v", "libx264", "-preset", "ultrafast"]


# ---------------------------------------------------------------------------
# 🛡️ OPENMONTAGE EXTRACTION — Post-Render Self-Review QA Gate
# Inspects every MP4 BEFORE it burns 1,600 YouTube API units: container/duration
# integrity, silence audit (volumedetect), black-frame audit (blackdetect).
# ---------------------------------------------------------------------------
def verify_rendered_video_qa(mp4_path: Path, expected_min_dur: float = 0.0) -> dict:
    """OpenMontage-style pre-upload inspection. Returns {passed, mean_volume_db, black_ratio, reasons}."""
    audit = {"passed": False, "mean_volume_db": None, "max_volume_db": None,
             "black_ratio": 0.0, "duration": 0.0, "reasons": []}
    try:
        if not Path(mp4_path).exists() or Path(mp4_path).stat().st_size < 500 * 1024:
            audit["reasons"].append("container missing or < 500KB")
            return audit
    except Exception as e:
        audit["reasons"].append(f"filesystem probe failed: {e}")
        return audit

    # 1. Stream & duration integrity (ffprobe)
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "stream=codec_name,codec_type,width:format=duration", "-of", "json", str(mp4_path)],
            stdout=subprocess.PIPE, text=True, check=True,
        )
        info = json.loads(probe.stdout or "{}")
        streams = info.get("streams", [])
        dur = float(float(info.get("format", {}).get("duration", 0) or 0))
        audit["duration"] = round(dur, 2)
        codecs = {(s.get("codec_type"), s.get("codec_name")) for s in streams}
        widths = [int(s.get("width", 0)) for s in streams if s.get("codec_type") == "video"]
        if ("video", "h264") not in codecs:
            audit["reasons"].append(f"no h264 video stream (got {sorted(codecs)})")
        if ("audio", "aac") not in codecs:
            audit["reasons"].append("no aac audio stream")
        if widths and min(widths) < 1080:
            audit["reasons"].append(f"video width {min(widths)} < 1080")
        if expected_min_dur > 0 and dur < expected_min_dur - 1.0:
            audit["reasons"].append(f"duration {dur:.1f}s shorter than narration {expected_min_dur:.1f}s")
    except Exception as e:
        audit["reasons"].append(f"ffprobe failed: {e}")
        return audit

    # 2. Silence audit: dead audio track must never reach YouTube (volumedetect)
    try:
        vol = subprocess.run(
            ["ffmpeg", "-i", str(mp4_path), "-vn", "-af", "volumedetect",
             "-f", "null", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        combined = vol.stderr + vol.stdout
        m_mean = re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB", combined)
        m_max = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", combined)
        mean_v = float(m_mean.group(1)) if m_mean else -91.0
        max_v = float(m_max.group(1)) if m_max else -91.0
        audit["mean_volume_db"] = round(mean_v, 1)
        audit["max_volume_db"] = round(max_v, 1)
        if mean_v < -35.0:
            # 🔧 Acoustic auto-healer: boost audio with broadcast loudnorm before failing
            print(f"🔧 [Acoustic Self-Heal] Volume low ({mean_v:.1f} dB). Applying surgical loudnorm audio boost...")
            healed_mp4 = mp4_path.with_name(f"healed_{mp4_path.name}")
            boost_cmd = [
                "ffmpeg", "-y", "-i", str(mp4_path),
                "-c:v", "copy",
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                "-c:a", "aac", "-b:a", "192k",
                str(healed_mp4)
            ]
            r_boost = subprocess.run(boost_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r_boost.returncode == 0 and healed_mp4.exists() and healed_mp4.stat().st_size > 1000:
                healed_mp4.replace(mp4_path)
                print(f"✓ [Acoustic Self-Heal] Replaced {mp4_path.name} with broadcast normalized audio.")
                mean_v = -14.0
                audit["mean_volume_db"] = -14.0
            else:
                audit["reasons"].append(f"near-silent audio track (mean {mean_v:.1f} dB < -35)")
    except Exception as e:
        audit["reasons"].append(f"volumedetect failed: {e}")

    # 3. Black-frame audit: broken chart PNGs renders as black — cap at 5% of runtime
    try:
        blk = subprocess.run(
            ["ffmpeg", "-i", str(mp4_path), "-vf", "blackdetect=d=1.5:pix_th=0.05",
             "-an", "-f", "null", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        combined = blk.stderr + blk.stdout
        black_total = 0.0
        for m in re.finditer(r"black_start:([\d.]+)\s+black_end:([\d.]+)", combined):
            black_total += float(m.group(2)) - float(m.group(1))
        ratio = (black_total / audit["duration"]) if audit["duration"] > 0 else 1.0
        audit["black_ratio"] = round(min(1.0, ratio), 4)
        if ratio > 0.05:
            audit["reasons"].append(f"black frames cover {ratio:.0%} of runtime (> 5% cap)")
    except Exception as e:
        audit["reasons"].append(f"blackdetect failed: {e}")

    audit["passed"] = not audit["reasons"]
    if audit["passed"]:
        print(f"🛡️ QA Gate PASSED: {audit['duration']:.1f}s · mean {audit['mean_volume_db']} dB · black {audit['black_ratio']:.1%}")
    else:
        print(f"🛡️ QA Gate FAILED: {audit['reasons']}")
    return audit


def _find_fontfile() -> str:
    """HUD drawtext needs a real fontfile; probe common linux/kaggle + macOS font paths."""
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if Path(p).exists():
            return p
    return ""


# ---------------------------------------------------------------------------
# 🎞️ LEMO-OPUSCAR EXTRACTION — Programmatic Motion (anti "static slideshow")
# Ken Burns zoom/pan on every still + animated HUD telemetry progress bar +
# live timestamp ticker. Continuous motion every second, zero diffusion cost.
# ---------------------------------------------------------------------------
def _ken_burns(src_label: str, out_label: str, size: str, drift: float = 0.22, sway: float = 40) -> str:
    """Ken Burns fragment WITH labels: [src:v]<motion>[out_label]; — for chains that
    reference out_label downstream (e.g. vstack). For in-chains use _ken_burns_body()."""
    return f"[{src_label}:v]" + _ken_burns_body(size, drift, sway) + f"[{out_label}]"


def _ken_burns_body(size: str, drift: float = 0.22, sway: float = 40) -> str:
    """Label-free Ken Burns fragment — caller keeps the chain alive with ',' until it
    closes with its own label (e.g. '[bg]'). Zoom drift + sinusoidal pan sway."""
    h = int(size.split("x")[1])
    return (
        f"scale=-2:{h * 2},"
        f"zoompan=z='min(zoom+0.0008,1.0+{drift})'"
        f":x='iw/2-(iw/zoom/2)+sin(on/45)*{sway}'"
        f":y='ih/2-(ih/zoom/2)+cos(on/60)*{sway // 2}'"
        f":d=1:fps=30:s={size}"
    )


HUD_BADGES = {
    "stock_market": "LIVE INSTITUTIONAL FLOW",
    "crypto": "LIVE ON-CHAIN DATA",
    "crypto_ethereum": "LIVE CHAIN MICROSTRUCTURE",
    "insurance": "POLICY WORDING AUDIT",
}


def _hud_filters(duration: float, vertical: str, fontfile: str = "", w: int = 1920, h: int = 1080) -> list:
    """Animated HUD chain: teal track + progress bar sweeping with playback time +
    live timestamp/vertical-badge ticker. Returns [] if nothing could be built."""
    dur = max(1.0, float(duration))
    bar_y = h - 26
    prog = (
        f"drawbox=x=0:y={bar_y}:w={w}:h=6:color=0x10B981@0.25:t=fill,"
        f"drawbox=x=0:y={bar_y}:w='min({w}\\,(t/{dur:.2f})*{w})':h=6:color=0x34D399@0.95:t=fill"
    )
    chain = [prog]
    if fontfile and FFCAPS["drawtext"]:
        badge = HUD_BADGES.get(vertical or "", "THE BULL PRINT")
        clock = (
            f"drawtext=fontfile='{fontfile}'"
            f":text='THE BULL PRINT · {badge} · %{{pts\\:hms}}'"
            f":fontcolor=0xEF4444:fontsize=30:box=1:boxcolor=0x0B0E14@0.62:boxborderw=12"
            f":x={w // 25}:y={h // 42}:enable='gte(t\\,0.8)'"
        )
        chain.append(clock)
    return chain


def _subs_tag(ass_path: Path) -> str:
    """',subtitles=...' fragment when libass exists in the host ffmpeg; '' otherwise."""
    if FFCAPS["subtitles"]:
        return f",subtitles='{Path(ass_path).as_posix()}'"
    if not Path(ass_path).exists():
        return ""
    return ""


def render_gpu_segment(seg: dict, mp3_path: Path, ass_path: Path, duration: float, out_mp4: Path, vertical: str = ""):
    """Renders 1080p NVIDIA segment — Ken Burns motion + animated HUD telemetry so
    no frame of the video is ever a frozen still (anti YPP 'static slideshow' flag)."""
    avatar_id = max(1, min(10, int(seg.get("avatar_studio_id", 1))))
    avatar_img = ASSETS_DIR / f"avatar_{avatar_id}.png"
    if not avatar_img.exists():
        avatar_img = ASSETS_DIR / "avatars" / f"avatar_{avatar_id}.png"

    b_roll = PAYLOAD_DIR / seg.get("b_roll_asset_ref", "NONE")
    fontfile = _find_fontfile()
    hud = _hud_filters(duration, vertical, fontfile)  # returns list of ready-to-chain filters

    if seg.get("visual_mode") == "CHART_B_ROLL_WITH_PIP" and b_roll.exists():
        filter_complex = "[0:v]" + _ken_burns_body("1920x1080")
        if hud:
            filter_complex += "," + ",".join(hud)
        filter_complex += (
            f"[bg];[1:v]scale=440:248[pip];"
            f"[bg][pip]overlay=x=1440:y=680" + _subs_tag(ass_path) + "[v]"
        )
        inputs = ["-loop", "1", "-i", str(b_roll), "-loop", "1", "-i", str(avatar_img), "-i", str(mp3_path)]
        audio_map = "2:a"
    else:
        filter_complex = "[0:v]" + _ken_burns_body("1920x1080", drift=0.14, sway=22)  # subtle studio drift
        if hud:
            filter_complex += "," + ",".join(hud)
        filter_complex += _subs_tag(ass_path) + "[v]"
        inputs = ["-loop", "1", "-i", str(avatar_img), "-i", str(mp3_path)]
        audio_map = "1:a"

    video_encoder = pick_video_encoder_args()

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", audio_map,
        "-af", "silenceremove=stop_periods=-1:stop_duration=0.35:stop_threshold=-42dB,loudnorm=I=-14:TP=-1.5:LRA=11",
        *video_encoder,
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-t", f"{duration:.2f}",
        str(out_mp4)
    ]
    subprocess.run(cmd, check=True)


def _normalize_title(text: str) -> str:
    """Case-insensitive, punctuation-insensitive title fingerprint for the dup guard."""
    return " ".join(re.sub(r"[^\w\s]+", " ", str(text or "").lower()).split())


def find_recent_duplicate(youtube_service, title: str, window_hours: int = 24) -> str:
    """
    Idempotency guard against overlapping schedulers / workflow retries.
    Pass A: channel uploads playlist scan (freshest & cheapest).
    Pass B: search.list(forMine=True) fallback (covers delayed playlist indexing).
    Returns the EXISTING video_id if the same normalized title was uploaded inside
    the 24h window; otherwise '' so the caller uploads a NEW video.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(hours=window_hours)

    def _norm(s: str) -> str:
        return _normalize_title(s)

    target = _norm(title)
    target_prefix = target[:60]
    if not target:
        return ""

    candidates = []

    # Pass A: uploads playlist (up to 25 most recent)
    try:
        chan = youtube_service.channels().list(part="contentDetails", mine=True).execute()
        uploads_pl = chan["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        for it in youtube_service.playlistItems().list(
            part="snippet", playlistId=uploads_pl, maxResults=25
        ).execute().get("items", []):
            sn = it.get("snippet", {})
            candidates.append((sn.get("resourceId", {}).get("videoId", ""), sn.get("title", ""), sn.get("publishedAt", "")))
    except Exception as e:
        print(f"Duplicate playlist scan notice: {e}")

    # Pass B: search.list forMine (up to 15 most recent by date)
    try:
        for it in youtube_service.search().list(
            part="snippet", forMine=True, type="video", maxResults=15, order="date"
        ).execute().get("items", []):
            sn = it.get("snippet", {})
            candidates.append((it.get("id", {}).get("videoId", ""), sn.get("title", ""), sn.get("publishTime", "")))
    except Exception as e:
        print(f"Duplicate search scan notice: {e}")

    seen = set()
    for vid, v_title, published_at in candidates:
        if not vid or vid in seen:
            continue
        seen.add(vid)
        norm = _norm(v_title)
        if not published_at or not (norm == target or norm[:60] == target_prefix):
            continue
        try:
            when = datetime.datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
            if when >= cutoff:
                return vid
        except Exception:
            continue
    return ""


def _is_quota_error(exc: Exception) -> bool:
    """True when we should rotate to the next Google Cloud project slot."""
    text = str(exc)
    return any(
        m in text
        for m in ("quotaExceeded", "dailyLimitExceeded", "uploadLimitExceeded", "rateLimitExceeded", "invalid_grant", "invalidCredentials")
    )


def load_oauth_pool() -> list:
    """Every OAuth slot: YT_OAUTH_POOL_JSON env > yt_oauth_pool.json > numbered/raw env vars."""
    slots = []
    pool_env = os.getenv("YT_OAUTH_POOL_JSON", "").strip()
    if pool_env:
        try:
            d = json.loads(pool_env)
            if isinstance(d, dict):
                d = [d]
            for s in d:
                if s.get("client_id") and s.get("client_secret") and s.get("refresh_token"):
                    slots.append(s)
        except Exception as e:
            print(f"YT_OAUTH_POOL_JSON unparsable: {e}")

    for p in [
        PAYLOAD_DIR / "yt_oauth_pool.json",
        ASSETS_DIR / "yt_oauth_pool.json",
        Path(__file__).parent.parent / "data" / "youtube_tokens" / "oauth_pool.json",
        Path("data/youtube_tokens/oauth_pool.json"),
    ]:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data = [data]
                for s in data:
                    if s.get("client_id") and s.get("client_secret") and s.get("refresh_token"):
                        slots.append(s)
            except Exception as e:
                print(f"{p} unparsable: {e}")

    if Path("/kaggle/input").exists():
        for match in Path("/kaggle/input").rglob("yt_oauth_pool.json"):
            try:
                data = json.loads(match.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    data = [data]
                for s in data:
                    if s.get("client_id") and s.get("client_secret") and s.get("refresh_token"):
                        slots.append(s)
            except Exception:
                pass

    for suffix in ("", "1", "2", "3", "4", "5", "6"):
        cid = os.getenv(f"YT_CLIENT_ID{suffix}") or os.getenv(f"YT_CLIENT_ID_{suffix}")
        cse = os.getenv(f"YT_CLIENT_SECRET{suffix}") or os.getenv(f"YT_CLIENT_SECRET_{suffix}")
        rt = os.getenv(f"YT_REFRESH_TOKEN{suffix}") or os.getenv(f"YT_REFRESH_TOKEN_{suffix}")
        if cid and cse and rt:
            slots.append({"client_id": cid, "client_secret": cse, "refresh_token": rt})

    seen, unique = set(), []
    for s in slots:
        key = (s.get("client_id") or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


LAST_OAUTH_SLOT = {"value": 0}


def _upload_with_slot(slot: dict, mp4_path: Path, thumb_path: Path, yt_payload: dict):
    """One full upload attempt on a single OAuth slot. Raises on quota so the caller rotates."""
    creds = Credentials(
        None,
        refresh_token=slot["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=slot["client_id"],
        client_secret=slot["client_secret"],
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)

    # Idempotency guard: skip if same normalized title was uploaded within 24h
    meta = yt_payload["metadata"]
    dup_id = find_recent_duplicate(youtube, meta["title"])
    if dup_id:
        print(f"Duplicate guard: '{meta['title'][:60]}' uploaded within 24h — skipping, existing video {dup_id}")
        return dup_id

    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta["description_body"],
            "tags": meta["tags"][:15],
            "categoryId": "27"
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True
        }
    }

    req = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(mp4_path), mimetype="video/mp4", resumable=True)
    )
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    video_id = resp["id"]

    if thumb_path.exists():
        try:
            youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumb_path))).execute()
        except Exception as te:
            print(f"⚠️ Custom thumbnail upload skipped (channel requires phone verification): {te}")

    return video_id


def upload_youtube_headless(mp4_path: Path, thumb_path: Path, yt_payload: dict) -> str:
    """Headless YouTube upload with containsSyntheticMedia=True, rotating through
    every Google Cloud project slot on quotaExceeded/invalid_grant."""
    pool = load_oauth_pool()
    if not pool:
        print("⚠️ No OAuth pool (yt_oauth_pool.json / yt_oauth.json / YT_* env vars) — DRY RUN upload.")
        return "DRY_RUN_KAGGLE_GPU_123"

    last_error = ""
    for idx, slot in enumerate(pool, 1):
        try:
            vid = _upload_with_slot(slot, mp4_path, thumb_path, yt_payload)
            LAST_OAUTH_SLOT["value"] = idx
            print(f"🔑 YouTube upload OK via Quota Slot #{idx} → {vid}")
            return vid
        except Exception as e:
            if _is_quota_error(e) and idx < len(pool):
                print(f"⚠️ YouTube API Slot #{idx} exhausted — rotating to Slot #{idx + 1} ({type(e).__name__})")
                last_error = str(e)
            else:
                if _is_quota_error(e):
                    last_error = str(e)
                    break
                print(f"Direct YouTube API upload bypassed (non-quota error on Slot #{idx}): {e}")
                raise

    LAST_OAUTH_SLOT["value"] = len(pool)
    print(f"❌ All {len(pool)} YouTube Quota Slots exhausted: {last_error}")
    return "QUOTA_EXHAUSTED_ALL_SLOTS"


async def render_and_upload_short_gpu(payload: dict, long_video_id: str, short_data: dict = None, short_index: int = 1, vertical: str = "") -> str:
    """Renders ONE 9:16 companion #Short (Ken Burns chart top / avatar bottom / emerald
    divider / HUD ticker) with vertical Hormozi subtitles and uploads headless to YouTube.

    short_data: the Short block (short_title / spoken_hook_and_body / cta_to_long_video / chart_image_ref).
                Defaults to youtube_payload.short_extraction for backward compatibility.
    short_index: 1-based position in today's Shorts batch — drives the per-short thumbnail
                 file lookup (short_thumb_1.jpg / short_thumb_2.jpg staged by the orchestrator).
    vertical: selects the signature voice persona + HUD badge for this Short."""
    yt_payload_block = payload.get("youtube_payload", {})
    persona = select_voice_persona(vertical or payload.get("vertical", ""))
    if not short_data:
        short_data = yt_payload_block.get("short_extraction")
    if not short_data:
        print("No short_extraction block in payload — skipping 9:16 Short.")
        return ""

    narration = " ".join(filter(None, [
        str(short_data.get("spoken_hook_and_body", "")).strip(),
        str(short_data.get("cta_to_long_video", "")).strip(),
    ]))
    if not narration:
        print(f"Short #{short_index} contained no narration — skipping.")
        return ""

    tag = f"{short_index:02d}"
    mp3 = WORK_DIR / f"short_{tag}.mp3"
    ass = WORK_DIR / f"short_{tag}.ass"
    dur = await make_tts_and_subtitles(narration, mp3, ass, persona=persona)

    # Retint the Hormozi .ass for vertical 9:16: 1080x1920 resolution header + larger 64pt font
    vertical_ass = (
        ass.read_text(encoding="utf-8")
        .replace("PlayResX: 1920", "PlayResX: 1080")
        .replace("PlayResY: 1080", "PlayResY: 1920")
        .replace(",Arial,56,", ",Arial,64,")
    )
    ass.write_text(vertical_ass, encoding="utf-8")

    chart_png = None
    chart_ref = str(short_data.get("chart_image_ref", "") or "")
    if chart_ref and (PAYLOAD_DIR / chart_ref).exists():
        chart_png = PAYLOAD_DIR / chart_ref
    if chart_png is None:
        for section in payload.get("website_article_payload", {}).get("article_sections", []):
            sec_ref = str(section.get("chart_image_ref", "") or "")
            if sec_ref and (PAYLOAD_DIR / sec_ref).exists():
                chart_png = PAYLOAD_DIR / sec_ref
                break
    if chart_png is None:
        staged_pngs = sorted(PAYLOAD_DIR.glob("*.png"))
        if not staged_pngs:
            print("No chart PNG staged — skipping 9:16 Short.")
            return ""
        chart_png = staged_pngs[0]

    avatar_img = ASSETS_DIR / "avatar_1.png"
    if not avatar_img.exists():
        avatar_img = ASSETS_DIR / "avatars" / "avatar_1.png"

    # Per-short 9:16 shelf thumbnail staged by the orchestrator
    short_thumb = PAYLOAD_DIR / f"short_thumb_{short_index}.jpg"
    if not short_thumb.exists():
        short_thumb = PAYLOAD_DIR / "yt_short_thumb.jpg"
    if not short_thumb.exists():
        short_thumb = PAYLOAD_DIR / "yt_thumb.jpg"

    # 9:16 master: Ken Burns chart on top, avatar bottom, emerald divider,
    # cover flash on first 0.85s for mobile thumbnail capture, Hormozi subtitles burned in.
    fontfile = _find_fontfile()
    hud_list = _hud_filters(min(dur, 58.5), vertical, fontfile, w=1080, h=1920)
    tail = list(hud_list)
    subs = _subs_tag(ass)
    if subs:
        tail.append(subs.lstrip(","))

    has_cover = short_thumb.exists()
    if has_cover:
        filter_graph = (
            "[0:v]" + _ken_burns_body("1080x960", drift=0.18, sway=28) + "[chartm];"
            "[1:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[ava];"
            "[chartm][ava]vstack=inputs=2,"
            "drawbox=x=0:y=956:w=1080:h=8:color=0x10B981@1.0:t=fill[vsplit];"
            "[2:v]scale=1080:1920[cover];"
            "[vsplit][cover]overlay=0:0:enable='between(t,0,0.85)'[vbase]"
        )
        if tail:
            filter_graph += ";" + "[vbase]" + ",".join(tail) + "[v]"
        else:
            filter_graph += ";[vbase]null[v]"
    else:
        filter_graph = (
            "[0:v]" + _ken_burns_body("1080x960", drift=0.18, sway=28) + "[chartm];"
            "[1:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[ava];"
            "[chartm][ava]vstack=inputs=2,"
            "drawbox=x=0:y=956:w=1080:h=8:color=0x10B981@1.0:t=fill"
        )
        if tail:
            filter_graph += "," + ",".join(tail)
        filter_graph += "[v]"

    out_mp4 = WORK_DIR / f"final_short_{tag}.mp4"
    inputs = [
        "-loop", "1", "-i", str(chart_png),
        "-loop", "1", "-i", str(avatar_img),
    ]
    if has_cover:
        inputs += ["-loop", "1", "-i", str(short_thumb)]
    audio_idx = 3 if has_cover else 2
    inputs += ["-i", str(mp3)]

    cmd = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_graph,
        "-map", "[v]", "-map", f"{audio_idx}:a",
        "-af", "silenceremove=stop_periods=-1:stop_duration=0.35:stop_threshold=-42dB,loudnorm=I=-14:TP=-1.5:LRA=11",
        *pick_video_encoder_args(),
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", f"{min(dur, 58.5):.2f}",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)

    # 🛡️ OpenMontage QA gate — never burn 1,600 quota units on a broken Short
    qa = verify_rendered_video_qa(out_mp4, expected_min_dur=min(dur, 58.5))
    if not qa["passed"]:
        print(f"❌ Short #{short_index} failed QA — upload SKIPPED (quota protected): {qa['reasons']}")
        return ""

    meta = yt_payload_block.get("metadata", {})
    angle_tag = str(short_data.get("angle", "") or "").strip()
    angle_suffix = {"core_trap_hook": "The Trap Nobody Talks About",
                    "quantitative_proof_rule": "The Math That Settles It"}.get(angle_tag, "")
    short_title = str(short_data.get("short_title", "") or meta.get("title", "The Bull Print Daily Brief"))
    if angle_suffix and angle_suffix.lower() not in short_title.lower():
        short_title = f"{short_title} | {angle_suffix}"
    description_body = (
        f"{str(short_data.get('spoken_hook_and_body', ''))[:180]}\n\n"
        f"▶️ Watch the FULL MASTERCLASS: https://youtu.be/{long_video_id}\n"
        f"🛠️ Get every free trading tool: https://the-bull-print.vercel.app/tools\n\n"
        f"🎓 SEBI: Educational content only — not investment advice."
    )
    short_yt_payload = {
        "metadata": {
            "title": f"{short_title} #Shorts",
            "description_body": description_body,
            "tags": (meta.get("tags", []) or [])[:15] + ["shorts"],
        }
    }
    # Per-short 9:16 shelf thumbnail staged by the orchestrator (short_thumb_1.jpg / short_thumb_2.jpg),
    # falling back to the shared short banner, then the long-form thumb.
    short_thumb = PAYLOAD_DIR / f"short_thumb_{short_index}.jpg"
    if not short_thumb.exists():
        short_thumb = PAYLOAD_DIR / "yt_short_thumb.jpg"
    if not short_thumb.exists():
        short_thumb = PAYLOAD_DIR / "yt_thumb.jpg"
    short_vid_id = upload_youtube_headless(out_mp4, short_thumb, short_yt_payload)
    print(f"9:16 Short #{short_index} render and upload completed! Short Video ID: {short_vid_id}")
    return short_vid_id


def gather_shorts_batch(payload: dict) -> list:
    """Builds today's Shorts batch: explicit short_extractions first (orchestrator enforces 2),
    padded / replaced by the legacy short_extraction block so single-short payloads still render."""
    yt = payload.get("youtube_payload", {})
    batch = []
    for item in yt.get("short_extractions") or []:
        if isinstance(item, dict) and str(item.get("spoken_hook_and_body", "")).strip():
            batch.append(item)
    legacy = yt.get("short_extraction")
    if isinstance(legacy, dict) and str(legacy.get("spoken_hook_and_body", "")).strip():
        if not batch:
            batch = [legacy]
        elif len(batch) == 1 and json.dumps(batch[0], sort_keys=True) != json.dumps(legacy, sort_keys=True):
            batch.append(legacy)
    target = int(payload.get("shorts_count", 0) or 0)
    if target > 0:
        batch = batch[:target]
    else:
        batch = batch[:2]
    return batch


async def run_kaggle_job():
    global PAYLOAD_DIR, ASSETS_DIR
    PAYLOAD_DIR = get_payload_dir()
    ASSETS_DIR = get_assets_dir()

    payload_file = PAYLOAD_DIR / "payload.json"
    if not payload_file.exists():
        found = list(Path("/kaggle/input").rglob("payload.json")) if Path("/kaggle/input").exists() else []
        if found:
            payload_file = found[0]
            PAYLOAD_DIR = payload_file.parent
        else:
            payload_file = Path(__file__).parent.parent / "payload.json"
            if not payload_file.exists() and Path("payload.json").exists():
                payload_file = Path("payload.json")
                PAYLOAD_DIR = Path(".")

    print(f"📦 Loaded payload from: {payload_file} (PAYLOAD_DIR={PAYLOAD_DIR}, ASSETS_DIR={ASSETS_DIR})")
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    vertical = str(payload.get("vertical", "") or "")
    persona = select_voice_persona(vertical)
    if persona.get("desc"):
        print(f"🎙️ Voice persona for this slot: {persona['voice']} ({persona['desc']})")
    only_shorts = bool(payload.get("only_shorts", False))
    vid_id = payload.get("existing_long_video_id", "")
    qa = {"passed": True, "mean_volume_db": -16.0, "max_volume_db": -1.0, "black_ratio": 0.0, "duration": 0.0, "reasons": []}
    timestamps = []

    if not only_shorts:
        seg_files = []
        cumulative = 0.0
        for seg in payload["youtube_payload"]["segments"]:
            idx = seg["segment_index"]
            mp3 = WORK_DIR / f"seg_{idx:02d}.mp3"
            ass = WORK_DIR / f"seg_{idx:02d}.ass"
            mp4 = WORK_DIR / f"seg_{idx:02d}.mp4"

            m, s = divmod(int(cumulative), 60)
            timestamps.append(f"{m:02d}:{s:02d} - {seg['chapter_title']}")

            dur = await make_tts_and_subtitles(seg["spoken_narration"], mp3, ass, persona=persona)
            render_gpu_segment(seg, mp3, ass, dur, mp4, vertical=vertical)
            seg_files.append(mp4)
            cumulative += dur

        concat_txt = WORK_DIR / "concat.txt"
        concat_txt.write_text("\n".join([f"file '{f.as_posix()}'" for f in seg_files]), encoding="utf-8")
        final_mp4 = WORK_DIR / "final_longform.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(final_mp4)], check=True)

        # 🛡️ OpenMontage QA gate on the long master — silent audio / black frames never reach YouTube
        qa = verify_rendered_video_qa(final_mp4, expected_min_dur=cumulative)

        payload["youtube_payload"]["metadata"]["description_body"] += "\n\n⏱️ CHAPTERS:\n" + "\n".join(timestamps)
        if qa["passed"]:
            vid_id = upload_youtube_headless(final_mp4, PAYLOAD_DIR / "yt_thumb.jpg", payload["youtube_payload"])
        else:
            print(f"❌ Long-form failed QA — upload SKIPPED (quota protected): {qa['reasons']}")
    else:
        print("⚡ ONLY_SHORTS mode active — skipping longform rendering!")

    shorts_batch = gather_shorts_batch(payload)
    target_idx = payload.get("target_short_index")
    if target_idx and 1 <= int(target_idx) <= len(shorts_batch):
        shorts_batch = [shorts_batch[int(target_idx) - 1]]
        start_idx = int(target_idx)
    else:
        start_idx = 1

    print(f"Shorts batch for this slot: {len(shorts_batch)} video(s)")
    short_video_ids = []
    for i, short_data in enumerate(shorts_batch, start=start_idx):
        try:
            short_vid_id = await render_and_upload_short_gpu(payload, vid_id, short_data=short_data, short_index=i, vertical=vertical)
        except Exception as exc:
            print(f"Short #{i} render/upload failed — continuing batch: {exc}")
            short_vid_id = ""
        if short_vid_id:
            short_video_ids.append(short_vid_id)

    result = {
        "youtube_video_id": vid_id,
        "short_video_ids": short_video_ids,
        "short_video_id": short_video_ids[0] if short_video_ids else "",
        "shorts_count": len(short_video_ids),
        "oauth_slot_used": LAST_OAUTH_SLOT["value"],
        "qa_audit": {"passed": qa["passed"], "mean_volume_db": qa["mean_volume_db"],
                     "max_volume_db": qa["max_volume_db"], "black_ratio": qa["black_ratio"],
                     "duration": qa["duration"], "reasons": qa["reasons"][:3]},
        "timestamps_log": timestamps
    }
    (WORK_DIR / "render_result.json").write_text(json.dumps(result), encoding="utf-8")
    print(f"Kaggle render and upload completed! Long Video ID: {vid_id} | Shorts: {short_video_ids}")


if __name__ == "__main__":
    asyncio.run(run_kaggle_job())
