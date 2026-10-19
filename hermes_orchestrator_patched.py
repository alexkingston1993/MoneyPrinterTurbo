#!/usr/bin/env python3.11
"""
Hermes Agent — Self-improving Pipeline Orchestrator.

A self-contained, self-learning agent that:
1. Monitors Indian financial news (RSS + GDELT)
2. Orchestrates the full video pipeline with auto-retry
3. Learns from failures (creates skills in SQLite KB)
4. Generates organized output (date/channel/video_name)
5. Sends EOD reports (local + email)

Usage:
  python3.11 hermes_orchestrator.py              # Full run
  python3.11 hermes_orchestrator.py --news-only   # Just news cycle
  python3.11 hermes_orchestrator.py --pipeline-only  # Just pipeline
"""

import asyncio
import datetime
import json
import math
import os
import random
import re
import shutil
import smtplib
import sqlite3
import subprocess
import sys
import time
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

# ── Configuration ───────────────────────────────────────────────
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PY311 = "/Users/apple/Documents/Antigravity/untitled folder/.venv/bin/python3.11"
PEXELS_KEY = os.environ.get("PEXELS_API_KEY",
    "2927GljrcuM0PxfFHrBTUfShGAHLL2LcVGbGhuQkxddHHTZ61NzP1sSb")
VOICE_REF = os.path.join(PROJECT_DIR, "app/services/voices/alex_ref.wav")
AVATAR_DIR = os.path.join(PROJECT_DIR, "data/avatars")
BASE_OUTPUT = os.path.join(PROJECT_DIR, "output")
DB_PATH = os.path.join(PROJECT_DIR, "data", "hermes_agent.db")
SCRIPT_FILE = "/tmp/market_script_full.txt"
LOG_FILE = "/tmp/hermes_pipeline.log"

CHANNELS = {"en": "The Compounder", "ta": "The Compounder Tamil", "hi": "The Compounder Hindi"}
NSE_SYMBOLS = {
    "TCS": "TCS.NS", "RELIANCE": "RELIANCE.NS", "HDFC": "HDFCBANK.NS",
    "INFY": "INFY.NS", "ICICI": "ICICIBANK.NS", "SBIN": "SBIN.NS",
    "BHARTI": "BHARTIARTL.NS", "DMART": "DMART.NS", "TITAN": "TITAN.NS",
    "NIFTY": "^NSEI", "SENSEX": "^BSESN", "BANKNIFTY": "^NSEBANK",
}

# ── Utilities ────────────────────────────────────────────────────

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def sanitize_script(text: str) -> str:
    text = text.replace("\u2011", "-").replace("\u2012", "-").replace("\u2013", "-")
    text = text.replace("\u2014", " - ").replace("\u2015", " - ").replace("\u2212", "-")
    text = text.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ")
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'---', '', text)
    text = re.sub(r'###\s*', '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'(\d+)\s*%', r'\1 percent', text)
    text = re.sub(r' +', ' ', text)

    def _fmt_date(m):
        raw = m.group(0)
        parts = raw.replace("-", "/").split("/")
        if len(parts) == 3:
            months = ["", "January", "February", "March", "April", "May", "June",
                     "July", "August", "September", "October", "November", "December"]
            try:
                p0, p1, p2 = parts[0], parts[1], parts[2]
                if len(p0) == 4:
                    return f"{months[int(p1)]} {int(p2)}, {p0}"
                elif int(p0) > 12:
                    return f"{months[int(p1)]} {int(p0)}, {p2}"
                else:
                    return f"{months[int(p0)]} {int(p1)}, {p2}"
            except:
                pass
        return raw
    text = re.sub(r'\b\d{1,4}[-/]\d{1,2}[-/]\d{2,4}\b', _fmt_date, text)
    text = text.strip()
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def extract_stock_mentions(script: str) -> List[Tuple[str, str]]:
    mentions = []
    for name, symbol in NSE_SYMBOLS.items():
        if re.search(r'\b' + re.escape(name) + r'\b', script, re.IGNORECASE):
            mentions.append((name, symbol))
    return mentions


def create_output_structure(today: str = "", channel: str = "en",
                            video_name: str = "market_update") -> str:
    if not today:
        today = date.today().isoformat()
    day_dir = os.path.join(BASE_OUTPUT, today)
    channel_name = CHANNELS.get(channel, channel)
    video_dir = os.path.join(day_dir, channel_name, video_name)
    os.makedirs(video_dir, exist_ok=True)
    return video_dir


# ── Knowledge Base (SQLite) ──────────────────────────────────────

class KnowledgeBase:
    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS topics (
                    id TEXT PRIMARY KEY, topic TEXT UNIQUE, category TEXT,
                    first_seen TEXT, last_covered TEXT,
                    coverage_count INTEGER DEFAULT 0, avg_engagement REAL DEFAULT 0.0,
                    performance_score REAL DEFAULT 0.5
                );
                CREATE TABLE IF NOT EXISTS news (
                    id TEXT PRIMARY KEY, title TEXT, source TEXT, url TEXT UNIQUE,
                    summary TEXT, published TEXT, topics TEXT,
                    relevance_score REAL DEFAULT 0.0, processed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS content_queue (
                    id TEXT PRIMARY KEY, topic TEXT, hook_category TEXT,
                    target_languages TEXT, rationale TEXT, source_news_id TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now')), generated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS skills (
                    id TEXT PRIMARY KEY, name TEXT UNIQUE, description TEXT,
                    pattern TEXT, success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')), last_used TEXT
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY, content_queue_id TEXT,
                    engagement_score REAL, views INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0, comments INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    reported_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS agent_state (
                    key TEXT PRIMARY KEY, value TEXT
                );
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id TEXT PRIMARY KEY, run_date TEXT, status TEXT,
                    steps_json TEXT, video_path TEXT, duration REAL,
                    created_at TEXT DEFAULT (datetime('now'))
                );
            """)

    def get_state(self, key: str, default: str = "") -> str:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM agent_state WHERE key = ?", (key,)).fetchone()
            return row[0] if row else default

    def set_state(self, key: str, value: str):
        with self._conn() as conn:
            conn.execute("INSERT OR REPLACE INTO agent_state (key, value) VALUES (?, ?)", (key, value))
            conn.commit()

    def store_skill(self, skill: "Skill"):
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO skills (id, name, description, pattern,
                   success_count, fail_count, created_at, last_used)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (skill.id or str(uuid.uuid4()), skill.name, skill.description,
                 json.dumps(skill.pattern) if isinstance(skill.pattern, dict) else skill.pattern,
                 skill.success_count, skill.fail_count,
                 skill.created_at or datetime.now().isoformat(),
                 skill.last_used or datetime.now().isoformat()),
            )
            conn.commit()

    def get_skills(self) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM skills ORDER BY success_count DESC, fail_count ASC"
            ).fetchall()
            return [dict(row) for row in rows]

    def record_pipeline_run(self, run_id: str, run_date: str, status: str,
                             steps_json: str, video_path: str, duration: float):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO pipeline_runs (id, run_date, status, steps_json, video_path, duration)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (run_id, run_date, status, steps_json, video_path, duration),
            )
            conn.commit()

    def get_recent_runs(self, limit: int = 10) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    def store_news(self, item: "NewsItem"):
        with self._conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO news
                   (id, title, source, url, summary, published, topics, relevance_score, processed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (item.id or str(uuid.uuid4()), item.title, item.source, item.url,
                 item.summary, item.published, json.dumps(item.topics),
                 item.relevance_score, 1 if item.processed else 0),
            )
            conn.commit()

    def get_unprocessed_news(self, limit: int = 10) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM news WHERE processed = 0 ORDER BY relevance_score DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_news_processed(self, news_id: str):
        with self._conn() as conn:
            conn.execute("UPDATE news SET processed = 1 WHERE id = ?", (news_id,))
            conn.commit()

    def enqueue(self, suggestion: "ContentSuggestion"):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO content_queue
                   (id, topic, hook_category, target_languages, rationale, source_news_id, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (suggestion.id or str(uuid.uuid4()), suggestion.topic, suggestion.hook_category,
                 json.dumps(suggestion.target_languages), suggestion.rationale,
                 suggestion.source_news_id, suggestion.status,
                 suggestion.created_at or datetime.now().isoformat()),
            )
            conn.commit()

    def get_pending_queue(self, limit: int = 10) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM content_queue WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    def upsert_topic(self, topic: str, category: str = "general"):
        now = datetime.now().isoformat()
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id, first_seen, coverage_count FROM topics WHERE topic = ?", (topic,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE topics SET last_covered = ?, coverage_count = coverage_count + 1 WHERE topic = ?",
                    (now, topic),
                )
            else:
                conn.execute(
                    "INSERT INTO topics (id, topic, category, first_seen, last_covered, coverage_count) VALUES (?, ?, ?, ?, ?, 1)",
                    (str(uuid.uuid4()), topic, category, now, now),
                )
            conn.commit()

    def get_stats(self) -> dict:
        with self._conn() as conn:
            return {
                "topics": conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0],
                "news_articles": conn.execute("SELECT COUNT(*) FROM news").fetchone()[0],
                "pending_queue": conn.execute(
                    "SELECT COUNT(*) FROM content_queue WHERE status = 'pending'"
                ).fetchone()[0],
                "skills": conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0],
                "pipeline_runs": conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0],
            }


@dataclass
class NewsItem:
    id: str = ""
    title: str = ""
    source: str = ""
    url: str = ""
    summary: str = ""
    published: str = ""
    topics: List[str] = field(default_factory=list)
    relevance_score: float = 0.0
    processed: bool = False


@dataclass
class ContentSuggestion:
    id: str = ""
    topic: str = ""
    hook_category: str = ""
    target_languages: List[str] = field(default_factory=lambda: ["en", "ta", "hi"])
    rationale: str = ""
    source_news_id: str = ""
    status: str = "pending"
    created_at: str = ""


@dataclass
class Skill:
    id: str = ""
    name: str = ""
    description: str = ""
    pattern: str = ""
    success_count: int = 0
    fail_count: int = 0
    created_at: str = ""
    last_used: str = ""


@dataclass
class StepResult:
    name: str = ""
    status: str = "fail"
    duration: float = 0.0
    error: str = ""
    output: str = ""
    retry_count: int = 0


# ── News Fetcher ─────────────────────────────────────────────────

class NewsFetcher:
    def __init__(self):
        self.session = requests.Session() if 'requests' in sys.modules else None
        import requests as req
        self.session = req.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36"
        })

    def fetch_rss(self, url: str, source_name: str) -> List[NewsItem]:
        try:
            import xml.etree.ElementTree as ET
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            items = []
            for entry in root.iter("item"):
                items.append(NewsItem(
                    title=entry.findtext("title", "").strip(),
                    source=source_name,
                    url=entry.findtext("link", "").strip(),
                    summary=entry.findtext("description", "").strip(),
                    published=entry.findtext("pubDate", "").strip(),
                ))
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
                link = link_el.attrib.get("href", "") if link_el is not None else ""
                items.append(NewsItem(
                    title=entry.findtext("{http://www.w3.org/2005/Atom}title", "").strip(),
                    source=source_name, url=link.strip(),
                    summary=entry.findtext("{http://www.w3.org/2005/Atom}summary", "").strip(),
                    published=entry.findtext("{http://www.w3.org/2005/Atom}published", "").strip(),
                ))
            return items
        except Exception as e:
            log(f"RSS fetch failed {source_name}: {e}")
            return []

    def fetch_all(self) -> List[NewsItem]:
        feeds = [
            ("https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms", "Economic Times"),
            ("https://www.moneycontrol.com/rss/business.xml", "Moneycontrol"),
            ("https://www.livemint.com/rss/money", "LiveMint"),
        ]
        items = []
        for url, name in feeds:
            items.extend(self.fetch_rss(url, name))
        # GDELT
        try:
            url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={quote('Indian stock market')}&mode=artlist&format=json&maxrecords=25&timespan=1d&sort=date"
            resp = self.session.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                for article in data.get("articles", []):
                    items.append(NewsItem(
                        title=article.get("title", ""), source="GDELT",
                        url=article.get("url", ""), summary=article.get("snippet", ""),
                        published=article.get("seendate", ""),
                    ))
        except Exception as e:
            log(f"GDELT fetch failed: {e}")
        return items


# ── Pipeline Steps ───────────────────────────────────────────────

class PipelineSteps:
    @staticmethod
    def step_script_prep(script_path: str) -> Tuple[str, List[str], List[Tuple[str, str]]]:
        with open(script_path) as f:
            raw = f.read()
        sanitized = sanitize_script(raw)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', sanitized) if s.strip()]
        stocks = extract_stock_mentions(raw)
        log(f"Script: {len(sanitized)} chars, {len(sentences)} sentences, {len(stocks)} stock mentions")
        return sanitized, sentences, stocks

    @staticmethod
    def step_tts(text: str, output_path: str) -> Tuple[str, float]:
        log("TTS: Coqui XTTS v2 with Alex's voice")
        tts_script = f'''import os, sys, time, json
os.environ["COQUI_TOS_AGREED"] = "1"
text = {json.dumps(text)}
from TTS.api import TTS
t0 = time.time()
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
print(f"LOADED={{time.time()-t0:.1f}}", flush=True)
t0 = time.time()
tts.tts_to_file(text=text, file_path="{output_path}",
                speaker_wav="{VOICE_REF}", language="en", speed=1.0)
print(f"GEN_TIME={{time.time()-t0:.1f}}", flush=True)
import soundfile as sf
data, sr = sf.read("{output_path}")
print(f"DURATION={{len(data)/sr}}", flush=True)
'''
        tts_file = "/tmp/_hermes_tts.py"
        with open(tts_file, "w") as f:
            f.write(tts_script)
        t0 = time.time()
        r = subprocess.run([PY311, tts_file], capture_output=True, text=True, timeout=7200)
        elapsed = time.time() - t0
        if r.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(f"TTS failed: {r.stderr[:500]}")
        dur_match = re.search(r'DURATION=([\d.]+)', r.stdout)
        duration = float(dur_match.group(1)) if dur_match else 0
        log(f"TTS: {duration:.0f}s in {elapsed:.1f}s")
        return output_path, duration

    @staticmethod
    def step_tts_fallback(text: str, output_path: str) -> Tuple[str, float]:
        log("TTS fallback: edge-tts")
        import edge_tts
        import soundfile as sf
        async def _gen():
            communicate = edge_tts.Communicate(text, "en-US-JennyNeural")
            await communicate.save(output_path)
        t0 = time.time()
        asyncio.run(_gen())
        elapsed = time.time() - t0
        data, sr = sf.read(output_path)
        duration = len(data) / sr
        log(f"TTS fallback: {duration:.0f}s in {elapsed:.1f}s")
        return output_path, duration

    @staticmethod
    def step_charts(stock_mentions: List[Tuple[str, str]], output_dir: str) -> List[Tuple[str, str]]:
        if not stock_mentions:
            return []
        chart_videos = []
        for name, symbol in stock_mentions[:3]:
            try:
                cv = PipelineSteps._gen_chart(name, symbol, output_dir)
                if cv:
                    chart_videos.append((name, cv))
            except Exception as e:
                log(f"Chart failed for {name}: {e}")
        return chart_videos

    @staticmethod
    def _gen_chart(name: str, symbol: str, output_dir: str) -> Optional[str]:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="6mo")
        if hist.empty or len(hist) < 20:
            return None
        close_prices = hist["Close"].values
        dates = hist.index
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=60)
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#161b22")
        chart_dir = os.path.join(output_dir, "charts", name)
        os.makedirs(chart_dir, exist_ok=True)
        step = max(1, len(close_prices) // 300)
        frames = []
        for i in range(0, len(close_prices), step):
            ax.clear()
            data_up = close_prices[:i+1]
            dates_up = dates[:i+1]
            color = "#00d4aa" if data_up[-1] >= data_up[0] else "#ff6b6b"
            ax.plot(dates_up, data_up, color=color, linewidth=2.5, zorder=2)
            ax.fill_between(dates_up, data_up, alpha=0.1, color=color, zorder=1)
            cv = data_up[-1]
            ch = ((cv - data_up[0]) / data_up[0]) * 100
            ax.set_title(f"{name}  |  \u20b9{cv:.2f}  ({ch:+.2f}%)",
                        color="white", fontsize=28, pad=20, fontweight="bold")
            ax.tick_params(colors="#8b949e", labelsize=14)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.grid(True, alpha=0.15, color="#30363d")
            fp = os.path.join(chart_dir, f"frame_{i:04d}.png")
            fig.savefig(fp, facecolor="#0d1117", bbox_inches="tight", pad_inches=0.2)
            frames.append(fp)
        plt.close(fig)
        chart_video = os.path.join(chart_dir, f"{name}_chart.mp4")
        subprocess.run(["ffmpeg", "-y", "-framerate", "15",
            "-i", f"{chart_dir}/frame_%04d.png",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast", "-crf", "20", chart_video],
            capture_output=True, check=True, timeout=120)
        for f in frames:
            os.remove(f)
        return chart_video

    @staticmethod
    def step_download_footage(search_terms: List[str], output_dir: str,
                               target_duration: float) -> List[str]:
        import requests
        os.makedirs(output_dir, exist_ok=True)
        download_urls = []
        for term in search_terms:
            if len(download_urls) >= 60:
                break
            url = f"https://api.pexels.com/videos/search?query={term}&orientation=landscape&per_page=15"
            try:
                resp = requests.get(url, headers={"Authorization": PEXELS_KEY}, timeout=15)
                data = resp.json()
                for v in data.get("videos", []):
                    dur = v.get("duration", 0)
                    if dur < 5: continue
                    for f in v.get("video_files", []):
                        if f.get("quality") == "hd" and f.get("width", 0) >= 1280:
                            download_urls.append((f["link"], dur))
                            break
            except: pass
        random.shuffle(download_urls)
        downloaded = []
        total = 0
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        for vurl, dur in download_urls:
            if total >= target_duration: break
            fname = os.path.join(output_dir, f"clip_{len(downloaded):04d}.mp4")
            try:
                r = requests.get(vurl, headers=headers, stream=True, timeout=30)
                if r.status_code == 200:
                    with open(fname, "wb") as f:
                        for chunk in r.iter_content(8192): f.write(chunk)
                    if os.path.getsize(fname) > 10000:
                        downloaded.append(fname)
                        total += min(dur, 12)
            except: pass
        log(f"Footage: {len(downloaded)} clips ({total:.0f}s)")
        return downloaded

    @staticmethod
    def step_combine_video(video_paths: List[str], chart_videos: List[Tuple[str, str]],
                            audio_duration: float, output_path: str) -> str:
        seg_dur = 10
        chart_clips = [c[1] for c in chart_videos]
        clips = []
        total = 0.0
        idx = 0
        while total < audio_duration:
            remaining = audio_duration - total
            sd = min(seg_dur, remaining)
            if chart_clips and idx % 3 == 0:
                clip_path = chart_clips[(idx // 3) % len(chart_clips)]
            else:
                clip_path = video_paths[idx % len(video_paths)] if video_paths else ""
            if clip_path and os.path.exists(clip_path):
                clips.append((clip_path, sd))
            total += sd
            idx += 1
        if not clips:
            fallback = output_path.replace(".mp4", "_fb.mp4")
            subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                f"color=c=0x001e32:s=1920x1080:d={audio_duration}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", fallback],
                capture_output=True, check=True, timeout=120)
            return fallback
        concat_file = "/tmp/_h_concat.txt"
        with open(concat_file, "w") as f:
            for cp, sd in clips:
                f.write(f"file '{cp}'\nduration {sd}\n")
        temp = output_path.replace(".mp4", "_t.mp4")
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file, "-c:v", "libx264", "-preset", "fast",
            "-pix_fmt", "yuv420p", "-crf", "22", "-threads", "4", temp],
            capture_output=True, check=True, timeout=600)
        subprocess.run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", temp,
            "-c:v", "libx264", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-t", str(audio_duration), "-crf", "22", "-threads", "4", output_path],
            capture_output=True, check=True, timeout=600)
        for f in [temp]:
            if os.path.exists(f): os.remove(f)
        return output_path

    @staticmethod
    def step_render_final(video_path: str, audio_path: str,
                           sentences: List[str], audio_duration: float,
                           avatar_path: str, output_path: str) -> str:
        total_chars = sum(len(s) for s in sentences)
        cps = total_chars / audio_duration if audio_duration > 0 else 10
        srt_lines = []
        ct = 0.0
        for i, sent in enumerate(sentences):
            if not sent.strip(): continue
            sd = max(1.0, len(sent) / cps)
            start = ct
            end = min(ct + sd, audio_duration)
            if start >= audio_duration: break
            def _fmt(sec):
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s = sec % 60
                return f"{h:02d}:{m:02d}:{s:06.3f}"
            srt_lines.append(f"{i+1}")
            srt_lines.append(f"{_fmt(start)} --> {_fmt(end)}")
            srt_lines.append(sent.strip())
            srt_lines.append("")
            ct = end

        srt_path = "/tmp/_h_subs.srt"
        with open(srt_path, "w") as f:
            f.write("\n".join(srt_lines))

        sub_entries = []
        for block in re.split(r'\n\n', "\n".join(srt_lines).strip()):
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                tm = re.match(r'(\d+:\d+:\d+[.,]\d+) --> (\d+:\d+:\d+[.,]\d+)', lines[1])
                if tm:
                    def _pts(s):
                        s = s.replace(",", ".")
                        p = s.split(":")
                        return int(p[0])*3600 + int(p[1])*60 + float(p[2])
                    sub_entries.append((_pts(tm.group(1)), _pts(tm.group(2)), "\n".join(lines[2:])))

        render_script = f'''import sys, os, math, json, time
import numpy as np
from PIL import Image, ImageEnhance
from PIL import Image as PILImage
from moviepy import CompositeVideoClip, VideoClip, VideoFileClip, TextClip

video = VideoFileClip("{video_path}")
duration = video.duration; fps = int(video.fps) if video.fps else 30
w, h = video.w, video.h

pil_img = Image.open("{avatar_path}").convert("RGB")
ow = int(w * 0.28); oh = min(int(ow * pil_img.height / pil_img.width), int(h * 0.45))
pil_img = pil_img.resize((ow, oh), Image.LANCZOS)
enhancer = ImageEnhance.Contrast(pil_img); pil_img = enhancer.enhance(1.1)
enhancer = ImageEnhance.Sharpness(pil_img); pil_img = enhancer.enhance(1.05)
avatar_arr = np.array(pil_img)
mx, my = int(w * 0.03), int(h * 0.02)
px, py = w - ow - mx, h - oh - my

def mk_av(t):
    br = 1.0 + 0.003 * math.sin(2 * math.pi * t / 3.0)
    cw = max(1, int(ow * br)); ch = max(1, int(oh * br))
    return np.array(PILImage.fromarray(avatar_arr).resize((cw, ch), PILImage.LANCZOS))

av_clip = (VideoClip(mk_av, duration=duration)
    .with_position(lambda t: (px, py + 1.5 * math.sin(2 * math.pi * t / 2.5)))
    .with_duration(duration))

subs = {json.dumps(sub_entries)}
ovs = [av_clip]
fp = "/System/Library/Fonts/Helvetica.ttc"

for start, end, text in subs:
    sd = end - start
    if sd <= 0: continue
    if len(text) > 60:
        words = text.split()
        lines, line = [], ""
        for w in words:
            test = f"{{line}} {{w}}".strip()
            if len(test) > 50: lines.append(line); line = w
            else: line = test
        if line: lines.append(line)
        text = "\\n".join(lines)
    ovs.append(
        TextClip(text=text, font_size=28, color="white", font=fp,
                 stroke_color="black", stroke_width=2, method="label")
        .with_position(("center", h * 0.85))
        .with_start(start).with_duration(sd)
    )

final = CompositeVideoClip([video] + ovs)
final.write_videofile("{output_path}", codec="libx264",
                       audio_codec="aac", fps=fps, threads=4)
video.close(); final.close()
'''
        render_file = "/tmp/_h_render.py"
        with open(render_file, "w") as f:
            f.write(render_script)
        t0 = time.time()
        r = subprocess.run([PY311, render_file], capture_output=True, text=True, timeout=7200)
        elapsed = time.time() - t0
        if r.returncode != 0 or not os.path.exists(output_path):
            raise RuntimeError(f"Render failed: {r.stderr[:500]}")
        log(f"Render: {os.path.getsize(output_path)/1e6:.0f}MB in {elapsed:.1f}s")
        return output_path


# ── Self-Fixing ──────────────────────────────────────────────────

def diagnose_failure(step_name: str, error: str) -> dict:
    prompt = f"""A video pipeline step failed. Diagnose.
Step: {step_name}
Error: {error[:300]}
Reply JSON with: likely_cause, fix_hint, should_retry, adjust_params"""
    try:
        import requests
        resp = requests.post("https://text.pollinations.ai/",
            json={"messages": [{"role": "user", "content": prompt}],
                  "model": "openai", "max_tokens": 300},
            timeout=30)
        if resp.status_code == 200:
            text = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            text = re.sub(r"^```(?:json)?\s*", "", text.strip())
            text = re.sub(r"\s*```$", "", text)
            return json.loads(text)
    except: pass
    return {"likely_cause": "unknown", "fix_hint": "retry",
            "should_retry": True, "adjust_params": {}}


def retry_step(step_fn, step_name: str, max_retries: int = 3,
               *args, **kwargs) -> Tuple[StepResult, any]:
    result = StepResult(name=step_name, status="fail")
    for attempt in range(max_retries):
        try:
            t0 = time.time()
            output = step_fn(*args, **kwargs)
            elapsed = time.time() - t0
            result.status = "ok"
            result.duration = elapsed
            result.retry_count = attempt
            result.output = str(output)[:200] if output else ""
            return result, output
        except Exception as e:
            log(f"{step_name}: attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                diag = diagnose_failure(step_name, str(e))
                wait = (attempt + 1) * 15
                log(f"  Diagnosis: {diag.get('likely_cause', 'unknown')}")
                log(f"  Retrying in {wait}s...")
                time.sleep(wait)
    result.error = f"Failed after {max_retries} attempts"
    return result, None


# ── EOD Report ───────────────────────────────────────────────────

def build_eod_report(steps: List[StepResult], today: str, stats: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ok = sum(1 for s in steps if s.status == "ok")
    fail = sum(1 for s in steps if s.status == "fail")
    skip = sum(1 for s in steps if s.status == "skipped")
    lines = [
        "=" * 60,
        f"  HERMES PIPELINE EOD REPORT",
        f"  Date: {today}  |  Generated: {now}",
        "=" * 60, "",
        "SUMMARY",
        "-" * 40,
        f"  Steps succeeded: {ok}  |  Failed: {fail}  |  Skipped: {skip}",
        f"  Attention needed: {'YES' if fail > 0 else 'NO'}",
        f"  Hermes: {stats.get('topics',0)} topics, {stats.get('skills',0)} skills, "
        f"{stats.get('pending_queue',0)} queue, {stats.get('pipeline_runs',0)} runs", "",
        "STEP DETAILS", "-" * 40,
    ]
    for step in steps:
        icon = {"ok": "✅", "fail": "❌", "skipped": "⏭️"}.get(step.status, "❓")
        lines.append(f"  {icon} {step.name} [{step.status}]")
        if step.duration: lines.append(f"     Duration: {step.duration:.1f}s")
        if step.error: lines.append(f"     Error: {step.error}")
        if step.output: lines.append(f"     Output: {step.output}")
        if step.retry_count: lines.append(f"     Retries: {step.retry_count}")
        lines.append("")
    if fail > 0:
        lines.append("ATTENTION REQUIRED"); lines.append("-" * 40)
        for step in steps:
            if step.status == "fail":
                lines.append(f"  ❌ {step.name}: {step.error}")
        lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def send_eod_report(content: str, today: str):
    recipient = os.environ.get("EOD_EMAIL_RECIPIENT", "")
    password = os.environ.get("EOD_EMAIL_PASSWORD", "")
    report_dir = os.path.join(BASE_OUTPUT, today)
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"EOD_REPORT_{today}.md")
    with open(report_path, "w") as f:
        f.write(content)
    log(f"EOD report saved: {report_path}")
    if recipient and password:
        try:
            msg = MIMEMultipart()
            msg["From"] = "alex@thecompounder.in"
            msg["To"] = recipient
            msg["Subject"] = f"Hermes Pipeline EOD - {today}"
            msg.attach(MIMEText(content, "plain"))
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.starttls()
                server.login("alex@thecompounder.in", password)
                server.send_message(msg)
            log("EOD report emailed!")
        except Exception as e:
            log(f"EOD email failed: {e}")


# ── Hermes News Cycle ────────────────────────────────────────────

def run_news_cycle(kb: KnowledgeBase) -> dict:
    log("Hermes: News cycle started")
    fetcher = NewsFetcher()
    all_news = fetcher.fetch_all()
    log(f"Hermes: Fetched {len(all_news)} news items")
    relevant = 0
    for item in all_news:
        import requests
        try:
            resp = requests.post("https://text.pollinations.ai/",
                json={"messages": [{"role": "user", "content":
                    f"Rate relevance 0.0-1.0 for Indian investing channel. "
                    f"Title: {item.title[:200]}. Reply ONLY JSON like "
                    f'{{"relevance": 0.0, "topics": ["a","b"]}}'}],
                    "model": "openai", "max_tokens": 100},
                timeout=15)
            if resp.status_code == 200:
                text = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "{}")
                text = re.sub(r"^```(?:json)?\s*", "", text.strip())
                text = re.sub(r"\s*```$", "", text)
                data = json.loads(text)
                item.relevance_score = max(0.0, min(1.0, float(data.get("relevance", 0.0))))
                item.topics = data.get("topics", [])
                if isinstance(item.topics, str):
                    item.topics = [t.strip() for t in item.topics.split(",")]
        except: pass
        if item.relevance_score >= 0.4:
            kb.store_news(item)
            relevant += 1
            for topic in item.topics:
                kb.upsert_topic(topic)
    log(f"Hermes: {relevant} relevant items stored")

    unprocessed = kb.get_unprocessed_news(limit=5)
    suggestions = 0
    for news_item in unprocessed:
        try:
            import requests
            resp = requests.post("https://text.pollinations.ai/",
                json={"messages": [{"role": "user", "content":
                    f"Suggest 1 YouTube short topic about: {news_item['title'][:200]}. "
                    f"Hook options: stat_shock|myth_bust|story_open|question|contrast|"
                    f"challenge|what_if|relatable|visual|bold_claim. "
                    f'Reply JSON: {{"topic":"...","hook_category":"...","rationale":"..."}}'}],
                    "model": "openai", "max_tokens": 200},
                timeout=15)
            if resp.status_code == 200:
                text = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "{}")
                text = re.sub(r"^```(?:json)?\s*", "", text.strip())
                text = re.sub(r"\s*```$", "", text)
                data = json.loads(text)
                suggestion = ContentSuggestion(
                    id=str(uuid.uuid4()), topic=data.get("topic", ""),
                    hook_category=data.get("hook_category", ""),
                    rationale=data.get("rationale", ""),
                    source_news_id=news_item["id"],
                    created_at=datetime.now().isoformat(),
                )
                kb.enqueue(suggestion)
                suggestions += 1
                kb.mark_news_processed(news_item["id"])
        except: pass
    log(f"Hermes: {suggestions} new content suggestions")
    return {"fetched": len(all_news), "relevant": relevant, "suggestions": suggestions}


# ── Main Pipeline ────────────────────────────────────────────────

def run_pipeline(script_path: str, kb: KnowledgeBase) -> List[StepResult]:
    log(f"\n{'='*60}")
    log(f"  HERMES PIPELINE - {date.today().isoformat()}")
    log(f"{'='*60}\n")

    steps: List[StepResult] = []

    # Step 1: Script Prep
    log("— Step 1: Script Prep —")
    r1, data = retry_step(PipelineSteps.step_script_prep, "Script Prep", 2, script_path)
    steps.append(r1)
    if r1.status != "ok":
        return steps
    sanitized, sentences, stock_mentions = data

    # Step 2: TTS
    log("— Step 2: TTS (Alex Voice) —")
    audio_out = "/tmp/_h_tts.mp3"
    # Try edge-tts first (fast, reliable), fallback to Coqui
    r2, tts_res = retry_step(PipelineSteps.step_tts_fallback, "TTS (edge)", 2, sanitized, audio_out)
    if r2.status != "ok":
        log("edge-tts failed, trying Coqui fallback...")
        r2, tts_res = retry_step(PipelineSteps.step_tts, "TTS (Coqui)", 1, sanitized, audio_out)
    steps.append(r2)
    if r2.status != "ok":
        return steps
    audio_path, audio_duration = tts_res

    # Step 3: Charts
    log("— Step 3: Animated Charts —")
    chart_dir = "/tmp/_h_charts"
    r3, chart_videos = retry_step(PipelineSteps.step_charts, "Charts", 2, stock_mentions, chart_dir)
    steps.append(r3)

    # Step 4: Footage
    log("— Step 4: Download Footage —")
    search_terms = [
        "Indian stock market trading", "Nifty 50 exchange", "business news India",
        "stock chart analysis", "corporate office buildings", "financial data graphs",
        "Mumbai business district", "share market India",
    ] + [f"{name} stock" for name, _ in stock_mentions[:3]]
    footage_dir = "/tmp/_h_footage"
    r4, videos = retry_step(PipelineSteps.step_download_footage, "Footage", 3,
                             search_terms, footage_dir, audio_duration)
    steps.append(r4)
    if not videos:
        log("No footage, will use fallback")

    # Step 5: Combine
    log("— Step 5: Combine Videos —")
    combined_out = "/tmp/_h_combined.mp4"
    r5, combined_path = retry_step(PipelineSteps.step_combine_video, "Combine", 2,
                                    videos or [], chart_videos or [], audio_duration, combined_out)
    steps.append(r5)
    if r5.status != "ok":
        return steps

    # Step 6: Render Final
    log("— Step 6: Final Render —")
    import glob as _glob
    _av_files = _glob.glob(os.path.join(AVATAR_DIR, "*.jpg")) + _glob.glob(os.path.join(AVATAR_DIR, "*.png"))
    avatar_path = _av_files[0] if _av_files else os.path.join(AVATAR_DIR, "placeholder.jpg")
    log(f"Avatar: {avatar_path}")
    if not os.path.exists(avatar_path):
        avatar_path = ""
        log("No avatar image")

    video_dir = create_output_structure(date.today().isoformat(), "en",
                                         f"market_update_{date.today().isoformat()}")
    final_out = os.path.join(video_dir, "final.mp4")

    r6, final_path = retry_step(PipelineSteps.step_render_final, "Render", 2,
                                 combined_path, audio_path, sentences, audio_duration,
                                 avatar_path, final_out)
    steps.append(r6)

    if r6.status == "ok":
        log(f"\n✅ PIPELINE COMPLETE: {final_out}")
        log(f"   Size: {os.path.getsize(final_out)/1e6:.0f}MB")
    else:
        log("\n❌ Pipeline failed at render")

    return steps


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Hermes Pipeline Orchestrator")
    parser.add_argument("--news-only", action="store_true", help="Run news cycle only")
    parser.add_argument("--pipeline-only", action="store_true", help="Run pipeline only")
    args = parser.parse_args()

    kb = KnowledgeBase()
    run_id = str(uuid.uuid4())
    t0 = time.time()

    steps: List[StepResult] = []
    final_video_path = ""

    if not args.pipeline_only:
        news_results = run_news_cycle(kb)

    if not args.news_only:
        # Find script
        script_path = SCRIPT_FILE
        if not os.path.exists(script_path):
            tasks_dir = os.path.join(PROJECT_DIR, "storage/tasks")
            if os.path.exists(tasks_dir):
                for td in os.listdir(tasks_dir):
                    sj = os.path.join(tasks_dir, td, "script.json")
                    if os.path.exists(sj):
                        try:
                            data = json.load(open(sj))
                            script_text = data.get("script", "")
                            if len(script_text) > 1000:
                                script_path = f"/tmp/_h_script_{td}.txt"
                                with open(script_path, "w") as f:
                                    f.write(script_text)
                                break
                        except: pass

        if os.path.exists(script_path):
            steps = run_pipeline(script_path, kb)
            for s in steps:
                if s.status == "ok" and s.output and "final" in s.output.lower():
                    final_video_path = s.output
        else:
            log("No script found!")

    elapsed = time.time() - t0
    stats = kb.get_stats()
    report = build_eod_report(steps, date.today().isoformat(), stats)
    send_eod_report(report, date.today().isoformat())

    # Store run in KB
    kb.record_pipeline_run(run_id, date.today().isoformat(),
                           "ok" if all(s.status == "ok" for s in steps) else "partial",
                           json.dumps([asdict(s) for s in steps]),
                           final_video_path, elapsed)

    # Learn from failures
    for step in steps:
        if step.status == "fail" and step.error:
            sk = Skill(
                name=f"fix_{step.name.lower().replace(' ','_')[:40]}",
                description=f"Auto-fix: {step.error[:100]}",
                pattern=json.dumps({"failed_step": step.name, "error": step.error[:100]}),
            )
            kb.store_skill(sk)

    log(f"\nTotal time: {elapsed:.1f}s")
    log(f"Output: {final_video_path if final_video_path else 'N/A'}")
    return 0 if all(s.status == "ok" for s in steps) else 1


if __name__ == "__main__":
    sys.exit(main())
