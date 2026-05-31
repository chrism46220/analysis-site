#!/usr/bin/env python3
"""Build analysis-site from ~/share markdown and html files."""

import json
import os
import re
import shutil
from datetime import datetime

import markdown

SRC = os.path.expanduser("~/share")
DST = os.path.expanduser("~/share/analysis-site")

ARTICLES_DIR = os.path.join(DST, "articles")
os.makedirs(ARTICLES_DIR, exist_ok=True)

# ── Metadata extraction ──────────────────────────────────────────────

def extract_title(text):
    """Extract first # heading or first non-empty line."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    # fallback: first meaningful line
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:80]
    return "Untitled"


def extract_date(text):
    """Try to find a date near the top of the file."""
    patterns = [
        r"\*\*Date:\*\*\s*(.+?)(?:\n|$)",
        r"\*\*Analysis Date:\*\*\s*(.+?)(?:\n|$)",
        r"Date:\s+(.+?)(?:\n|$)",
        r"(\w+ \d{1,2},? \d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, text[:500])
        if m:
            return m.group(1).strip()
    return None


def make_slug(title):
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "article"


# ── Article info ─────────────────────────────────────────────────────

def gather_articles():
    """Return list of dicts describing every article."""
    articles = []

    md_files = sorted(f for f in os.listdir(SRC) if f.endswith(".md") and not f.startswith("."))
    html_files = sorted(f for f in os.listdir(SRC) if f.endswith(".html") and not f.startswith("."))

    # Markdown files
    for fname in md_files:
        src_path = os.path.join(SRC, fname)
        with open(src_path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()

        title = extract_title(text)
        date_str = extract_date(text)
        slug = make_slug(title)

        articles.append({
            "src": src_path,
            "fname": fname,
            "type": "md",
            "title": title,
            "date": date_str,
            "slug": slug,
            "dest_html": f"{slug}.html" if slug else fname.replace(".md", ".html"),
            "text": text,
        })

    # Pre-rendered HTML files — copy as-is
    pre_rendered = {
        "oil_crisis_comparison.html",
        "quantum.html",
        "quantum_timeline.html",
        "domain-restriction-design.html",
        "agent-learning-design.html",
        "memory-search-systems.html",
        "learning-mvp-plan.html",
        "learning-mvp-output.html",
        "ai-bubble-report.html",
        "macro_outlook.html",
    }

    for fname in html_files:
        if fname not in pre_rendered:
            continue
        src_path = os.path.join(SRC, fname)
        dest_name = fname
        # Avoid slug collision — use the base md slug if available
        md_base = fname.replace(".html", ".md")
        md_match = [a for a in articles if a["fname"] == md_base]
        if md_match:
            # This html is an alternate version of an md article
            a = md_match[0]
            dest_name = f"{a['slug']}-preview.html"
            articles.append({
                "src": src_path,
                "fname": fname,
                "type": "html",
                "title": f"{a['title']} (Preview)",
                "date": a["date"],
                "slug": f"{a['slug']}-preview",
                "dest_html": dest_name,
                "text": "",
            })
        else:
            # Standalone html
            title = fname.replace(".html", "").replace("-", " ").title()
            articles.append({
                "src": src_path,
                "fname": fname,
                "type": "html",
                "title": title,
                "date": None,
                "slug": fname.replace(".html", ""),
                "dest_html": fname,
                "text": "",
            })

    # Deduplicate by dest_html — keep first
    seen = set()
    deduped = []
    for a in articles:
        if a["dest_html"] not in seen:
            seen.add(a["dest_html"])
            deduped.append(a)
    return deduped


# ── Category assignment ──────────────────────────────────────────────

def categorize(title, fname):
    t = (title + " " + fname).lower()
    if "oil" in t or "crisis" in t:
        return "Oil Crisis Analysis"
    if "macro" in t or "ai-bubble" in t or "portfolio" in t or "bubble" in t:
        return "Markets & Macro"
    if "quantum" in t:
        return "Quantum Computing"
    if "agent" in t or "domain" in t or "learning" in t or "memory" in t or "mvp" in t or "agents" in t:
        return "Agent & System Design"
    return "Other"


# ── HTML templates ───────────────────────────────────────────────────

def article_template(title, date_str, content_html, back_url="../index.html"):
    date_line = ""
    if date_str:
        date_line = f'<p class="article-date">{date_str}</p>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — Analysis</title>
<link rel="stylesheet" href="../style.css">
</head>
<body>
<nav class="top-nav"><a href="{back_url}">← Back to Home</a></nav>
<main class="article">
<h1>{title}</h1>
{date_line}
<div class="content">
{content_html}
</div>
<footer><a href="{back_url}">← Back to Home</a></footer>
</main>
</body>
</html>"""


def index_template(categories, html_mapping):
    """Build index.html with grouped navigation."""
    cat_blocks = ""
    for cat_name, cat_articles in categories.items():
        items = ""
        for a in cat_articles:
            date_str = a["date"] or ""
            dest = html_mapping[a["src"]]

            # Get description (first paragraph after title)
            desc = ""
            if a["type"] == "md" and a["text"]:
                lines = a["text"].splitlines()
                in_front = False
                for line in lines:
                    stripped = line.strip()
                    if stripped.startswith("# "):
                        in_front = True
                        continue
                    if in_front and stripped and not stripped.startswith("#") and not stripped.startswith("**Date"):
                        desc = stripped[:150]
                        if len(stripped) > 150:
                            desc += "…"
                        break

            date_tag = f'<span class="date">{date_str}</span>' if date_str else ""
            badge = " <span class=\"badge\">pre-rendered</span>" if a["type"] == "html" else ""
            items += f"""
      <li>
        <a href="articles/{dest}">{a['title']}{badge}</a>
        {date_tag}
        <p class="desc">{desc}</p>
      </li>"""

        cat_blocks += f"""
    <section>
      <h2>{cat_name}</h2>
      <ul class="article-list">{items}
      </ul>
    </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Analysis Hub</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
<h1>Analysis Hub</h1>
<p class="subtitle">Research & analysis documents</p>
</header>
<main>{cat_blocks}
</main>
<footer><p>Generated {datetime.now().strftime("%B %d, %Y")}</p></footer>
</body>
</html>"""


# ── Main ─────────────────────────────────────────────────────────────

def main():
    articles = gather_articles()

    # Build HTML mapping: src_path -> dest_html
    html_mapping = {}

    md_extras = markdown.Markdown(extensions=["extra", "tables", "fenced_code", "codehilite"],
                                    output_format="html5")

    for a in articles:
        dest_path = os.path.join(ARTICLES_DIR, a["dest_html"])

        if a["type"] == "md":
            # Convert markdown to html
            text = a["text"]
            content_html = md_extras.convert(text)
            md_extras.reset()  # Reset state for next conversion

            page_html = article_template(a["title"], a["date"], content_html)
            with open(dest_path, "w", encoding="utf-8") as fh:
                fh.write(page_html)
            print(f"  [convert] {a['fname']} → articles/{a['dest_html']}")
        else:
            # Copy pre-rendered HTML as-is
            shutil.copy2(a["src"], dest_path)
            print(f"  [copy]    {a['fname']} → articles/{a['dest_html']}")

        html_mapping[a["src"]] = a["dest_html"]

    # Group by category
    categories = {}
    for a in articles:
        cat = categorize(a["title"], a["fname"])
        categories.setdefault(cat, []).append(a)

    # Sort within categories by date (newest first) if available
    def sort_key(a):
        if a["date"]:
            try:
                # Try parsing common date formats
                for fmt in ["%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"]:
                    try:
                        return datetime.strptime(a["date"], fmt)
                    except ValueError:
                        continue
            except Exception:
                pass
        return datetime.min

    for cat in categories:
        categories[cat].sort(key=sort_key, reverse=True)

    # Build index
    index_html = index_template(categories, html_mapping)
    with open(os.path.join(DST, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(index_html)
    print(f"\n  [index]   {os.path.join(DST, 'index.html')}")

    # Summary
    print(f"\n  Total articles: {len(articles)}")
    for cat, items in categories.items():
        print(f"    {cat}: {len(items)}")


if __name__ == "__main__":
    main()
