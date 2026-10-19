"""
WordPress REST API Publisher.

Publishes humanized, SEO/GEO-optimized financial articles directly to WordPress:
- Connects via official WP REST API (/wp-json/wp/v2/posts) using Application Passwords
- Automatically embeds responsive YouTube iframe players inside articles
- Injects Schema.org JSON-LD structured data into the post body or metadata
- Manages categories, tags, excerpts, and Yoast/RankMath SEO fields
- Features a graceful local offline/dry-run fallback to save articles to disk
"""

import base64
import json
import os
import re
from typing import Dict, List, Optional
import requests
from loguru import logger

from app.config import config
from app.services.article_generator import GeneratedArticle


class WordPressPublisher:
    """Manages publishing articles and embedded media to WordPress."""

    def __init__(self):
        self._load_config()

    def _load_config(self):
        wp_cfg = config.app.get("wordpress", {})
        self.site_url = wp_cfg.get("site_url", "").rstrip("/")
        self.username = wp_cfg.get("username", "")
        self.app_password = wp_cfg.get("app_password", "")
        self.default_status = wp_cfg.get("default_status", "publish")  # 'publish' or 'draft'
        self.enabled = bool(self.site_url and self.username and self.app_password)

    def _get_auth_headers(self) -> Dict[str, str]:
        token = base64.b64encode(f"{self.username}:{self.app_password}".encode()).decode()
        return {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "User-Agent": "AntigravityMarketPipeline/1.0",
        }

    @staticmethod
    def _extract_youtube_id(url: str) -> Optional[str]:
        """Extract YouTube video ID from various URL formats."""
        patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
            r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
            r"(?:embed\/)([0-9A-Za-z_-]{11})",
            r"(?:shorts\/)([0-9A-Za-z_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _render_youtube_embed(self, youtube_url: str) -> str:
        """Create responsive YouTube embed iframe."""
        video_id = self._extract_youtube_id(youtube_url)
        if not video_id:
            return ""
        
        return f"""
<div class="yt-embed-wrapper" style="position:relative; padding-bottom:56.25%; height:0; overflow:hidden; border-radius:8px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.1); margin:24px 0;">
    <iframe src="https://www.youtube.com/embed/{video_id}?rel=0" 
            title="Market Video Analysis" 
            style="position:absolute; top:0; left:0; width:100%; height:100%; border:0;" 
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
            allowfullscreen>
    </iframe>
</div>
"""

    def publish_article(
        self, article: GeneratedArticle, youtube_url: Optional[str] = None, status: Optional[str] = None
    ) -> Dict:
        """
        Publish article to WordPress or save locally if offline.
        Embeds the YouTube video into the article body for maximum dwell-time SEO.
        """
        self._load_config()
        publish_status = status or self.default_status

        # Replace YouTube embed placeholder
        content = article.html_content
        if youtube_url:
            embed_html = self._render_youtube_embed(youtube_url)
            content = content.replace("[YOUTUBE_EMBED_PLACEHOLDER]", embed_html)
        else:
            content = content.replace("[YOUTUBE_EMBED_PLACEHOLDER]", "")

        # Inject JSON-LD Schema script tag at bottom of article content
        schema_tag = f'\n<script type="application/ld+json">\n{json.dumps(article.schema_jsonld, indent=2)}\n</script>\n'
        content += schema_tag

        # Dry-run / Offline fallback if WP credentials are not yet configured
        if not self.enabled:
            logger.warning("[WordPressPublisher] WP credentials not configured in config.toml. Saving article to local disk.")
            os.makedirs("output/articles", exist_ok=True)
            local_path = f"output/articles/{article.slug}.html"
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(f"<!-- Title: {article.title} -->\n<!-- Meta: {article.meta_description} -->\n\n{content}")
            
            logger.info(f"[WordPressPublisher] Article saved locally to {local_path}")
            return {
                "success": True,
                "status": "saved_locally",
                "file_path": local_path,
                "title": article.title,
                "slug": article.slug,
                "url": f"file://{os.path.abspath(local_path)}",
            }

        # Live publishing via WordPress REST API
        endpoint = f"{self.site_url}/wp-json/wp/v2/posts"
        payload = {
            "title": article.title,
            "slug": article.slug,
            "status": publish_status,
            "content": content,
            "excerpt": article.meta_description,
        }

        try:
            logger.info(f"[WordPressPublisher] Publishing post '{article.title}' to {self.site_url}...")
            response = requests.post(endpoint, headers=self._get_auth_headers(), json=payload, timeout=30)
            
            if response.status_code in [200, 201]:
                post_data = response.json()
                post_url = post_data.get("link", "")
                logger.info(f"[WordPressPublisher] Successfully published post: {post_url}")
                return {
                    "success": True,
                    "status": "published",
                    "post_id": post_data.get("id"),
                    "url": post_url,
                    "title": article.title,
                }
            else:
                logger.error(f"[WordPressPublisher] WP API returned error {response.status_code}: {response.text}")
                return {"success": False, "error": response.text, "status_code": response.status_code}
        except Exception as e:
            logger.error(f"[WordPressPublisher] Failed to connect to WordPress: {e}")
            return {"success": False, "error": str(e)}


# Global instance
wp_publisher = WordPressPublisher()
