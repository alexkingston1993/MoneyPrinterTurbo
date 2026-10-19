"""
Programmatic SEO Sitemap & Robots.txt Generator for Dalal Street Alpha Desk.
Indexes all benchmark NSE equity analysis pages, legal pages, and market archives.
"""

import datetime
import json
import os

BASE_URL = "https://dalal-street-alpha.vercel.app"

def generate_sitemap():
    now_iso = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    
    # 1. Static Core Pages
    urls = [
        {"loc": f"{BASE_URL}/", "lastmod": now_iso, "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{BASE_URL}/disclaimer", "lastmod": now_iso, "changefreq": "monthly", "priority": "0.7"},
        {"loc": f"{BASE_URL}/risk-disclosure", "lastmod": now_iso, "changefreq": "monthly", "priority": "0.7"},
        {"loc": f"{BASE_URL}/affiliate-disclosure", "lastmod": now_iso, "changefreq": "monthly", "priority": "0.7"},
        {"loc": f"{BASE_URL}/terms", "lastmod": now_iso, "changefreq": "monthly", "priority": "0.5"},
        {"loc": f"{BASE_URL}/privacy", "lastmod": now_iso, "changefreq": "monthly", "priority": "0.5"},
    ]
    
    # 2. Add Benchmark Equities from data/nse_stocks.json
    stocks_file = "data/nse_stocks.json"
    if os.path.exists(stocks_file):
        with open(stocks_file, "r", encoding="utf-8") as f:
            stocks = json.load(f)
        for s in stocks:
            sym = s.get("symbol", "").upper()
            if sym:
                urls.append({
                    "loc": f"{BASE_URL}/stocks/{sym}",
                    "lastmod": now_iso,
                    "changefreq": "daily",
                    "priority": "0.85",
                })
    
    # 3. Format XML
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for u in urls:
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{u['loc']}</loc>")
        xml_lines.append(f"    <lastmod>{u['lastmod']}</lastmod>")
        xml_lines.append(f"    <changefreq>{u['changefreq']}</changefreq>")
        xml_lines.append(f"    <priority>{u['priority']}</priority>")
        xml_lines.append("  </url>")
    xml_lines.append("</urlset>")
    
    sitemap_content = "\n".join(xml_lines)
    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write(sitemap_content)
    print(f"Generated sitemap.xml with {len(urls)} indexed URLs.")

    # 4. Generate robots.txt
    robots_content = f"""User-agent: *
Allow: /

Sitemap: {BASE_URL}/sitemap.xml
"""
    with open("robots.txt", "w", encoding="utf-8") as f:
        f.write(robots_content)
    print("Generated robots.txt.")

if __name__ == "__main__":
    generate_sitemap()
