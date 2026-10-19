"""
Hermes Agent — Self-improving news monitoring agent for the Investing, Not Trading channel.

Inspired by Nous Research's Hermes Agent principles:
- Persistent cross-session knowledge
- Closed learning loop (act → observe → improve)
- Autonomous skill creation from experience
- Knowledge base that grows over time

Agent monitors Indian financial news, identifies topics aligned with
"Investing, Not Trading" message, builds a knowledge base of what works,
and auto-queues content generation.
"""

import datetime
import json
import os
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urlencode

import requests
from loguru import logger

from app.config import config
from app.services import llm

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "hermes_agent.db")
CONTENT_QUEUE_FILE = os.path.join(DB_DIR, "content_queue.json")

# ---------------------------------------------------------------------------
# Schema / Data Classes
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Knowledge Base (SQLite)
# ---------------------------------------------------------------------------

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
                    id TEXT PRIMARY KEY,
                    topic TEXT UNIQUE,
                    category TEXT,
                    first_seen TEXT,
                    last_covered TEXT,
                    coverage_count INTEGER DEFAULT 0,
                    avg_engagement REAL DEFAULT 0.0,
                    performance_score REAL DEFAULT 0.5
                );
                CREATE TABLE IF NOT EXISTS news (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    source TEXT,
                    url TEXT UNIQUE,
                    summary TEXT,
                    published TEXT,
                    topics TEXT,
                    relevance_score REAL DEFAULT 0.0,
                    processed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS content_queue (
                    id TEXT PRIMARY KEY,
                    topic TEXT,
                    hook_category TEXT,
                    target_languages TEXT,
                    rationale TEXT,
                    source_news_id TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT (datetime('now')),
                    generated_at TEXT
                );
                CREATE TABLE IF NOT EXISTS skills (
                    id TEXT PRIMARY KEY,
                    name TEXT UNIQUE,
                    description TEXT,
                    pattern TEXT,
                    success_count INTEGER DEFAULT 0,
                    fail_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now')),
                    last_used TEXT
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    content_queue_id TEXT,
                    engagement_score REAL,
                    views INTEGER DEFAULT 0,
                    likes INTEGER DEFAULT 0,
                    comments INTEGER DEFAULT 0,
                    shares INTEGER DEFAULT 0,
                    reported_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS agent_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            conn.commit()

    # --- Topic management ---
    def upsert_topic(self, topic: str, category: str = "general"):
        now = datetime.datetime.now().isoformat()
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

    def get_topics_by_performance(self, limit: int = 20) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM topics ORDER BY performance_score DESC, coverage_count DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_topics_by_category(self, category: str, limit: int = 10) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM topics WHERE category = ? ORDER BY last_covered DESC LIMIT ?",
                (category, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    # --- News management ---
    def store_news(self, item: NewsItem):
        with self._conn() as conn:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO news
                       (id, title, source, url, summary, published, topics, relevance_score, processed)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item.id or str(uuid.uuid4()),
                        item.title,
                        item.source,
                        item.url,
                        item.summary,
                        item.published,
                        json.dumps(item.topics),
                        item.relevance_score,
                        1 if item.processed else 0,
                    ),
                )
                conn.commit()
            except Exception as e:
                logger.warning(f"store_news failed: {e}")

    def get_unprocessed_news(self, limit: int = 10) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM news WHERE processed = 0 ORDER BY relevance_score DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_news_processed(self, news_id: str):
        with self._conn() as conn:
            conn.execute("UPDATE news SET processed = 1 WHERE id = ?", (news_id,))
            conn.commit()

    def get_recent_news(self, days: int = 7, limit: int = 50) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM news
                   WHERE published >= datetime('now', '-? days')
                   ORDER BY relevance_score DESC, published DESC LIMIT ?""",
                (days, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    # --- Content Queue ---
    def enqueue(self, suggestion: ContentSuggestion):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO content_queue
                   (id, topic, hook_category, target_languages, rationale, source_news_id, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    suggestion.id or str(uuid.uuid4()),
                    suggestion.topic,
                    suggestion.hook_category,
                    json.dumps(suggestion.target_languages),
                    suggestion.rationale,
                    suggestion.source_news_id,
                    suggestion.status,
                    suggestion.created_at or datetime.datetime.now().isoformat(),
                ),
            )
            conn.commit()

    def get_pending_queue(self, limit: int = 10) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM content_queue WHERE status = 'pending' ORDER BY created_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_queue_done(self, queue_id: str):
        with self._conn() as conn:
            conn.execute(
                "UPDATE content_queue SET status = 'generated', generated_at = datetime('now') WHERE id = ?",
                (queue_id,),
            )
            conn.commit()

    # --- Skills ---
    def store_skill(self, skill: Skill):
        with self._conn() as conn:
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO skills
                       (id, name, description, pattern, success_count, fail_count, created_at, last_used)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        skill.id or str(uuid.uuid4()),
                        skill.name,
                        skill.description,
                        skill.pattern,
                        skill.success_count,
                        skill.fail_count,
                        skill.created_at or datetime.datetime.now().isoformat(),
                        skill.last_used or datetime.datetime.now().isoformat(),
                    ),
                )
                conn.commit()
            except Exception as e:
                logger.warning(f"store_skill failed: {e}")

    def get_skills(self) -> List[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM skills ORDER BY success_count DESC, fail_count ASC"
            ).fetchall()
            return [dict(row) for row in rows]

    def update_skill_outcome(self, skill_name: str, success: bool):
        with self._conn() as conn:
            if success:
                conn.execute(
                    "UPDATE skills SET success_count = success_count + 1, last_used = datetime('now') WHERE name = ?",
                    (skill_name,),
                )
            else:
                conn.execute(
                    "UPDATE skills SET fail_count = fail_count + 1, last_used = datetime('now') WHERE name = ?",
                    (skill_name,),
                )
            conn.commit()

    # --- Feedback ---
    def record_feedback(self, queue_id: str, engagement: float, views: int = 0,
                        likes: int = 0, comments: int = 0, shares: int = 0):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO feedback
                   (id, content_queue_id, engagement_score, views, likes, comments, shares)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), queue_id, engagement, views, likes, comments, shares),
            )
            # Update topic performance
            conn.execute("""
                UPDATE topics SET performance_score = (
                    SELECT AVG(engagement_score) FROM feedback
                    WHERE content_queue_id IN (
                        SELECT id FROM content_queue WHERE topic = topics.topic
                    )
                ), avg_engagement = (
                    SELECT AVG(engagement_score) FROM feedback
                    WHERE content_queue_id IN (
                        SELECT id FROM content_queue WHERE topic = topics.topic
                    )
                )
            """)
            conn.commit()

    # --- Agent State ---
    def get_state(self, key: str, default: str = "") -> str:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value FROM agent_state WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else default

    def set_state(self, key: str, value: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO agent_state (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# News Sources (free, no API key)
# ---------------------------------------------------------------------------

class NewsFetcher:
    """Fetches Indian financial news from free sources."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def fetch_rss(self, url: str, source_name: str) -> List[NewsItem]:
        """Fetch and parse an RSS feed."""
        try:
            import xml.etree.ElementTree as ET
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            items = []
            # Handle both RSS 2.0 and Atom
            for entry in root.iter("item"):
                title = entry.findtext("title", "")
                link = entry.findtext("link", "")
                desc = entry.findtext("description", "")
                pub_date = entry.findtext("pubDate", "")
                items.append(NewsItem(
                    title=title.strip(),
                    source=source_name,
                    url=link.strip(),
                    summary=desc.strip(),
                    published=pub_date.strip(),
                ))
            for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
                title = entry.findtext("{http://www.w3.org/2005/Atom}title", "")
                link_el = entry.find("{http://www.w3.org/2005/Atom}link")
                link = link_el.attrib.get("href", "") if link_el is not None else ""
                summary = entry.findtext("{http://www.w3.org/2005/Atom}summary", "")
                published = entry.findtext("{http://www.w3.org/2005/Atom}published", "")
                items.append(NewsItem(
                    title=title.strip(),
                    source=source_name,
                    url=link.strip(),
                    summary=summary.strip(),
                    published=published.strip(),
                ))

            logger.info(f"fetched {len(items)} items from {source_name}")
            return items
        except Exception as e:
            logger.warning(f"failed to fetch {source_name}: {e}")
            return []

    def fetch_indian_news(self) -> List[NewsItem]:
        """Fetch from Indian financial news RSS feeds."""
        feeds = [
            ("https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms", "Economic Times"),
            ("https://www.moneycontrol.com/rss/business.xml", "Moneycontrol"),
            ("http://feeds.feedburner.com/indiainfoline-news", "India Infoline"),
            ("https://www.livemint.com/rss/money", "LiveMint"),
        ]

        all_items = []
        for feed_url, source in feeds:
            all_items.extend(self.fetch_rss(feed_url, source))

        return all_items

    def search_gdelt(self, query: str = "Indian stock market", max_results: int = 25) -> List[NewsItem]:
        """Fetch from GDELT Project (free global news monitor)."""
        try:
            url = (
                f"https://api.gdeltproject.org/api/v2/doc/doc?"
                f"query={quote(query)}&mode=artlist&format=json&maxrecords={max_results}"
                f"&timespan=1d&sort=date"
            )
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            items = []
            for article in data.get("articles", []):
                items.append(NewsItem(
                    title=article.get("title", ""),
                    source=article.get("domain", "GDELT"),
                    url=article.get("url", ""),
                    summary=article.get("snippet", ""),
                    published=article.get("seendate", ""),
                ))
            logger.info(f"fetched {len(items)} items from GDELT ({query})")
            return items
        except Exception as e:
            logger.warning(f"GDELT fetch failed: {e}")
            return []


# ---------------------------------------------------------------------------
# Agent Brain (LLM-powered analysis)
# ---------------------------------------------------------------------------

class AgentBrain:
    """LLM-powered analysis and decision making."""

    RELEVANCE_PROMPT = """Rate relevance for Indian stock market education channel (0.0-1.0):
1.0=perfect investing education 0.7=good market topic 0.4=moderate 0.1=weak 0.0=irrelevant

Title: {title}
Summary: {summary}

Reply ONLY with valid JSON: {{"relevance": 0.0, "topics": ["topic1", "topic2"]}}"""

    SUGGESTION_PROMPT = """Suggest 1 YouTube short topic from this news for "Investing, Not Trading" channel.

Hook options: stat_shock | myth_bust | story_open | question | contrast | challenge | what_if | relatable | visual | bold_claim

Title: {title}
Summary: {summary}

Reply ONLY with valid JSON: {{"topic": "...", "hook_category": "...", "rationale": "..."}}"""

    ANALYZE_FAILURE_PROMPT = """A short had low engagement. Diagnose.

Topic: {topic}
Hook: {hook_category}
Rationale: {rationale}

Reply ONLY with valid JSON: {{"likely_issue": "...", "improvement": "...", "new_category": "..."}}"""

    def __init__(self):
        pass

    def _extract_json(self, text: str) -> dict:
        """Extract and parse JSON from LLM response, handling markdown wrapping."""
        text = text.strip()

        # Remove markdown code block fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try finding {...} in the text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        logger.warning(f"could not parse JSON from: {text[:200]}")
        return {}

    def analyze_relevance(self, title: str, summary: str) -> Tuple[float, List[str]]:
        prompt = self.RELEVANCE_PROMPT.format(title=title[:200], summary=summary[:500])
        try:
            response = llm._generate_response(prompt=prompt)
            data = self._extract_json(response)
            if not data:
                return 0.0, []
            relevance = max(0.0, min(1.0, float(data.get("relevance", 0.0))))
            topics = data.get("topics", [])
            if isinstance(topics, str):
                topics = [t.strip() for t in topics.split(",")]
            return relevance, topics
        except Exception as e:
            logger.warning(f"relevance analysis failed: {e}")
            return 0.0, []

    def suggest_content(self, title: str, summary: str) -> Optional[ContentSuggestion]:
        prompt = self.SUGGESTION_PROMPT.format(title=title[:200], summary=summary[:500])
        try:
            response = llm._generate_response(prompt=prompt)
            data = self._extract_json(response)
            if not data:
                return None
            return ContentSuggestion(
                id=str(uuid.uuid4()),
                topic=data.get("topic", ""),
                hook_category=data.get("hook_category", ""),
                rationale=data.get("rationale", ""),
                created_at=datetime.datetime.now().isoformat(),
            )
        except Exception as e:
            logger.warning(f"content suggestion failed: {e}")
            return None

    def analyze_failure(self, topic: str, hook_category: str, rationale: str) -> dict:
        prompt = self.ANALYZE_FAILURE_PROMPT.format(
            topic=topic, hook_category=hook_category, rationale=rationale
        )
        try:
            response = llm._generate_response(prompt=prompt)
            data = self._extract_json(response)
            return data if data else {"likely_issue": "unknown", "improvement": "try different hook", "new_category": "question"}
        except Exception as e:
            logger.warning(f"failure analysis failed: {e}")
            return {"likely_issue": "unknown", "improvement": "try different hook", "new_category": "question"}


# ---------------------------------------------------------------------------
# Main Agent
# ---------------------------------------------------------------------------

class HermesAgent:
    """Self-improving news monitoring agent for the Investing, Not Trading channel.

    Principles:
    1. Persistent knowledge base (SQLite) — remembers all topics, news, and performance
    2. Closed learning loop — evaluates content performance, learns what works
    3. Autonomous skill creation — creates reusable monitoring patterns
    4. Continuous improvement — every cycle improves topic selection and hook choices
    """

    def __init__(self):
        self.kb = KnowledgeBase()
        self.fetcher = NewsFetcher()
        self.brain = AgentBrain()
        self.running = False

    def cycle(self, max_news: int = 50, max_suggestions: int = 5) -> Dict:
        """Run one full cycle of the agent: fetch → analyze → suggest → learn."""
        start = time.time()
        results = {
            "news_fetched": 0,
            "news_relevant": 0,
            "suggestions": 0,
            "skills_used": 0,
            "errors": [],
        }

        # 1. FETCH news from all sources
        logger.info("[Hermes] Cycle start — fetching news...")
        all_news = self.fetcher.fetch_indian_news()
        gdelt_news = self.fetcher.search_gdelt("Indian stock market investing", 15)
        all_news.extend(gdelt_news)
        gdelt_nifty = self.fetcher.search_gdelt("Nifty Sensex investing", 10)
        all_news.extend(gdelt_nifty)
        results["news_fetched"] = len(all_news)
        logger.info(f"[Hermes] Fetched {len(all_news)} news items total")

        # 2. ANALYZE relevance and store
        for item in all_news[:max_news]:
            try:
                relevance, topics = self.brain.analyze_relevance(item.title, item.summary)
                item.relevance_score = relevance
                item.topics = topics
                item.id = str(uuid.uuid4())

                if relevance >= 0.4:
                    self.kb.store_news(item)
                    results["news_relevant"] += 1

                    # Upsert topics to knowledge base
                    for topic in topics:
                        category = self._categorize_topic(topic)
                        self.kb.upsert_topic(topic, category)
            except Exception as e:
                results["errors"].append(f"analyze: {e}")

        logger.info(f"[Hermes] Stored {results['news_relevant']} relevant items")

        # 3. SUGGEST content from unprocessed news
        unprocessed = self.kb.get_unprocessed_news(limit=10)
        for news_item in unprocessed[:max_suggestions]:
            try:
                suggestion = self.brain.suggest_content(
                    news_item["title"], news_item["summary"]
                )
                if suggestion:
                    suggestion.source_news_id = news_item["id"]
                    # Apply learned skills to modify hook category
                    applied_skill = self._apply_skills(suggestion)
                    if applied_skill:
                        results["skills_used"] += 1

                    self.kb.enqueue(suggestion)
                    results["suggestions"] += 1
                    self.kb.mark_news_processed(news_item["id"])
                    logger.info(f"[Hermes] Suggested: {suggestion.topic} ({suggestion.hook_category})")
            except Exception as e:
                results["errors"].append(f"suggest: {e}")

        # 4. LEARN from past performance (self-improvement loop)
        self._learn_cycle()

        elapsed = time.time() - start
        results["duration"] = round(elapsed, 2)
        self.kb.set_state("last_cycle", datetime.datetime.now().isoformat())
        self.kb.set_state("last_cycle_results", json.dumps(results))

        logger.info(f"[Hermes] Cycle complete: {results['suggestions']} suggestions in {elapsed:.1f}s")
        return results

    def _categorize_topic(self, topic: str) -> str:
        topic_lower = topic.lower()
        if any(w in topic_lower for w in ["nifty", "sensex", "index", "market"]):
            return "market"
        if any(w in topic_lower for w in ["sip", "mutual fund", "mf", "invest"]):
            return "investing"
        if any(w in topic_lower for w in ["stock", "share", "equity", "ipo"]):
            return "stocks"
        if any(w in topic_lower for w in ["economy", "gdp", "inflation", "rate"]):
            return "economy"
        if any(w in topic_lower for w in ["tax", "budget", "finance"]):
            return "personal_finance"
        if any(w in topic_lower for w in ["trade", "trading", "f&o", "derivative"]):
            return "trading"
        return "general"

    def _apply_skills(self, suggestion: ContentSuggestion) -> Optional[str]:
        """Apply learned skills to modify suggestion. Returns skill name if applied."""
        skills = self.kb.get_skills()
        best_skill = None
        best_score = 0

        for skill in skills:
            score = skill["success_count"] - skill["fail_count"] * 2
            if score > best_score and skill["success_count"] > 2:
                best_score = score
                best_skill = skill

        if best_skill and best_skill["pattern"]:
            try:
                pattern_data = json.loads(best_skill["pattern"])
                if "hook_category" in pattern_data:
                    suggestion.hook_category = pattern_data["hook_category"]
                if "topics" in pattern_data and suggestion.topic:
                    for kw, replacement in pattern_data["topics"].items():
                        if kw.lower() in suggestion.topic.lower():
                            suggestion.topic = suggestion.topic.replace(kw, replacement)
                return best_skill["name"]
            except (json.JSONDecodeError, TypeError):
                pass
        return None

    def _learn_cycle(self):
        """Self-improvement: analyze past content performance and create/update skills."""
        # Check if we have enough feedback to learn from
        with sqlite3.connect(self.kb.db_path) as conn:
            recent_feedback = conn.execute(
                """SELECT cq.topic, cq.hook_category, cq.rationale, f.engagement_score
                   FROM feedback f
                   JOIN content_queue cq ON f.content_queue_id = cq.id
                   ORDER BY f.reported_at DESC LIMIT 10"""
            ).fetchall()

        if len(recent_feedback) < 3:
            return

        # Find low-performing content and analyze why
        low_performers = [f for f in recent_feedback if f[3] and float(f[3]) < 0.3]
        for item in low_performers[:3]:
            topic, hook, rationale, _ = item
            analysis = self.brain.analyze_failure(topic, hook, rationale)

            # Create or update a skill based on failure analysis
            skill_name = f"avoid_{hook}_{topic.split()[0]}"
            skill = Skill(
                name=skill_name[:50],
                description=analysis.get("improvement", ""),
                pattern=json.dumps({
                    "hook_category": analysis.get("new_category", hook),
                    "avoid_hook": hook,
                }),
            )
            self.kb.store_skill(skill)
            logger.info(f"[Hermes] Created skill '{skill_name}' from failure analysis")

        # Find high-performing content and create positive skills
        high_performers = [f for f in recent_feedback if f[3] and float(f[3]) > 0.7]
        for item in high_performers[:3]:
            topic, hook, rationale, _ = item
            skill_name = f"do_{hook}_{topic.split()[0]}"
            skill = Skill(
                name=skill_name[:50],
                description=f"High-performing pattern: {hook} hook on {topic} topics",
                pattern=json.dumps({
                    "hook_category": hook,
                }),
                success_count=1,
            )
            self.kb.store_skill(skill)
            logger.info(f"[Hermes] Created skill '{skill_name}' from success pattern")

    def get_queue(self, limit: int = 10) -> List[dict]:
        """Get pending content suggestions."""
        return self.kb.get_pending_queue(limit)

    def enqueue_content(self, topic: str, hook_category: str = "question",
                        rationale: str = "") -> str:
        """Manually enqueue a content suggestion."""
        suggestion = ContentSuggestion(
            id=str(uuid.uuid4()),
            topic=topic,
            hook_category=hook_category,
            rationale=rationale or f"Manual suggestion: {topic}",
            created_at=datetime.datetime.now().isoformat(),
        )
        self.kb.enqueue(suggestion)
        self.kb.upsert_topic(topic)
        logger.info(f"[Hermes] Manual enqueue: {topic}")
        return suggestion.id

    def record_performance(self, queue_id: str, views: int, likes: int,
                           comments: int, shares: int):
        """Record content performance for the learning loop."""
        total_engagement = views + likes * 2 + comments * 3 + shares * 5
        engagement_score = min(1.0, total_engagement / 10000) if views > 0 else 0.5
        self.kb.record_feedback(queue_id, engagement_score, views, likes, comments, shares)

        # Update skill success/fail based on engagement
        with sqlite3.connect(self.kb.db_path) as conn:
            row = conn.execute(
                "SELECT topic, hook_category FROM content_queue WHERE id = ?", (queue_id,)
            ).fetchone()
        if row:
            topic, hook = row
            skill_name = f"do_{hook}_{topic.split()[0]}"
            if engagement_score >= 0.5:
                self.kb.update_skill_outcome(skill_name, success=True)
            else:
                self.kb.update_skill_outcome(f"avoid_{hook}_{topic.split()[0]}", success=True)

    def get_stats(self) -> Dict:
        """Get agent statistics."""
        with sqlite3.connect(self.kb.db_path) as conn:
            topic_count = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
            news_count = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
            queue_count = conn.execute(
                "SELECT COUNT(*) FROM content_queue WHERE status = 'pending'"
            ).fetchone()[0]
            skill_count = conn.execute("SELECT COUNT(*) FROM skills").fetchone()[0]
            feedback_count = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]

        return {
            "topics": topic_count,
            "news_articles": news_count,
            "pending_queue": queue_count,
            "skills": skill_count,
            "feedback_entries": feedback_count,
            "last_cycle": self.kb.get_state("last_cycle", "never"),
        }


# Singleton instance
_agent: Optional[HermesAgent] = None


def get_agent() -> HermesAgent:
    global _agent
    if _agent is None:
        _agent = HermesAgent()
    return _agent
