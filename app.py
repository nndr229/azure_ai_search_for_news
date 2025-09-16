import os
import re
from flask import Flask, render_template, jsonify
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime

# ============ Config & Setup ============

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise RuntimeError(
        "Missing GOOGLE_API_KEY in environment. Create a .env with GOOGLE_API_KEY=...")

# Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)

# Use a model with web grounding capability
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
MODEL = genai.GenerativeModel(MODEL_NAME)

app = Flask(__name__)

# Simple in-memory cache of the latest sources for convenience across routes during a process lifetime
LATEST_SOURCES = {
    "news": [],
    "improvements": []
}

# ============ Helpers ============


def extract_citations(response) -> list:
    """
    Try to extract citations/URLs from a grounded Gemini response. This covers multiple
    SDK shapes that may vary across versions.
    """
    sources = []

    # 1) Preferred: response.candidates[0].grounding_metadata.grounding_chunks[*].web.page.site
    try:
        for cand in getattr(response, "candidates", []) or []:
            gm = getattr(cand, "grounding_metadata", None)
            if not gm:
                continue
            chunks = getattr(gm, "grounding_chunks", []) or []
            for ch in chunks:
                # Typical web chunk shape: ch.web.page.uri or .page.site; be defensive
                uri = None
                try:
                    uri = ch.web.page.uri
                except Exception:
                    pass
                if not uri:
                    try:
                        uri = ch.web.page.site
                    except Exception:
                        pass
                if uri:
                    sources.append(uri)
    except Exception:
        pass

    # 2) response.citations (older shapes)
    try:
        for cit in getattr(response, "citations", []) or []:
            # Some SDKs provide a list of citation dicts with "uri" or "source"
            uri = cit.get("uri") or cit.get("source") or cit.get("url")
            if uri:
                sources.append(uri)
    except Exception:
        pass

    # 3) Fallback: detect URLs in response text
    try:
        txt = getattr(response, "text", "") or ""
        if txt:
            for m in re.findall(r"(https?://[^\s)]+)", txt):
                sources.append(m)
    except Exception:
        pass

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for u in sources:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped[:20]  # cap safety


def parse_structured_blocks(text: str):
    """
    Parse blocks of the format:
    Headline: ...
    Summary: ...
    Link: ...
    ---
    Returns list of dicts.
    """
    items = []
    if not text:
        return items
    for block in text.split("---"):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        entry = {}
        for ln in lines:
            if ln.lower().startswith("headline:"):
                entry["headline"] = ln.split(":", 1)[1].strip()
            elif ln.lower().startswith("summary:"):
                entry["summary"] = ln.split(":", 1)[1].strip()
            elif ln.lower().startswith("link:"):
                entry["link"] = ln.split(":", 1)[1].strip()
            elif ln.lower().startswith("why it matters:"):
                entry["why"] = ln.split(":", 1)[1].strip()
            elif ln.lower().startswith("source:"):
                entry["source"] = ln.split(":", 1)[1].strip()
        if entry:
            items.append(entry)
    return items


# ============ Routes ============

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/news")
def news():
    return render_template("news.html")


@app.route("/improvements")
def improvements():
    return render_template("improvements.html")


@app.route("/sources")
def sources():
    return render_template("sources.html")


# -------- API: Top 5 News Agent --------
@app.route("/api/news")
def api_news():
    """
    Fetch top 5 Azure AI Foundry news stories. Uses Gemini with Google Search grounding.
    Returns structured JSON with items and sources.
    """
    prompt = """
You are a news scout focusing on Azure AI Foundry.
Use web search. Find the 5 most recent, credible news items about Azure AI Foundry (product announcements, major partnerships, GA/preview updates).

Return EXACTLY 5 entries formatted as blocks:
Headline: <max 10 words>
Summary: <2–3 sentences – neutral, specific, and concise>
Link: <direct URL>
---

Rules:
- Prefer official Microsoft sources, reputable tech media, and engineering blogs.
- No speculation; only verifiable information.
- Avoid duplicates; include distinct items.
- If fewer than 5 truly recent items exist, backfill with most impactful items from the last 6 months.
    """.strip()

    response = MODEL.generate_content(prompt)
    text = response.text or ""
    items = parse_structured_blocks(text)

    # Extract citations/sources
    cites = extract_citations(response)
    LATEST_SOURCES["news"] = cites

    return jsonify({
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(items),
        "items": items[:5],
        "sources": cites
    })


# -------- API: Most Relevant Technical Improvements Agent --------
@app.route("/api/improvements")
def api_improvements():
    """
    Fetch the most relevant technical improvements pulled from official docs/release notes
    (SDK changes, API updates, pricing/quotas, deployment/runtime or evaluation capabilities).
    """
    prompt = """
You are a documentation analyst for Azure AI Foundry.
Use web search to read official Microsoft documentation, release notes, and engineering blogs.

Task:
Extract the 5 most relevant recent TECHNICAL improvements (features or changes) for developers using Azure AI Foundry.
For each, include:
Headline: <feature/change in ~8 words>
Summary: <2–3 sentences focusing on what changed + impact on devs>
Link: <deep link to the source doc or release note>
Why it matters: <short bullet/phrase on developer benefit>

Format EXACTLY like:
Headline: ...
Summary: ...
Link: ...
Why it matters: ...
---

Rules:
- Prioritize official docs.microsoft.com/learn.microsoft.com/azure pages and Azure Updates.
- Be precise (mention API/SDK names, regions, quotas, GA/preview labels when available).
- Avoid marketing fluff.
    """.strip()

    response = MODEL.generate_content(prompt)
    text = response.text or ""
    items = parse_structured_blocks(text)

    # Extract citations/sources
    cites = extract_citations(response)
    LATEST_SOURCES["improvements"] = cites

    return jsonify({
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(items),
        "items": items[:5],
        "sources": cites
    })


# -------- API: Sources Aggregator Agent --------
@app.route("/api/sources")
def api_sources():
    """
    Aggregate the latest sources observed by the other two agents in this process lifetime.
    This avoids re-calling the model; it's just a convenience endpoint.
    If you need fresh sources, call /api/news and /api/improvements first.
    """
    merged = []
    for key in ("news", "improvements"):
        for url in LATEST_SOURCES.get(key, []):
            merged.append({"url": url, "from": key})

    # Deduplicate by URL while preserving first-seen origin
    seen = set()
    uniq = []
    for item in merged:
        if item["url"] not in seen:
            uniq.append(item)
            seen.add(item["url"])

    return jsonify({
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(uniq),
        "sources": uniq
    })


if __name__ == "__main__":
    # Default port 3000 per your starter
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "3000")), debug=True)
