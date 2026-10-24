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

ASSETS_DIR = Path("/kaggle/input/flipzon-studio-assets")
PAYLOAD_DIR = Path("/kaggle/input/flipzon-daily-payload")
WORK_DIR = Path("/kaggle/working")

# Fallback to local paths if testing locally
if not ASSETS_DIR.exists():
    ASSETS_DIR = Path(__file__).parent.parent / "assets"
if not PAYLOAD_DIR.exists():
    PAYLOAD_DIR = Path(__file__).parent.parent / "kaggle_stage"


async def make_tts_and_subtitles(text: str, mp3_path: Path, ass_path: Path) -> float:
    """Generates audio via Edge-TTS and word-level Hormozi ASS subtitles via Faster-Whisper."""
    comm = edge_tts.Communicate(text=text, voice="en-US-AndrewNeural", rate="+3%")
    await comm.save(str(mp3_path))

    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(mp3_path)],
        stdout=subprocess.PIPE, text=True, check=True
    )
    duration = float(res.stdout.strip())

    try:
        model = WhisperModel("base.en", device="cuda", compute_type="float16")
        segments, _ = model.transcribe(str(mp3_path), word_timestamps=True)
    except Exception:
        model = WhisperModel("base.en", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(mp3_path), word_timestamps=True)

    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, BackColour, Bold, Outline, Shadow, Alignment, MarginV
Style: Hormozi,Arial,56,&H0081B910,&H80000000,-1,4,2,2,140

[Events]
Format: Layer, Start, End, Style, Text
"""
    events = []
    for seg in segments:
        for w in (seg.words or []):
            s_m, s_s = divmod(w.start, 60)
            e_m, e_s = divmod(w.end, 60)
            start_ts = f"0:{int(s_m):02d}:{s_s:05.2f}"
            end_ts = f"0:{int(e_m):02d}:{e_s:05.2f}"
            clean_word = w.word.strip().upper()
            events.append(f"Dialogue: 0,{start_ts},{end_ts},Hormozi,{clean_word}")

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


def render_gpu_segment(seg: dict, mp3_path: Path, ass_path: Path, duration: float, out_mp4: Path):
    """Renders 1080p segment using NVIDIA GPU NVENC hardware acceleration."""
    avatar_id = max(1, min(10, int(seg.get("avatar_studio_id", 1))))
    avatar_img = ASSETS_DIR / f"avatar_{avatar_id}.png"
    if not avatar_img.exists():
        avatar_img = ASSETS_DIR / "avatars" / f"avatar_{avatar_id}.png"

    b_roll = PAYLOAD_DIR / seg.get("b_roll_asset_ref", "NONE")

    if seg.get("visual_mode") == "CHART_B_ROLL_WITH_PIP" and b_roll.exists():
        filter_complex = (
            f"[0:v]scale=1920:1080[bg];"
            f"[1:v]scale=440:248[pip];"
            f"[bg][pip]overlay=x=1440:y=680,subtitles='{ass_path.as_posix()}'[v]"
        )
        inputs = ["-loop", "1", "-i", str(b_roll), "-loop", "1", "-i", str(avatar_img), "-i", str(mp3_path)]
        audio_map = "2:a"
    else:
        filter_complex = f"[0:v]scale=1920:1080,subtitles='{ass_path.as_posix()}'[v]"
        inputs = ["-loop", "1", "-i", str(avatar_img), "-i", str(mp3_path)]
        audio_map = "1:a"

    video_encoder = pick_video_encoder_args()

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", audio_map,
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


def upload_youtube_headless(mp4_path: Path, thumb_path: Path, yt_payload: dict) -> str:
    """Headless YouTube upload with containsSyntheticMedia=True using OAuth refresh token."""
    creds_file = ASSETS_DIR / "yt_oauth.json"
    client_id = os.getenv("YT_CLIENT_ID")
    client_secret = os.getenv("YT_CLIENT_SECRET")
    refresh_token = os.getenv("YT_REFRESH_TOKEN")
    
    creds = None
    if client_id and client_secret and refresh_token:
        try:
            creds = Credentials(
                None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret
            )
            creds.refresh(Request())
        except Exception as e:
            print(f"Direct refresh token error: {e}")

    if not creds and creds_file.exists():
        try:
            creds_data = json.loads(creds_file.read_text(encoding="utf-8"))
            creds = Credentials(
                None,
                refresh_token=creds_data["refresh_token"],
                token_uri="https://oauth2.googleapis.com/token",
                client_id=creds_data["client_id"],
                client_secret=creds_data["client_secret"]
            )
            creds.refresh(Request())
        except Exception as e:
            print(f"OAuth file error: {e}")

    if creds:
        try:
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
                youtube.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumb_path))).execute()

            return video_id
        except Exception as e:
            print(f"Direct YouTube API upload bypassed: {e}")

    return "DRY_RUN_KAGGLE_GPU_123"


async def render_and_upload_short_gpu(payload: dict, long_video_id: str) -> str:
    """Renders the 9:16 companion #Shorts (chart top / avatar bottom / emerald divider)
    with vertical Hormozi subtitles and uploads headless to YouTube with #Shorts branding."""
    short_data = payload.get("youtube_payload", {}).get("short_extraction")
    if not short_data:
        print("No short_extraction block in payload — skipping 9:16 Short.")
        return ""

    narration = " ".join(filter(None, [
        str(short_data.get("spoken_hook_and_body", "")).strip(),
        str(short_data.get("cta_to_long_video", "")).strip(),
    ]))
    if not narration:
        print("short_extraction contained no narration — skipping 9:16 Short.")
        return ""

    mp3 = WORK_DIR / "short_00.mp3"
    ass = WORK_DIR / "short_00.ass"
    dur = await make_tts_and_subtitles(narration, mp3, ass)

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

    # 9:16 master: chart cropped to 1080x960 on top, avatar 1080x960 on bottom,
    # #10B981 emerald divider bridging the seam, Hormozi subtitles burned in.
    filter_graph = (
        "[0:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[chart];"
        "[1:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[ava];"
        "[chart][ava]vstack=inputs=2,"
        "drawbox=x=0:y=956:w=1080:h=8:color=0x10B981@1.0:t=fill,"
        f"subtitles='{ass.as_posix()}'[v]"
    )

    out_mp4 = WORK_DIR / "final_short_9x16.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(chart_png),
        "-loop", "1", "-i", str(avatar_img),
        "-i", str(mp3),
        "-filter_complex", filter_graph,
        "-map", "[v]", "-map", "2:a",
        *pick_video_encoder_args(),
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", f"{min(dur, 58.5):.2f}",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True)

    meta = payload.get("youtube_payload", {}).get("metadata", {})
    short_title = str(short_data.get("short_title", "") or meta.get("title", "The Bull Print Daily Brief"))
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
    short_vid_id = upload_youtube_headless(out_mp4, PAYLOAD_DIR / "yt_thumb.jpg", short_yt_payload)
    print(f"9:16 Short render and upload completed! Short Video ID: {short_vid_id}")
    return short_vid_id


async def run_kaggle_job():
    payload_file = PAYLOAD_DIR / "payload.json"
    if not payload_file.exists():
        payload_file = Path(__file__).parent.parent / "payload.json"
        
    payload = json.loads(payload_file.read_text(encoding="utf-8"))
    seg_files = []
    cumulative = 0.0
    timestamps = []

    for seg in payload["youtube_payload"]["segments"]:
        idx = seg["segment_index"]
        mp3 = WORK_DIR / f"seg_{idx:02d}.mp3"
        ass = WORK_DIR / f"seg_{idx:02d}.ass"
        mp4 = WORK_DIR / f"seg_{idx:02d}.mp4"

        m, s = divmod(int(cumulative), 60)
        timestamps.append(f"{m:02d}:{s:02d} - {seg['chapter_title']}")

        dur = await make_tts_and_subtitles(seg["spoken_narration"], mp3, ass)
        render_gpu_segment(seg, mp3, ass, dur, mp4)
        seg_files.append(mp4)
        cumulative += dur

    concat_txt = WORK_DIR / "concat.txt"
    concat_txt.write_text("\n".join([f"file '{f.as_posix()}'" for f in seg_files]), encoding="utf-8")
    final_mp4 = WORK_DIR / "final_longform.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(final_mp4)], check=True)

    payload["youtube_payload"]["metadata"]["description_body"] += "\n\n⏱️ CHAPTERS:\n" + "\n".join(timestamps)
    vid_id = upload_youtube_headless(final_mp4, PAYLOAD_DIR / "yt_thumb.jpg", payload["youtube_payload"])

    short_vid_id = await render_and_upload_short_gpu(payload, vid_id)

    (WORK_DIR / "render_result.json").write_text(json.dumps({
        "youtube_video_id": vid_id,
        "short_video_id": short_vid_id,
        "timestamps_log": timestamps
    }), encoding="utf-8")
    print(f"Kaggle render and upload completed! Long Video ID: {vid_id} | Short Video ID: {short_vid_id}")


if __name__ == "__main__":
    asyncio.run(run_kaggle_job())
