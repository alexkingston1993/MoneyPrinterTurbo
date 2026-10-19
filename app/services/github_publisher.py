"""
GitHub & Vercel Publisher.

Publishes humanized, SEO/GEO-optimized market articles directly to a GitHub repository:
- Connects via GitHub REST API (using a Personal Access Token) or local Git CLI
- Generates clean Markdown with Frontmatter (YAML)
- Triggers automatic instant zero-cost deployments on Vercel
- Embeds YouTube video URLs directly in frontmatter and article markdown
- 100% serverless, zero hosting costs, 100/100 Core Web Vitals
"""

import base64
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional
import requests
from loguru import logger

from app.config import config
from app.services.article_generator import GeneratedArticle


class GitHubVercelPublisher:
    """Manages publishing articles to GitHub for automatic Vercel deployment."""

    def __init__(self):
        self._load_config()

    def _load_config(self):
        gh_cfg = config._cfg.get("github", {}) or config.app.get("github", {})
        self.repo = os.getenv("GITHUB_REPO", gh_cfg.get("repo", "alexkingston1993/MoneyPrinterTurbo"))
        self.branch = gh_cfg.get("branch", "main")
        self.token = os.getenv("GITHUB_TOKEN", gh_cfg.get("token", ""))
        self.posts_dir = gh_cfg.get("posts_dir", "content/posts").strip("/")
        self.enabled = bool(self.repo and self.token)

    def _update_local_posts_index(self, article: GeneratedArticle, youtube_url: Optional[str] = None):
        """Update content/posts.json manifest with the latest article."""
        os.makedirs("content", exist_ok=True)
        manifest_path = "content/posts.json"
        posts = []
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    posts = json.load(f)
            except Exception:
                posts = []

        # Remove existing if same slug
        posts = [p for p in posts if p.get("slug") != article.slug]

        # Ensure responsive video embed in HTML
        html_content = article.html_content
        if youtube_url:
            vid_id = ""
            if "youtu.be/" in youtube_url:
                vid_id = youtube_url.split("youtu.be/")[1].split("?")[0]
            elif "watch?v=" in youtube_url:
                vid_id = youtube_url.split("watch?v=")[1].split("&")[0]
            elif "embed/" in youtube_url:
                vid_id = youtube_url.split("embed/")[1].split("?")[0]
            
            embed_src = f"https://www.youtube.com/embed/{vid_id}" if vid_id else youtube_url
            embed_iframe = (
                f'<div class="yt-embed-wrapper" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:8px;margin:24px 0;">'
                f'<iframe src="{embed_src}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen></iframe>'
                f'</div>'
            )
            html_content = html_content.replace("[YOUTUBE_EMBED_PLACEHOLDER]", embed_iframe)
        else:
            html_content = html_content.replace("[YOUTUBE_EMBED_PLACEHOLDER]", "")

        new_entry = {
            "slug": article.slug,
            "title": article.title,
            "date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "excerpt": article.meta_description,
            "focusKeyword": article.focus_keyword,
            "categories": article.categories,
            "tags": article.tags,
            "youtubeUrl": youtube_url or "",
            "html": html_content,
            "schema": article.schema_jsonld,
        }
        # Prepend latest
        posts.insert(0, new_entry)
        # Keep latest 50
        posts = posts[:50]

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=2, ensure_ascii=False)


    def _format_markdown_with_frontmatter(
        self, article: GeneratedArticle, youtube_url: Optional[str] = None
    ) -> str:
        """Format article into clean Markdown with SEO frontmatter."""
        now_iso = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        frontmatter = [
            "---",
            f'title: "{article.title.replace(chr(34), chr(39))}"',
            f'date: "{now_iso}"',
            f'slug: "{article.slug}"',
            f'excerpt: "{article.meta_description.replace(chr(34), chr(39))}"',
            f'focusKeyword: "{article.focus_keyword}"',
            f'categories: {json.dumps(article.categories)}',
            f'tags: {json.dumps(article.tags)}',
            f'youtubeUrl: "{youtube_url or ""}"',
            "---",
            "",
        ]

        # Ensure responsive video embed in markdown
        content = article.html_content
        if youtube_url:
            embed_iframe = (
                f'<div class="yt-embed-wrapper" style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;border-radius:8px;margin:24px 0;">'
                f'<iframe src="{youtube_url.replace("watch?v=", "embed/")}" style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" allowfullscreen></iframe>'
                f'</div>'
            )
            content = content.replace("[YOUTUBE_EMBED_PLACEHOLDER]", embed_iframe)
        else:
            content = content.replace("[YOUTUBE_EMBED_PLACEHOLDER]", "")

        full_md = "\n".join(frontmatter) + content
        return full_md

    def publish_article(
        self, article: GeneratedArticle, youtube_url: Optional[str] = None
    ) -> Dict:
        """
        Commit article to GitHub repository, triggering Vercel deployment.
        Falls back to saving locally if GitHub token is not yet configured.
        """
        self._load_config()
        markdown_text = self._format_markdown_with_frontmatter(article, youtube_url=youtube_url)
        file_path = f"{self.posts_dir}/{article.slug}.md"

        # Maintain posts index in content/posts.json
        self._update_local_posts_index(article, youtube_url)

        # Always save locally first (for git commit step or local static server)
        os.makedirs(self.posts_dir, exist_ok=True)
        local_path = f"{self.posts_dir}/{article.slug}.md"
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        # In GitHub Actions runner, the workflow step handles the git commit and push
        if os.getenv("GITHUB_ACTIONS") == "true" or not self.enabled:
            logger.info(f"[GitHubVercel] Saved article to {local_path} (will be committed by workflow)")
            return {
                "success": True,
                "status": "saved_locally_for_vercel",
                "file_path": local_path,
                "url": f"https://github.com/{self.repo}/blob/{self.branch}/{file_path}",
                "title": article.title,
                "slug": article.slug,
            }

        # Commit via GitHub REST API
        api_url = f"https://api.github.com/repos/{self.repo}/contents/{file_path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "AntigravityMarketPipeline/1.0",
        }

        # Check if file exists to get sha for updating
        sha = None
        check_resp = requests.get(f"{api_url}?ref={self.branch}", headers=headers, timeout=15)
        if check_resp.status_code == 200:
            sha = check_resp.json().get("sha")

        commit_payload = {
            "message": f"feat(market): publish {article.title[:50]}",
            "content": base64.b64encode(markdown_text.encode("utf-8")).decode("utf-8"),
            "branch": self.branch,
        }
        if sha:
            commit_payload["sha"] = sha

        try:
            logger.info(f"[GitHubVercel] Pushing '{file_path}' to {self.repo}:{self.branch}...")
            resp = requests.put(api_url, headers=headers, json=commit_payload, timeout=25)
            if resp.status_code in [200, 201]:
                commit_info = resp.json()
                commit_sha = commit_info.get("commit", {}).get("sha", "")[:7]
                logger.success(f"[GitHubVercel] Successfully committed {commit_sha}! Vercel will deploy in ~20s.")
                return {
                    "success": True,
                    "status": "committed_to_github",
                    "commit_sha": commit_sha,
                    "repo": self.repo,
                    "file_path": file_path,
                    "title": article.title,
                    "url": f"https://github.com/{self.repo}/blob/{self.branch}/{file_path}",
                }
            else:
                logger.error(f"[GitHubVercel] GitHub API error {resp.status_code}: {resp.text}")
                return {"success": False, "error": resp.text, "status_code": resp.status_code}
        except Exception as e:
            logger.error(f"[GitHubVercel] Failed to push to GitHub: {e}")
            return {"success": False, "error": str(e)}


# Global instance
github_publisher = GitHubVercelPublisher()
