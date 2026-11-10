#!/usr/bin/env python3
"""Refresh data/*.json. Standard library only. Each source fails independently."""
import json, os, re, sys, urllib.parse, urllib.request, html
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
NOW = datetime.now(timezone.utc)
UA = {"User-Agent": "PulseBot/1.0 (https://github.com; mailto:%s)" % os.environ.get("CONTACT_EMAIL", "you@example.com")}

def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def save(name, obj):
    with open(os.path.join(DATA, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def load(name):
    with open(os.path.join(DATA, name + ".json"), encoding="utf-8") as f:
        return json.load(f)

# ---------------- NEWS ----------------
FEEDS = [  # edit freely
    ("Fierce Healthcare", "https://www.fiercehealthcare.com/rss/xml"),
    ("Healthcare Dive", "https://www.healthcaredive.com/feeds/news/"),
    ("HIStalk", "https://histalk2.com/feed/"),
    ("Healthcare IT Today", "https://www.healthcareittoday.com/feed/"),
    ("STAT", "https://www.statnews.com/feed/"),
    ("MobiHealthNews", "https://www.mobihealthnews.com/feed"),
]
AI = re.compile(r"\b(AI|artificial intelligence|machine learning|LLM|generative|agentic|chatbot|ambient|copilot)\b", re.I)
BIZ = re.compile(r"\b(acqui\w+|funding|raises?|revenue|layoffs?|merger|earnings|M&A|IPO|investment|partnership|valuation|profit|ROI)\b", re.I)
POL = re.compile(r"\b(FDA|CMS|HHS|regulat\w+|law|legislation|policy|Congress|AMA|bill|rule|Medicare|Medicaid|privacy|HIPAA)\b", re.I)

def parse_date(s):
    if not s: return None
    try:
        d = parsedate_to_datetime(s)
    except Exception:
        try: d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

def strip(s, n=220):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"

def fetch_feed(source, url):
    root = ET.fromstring(get(url))
    out = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"): continue
        g = lambda n: next((c for c in it if c.tag.split("}")[-1] == n), None)
        title = (g("title").text or "").strip() if g("title") is not None else ""
        link_el = g("link")
        link = (link_el.text or link_el.get("href") or "").strip() if link_el is not None else ""
        d = None
        for n in ("pubDate", "published", "updated", "date"):
            if g(n) is not None: d = parse_date(g(n).text); break
        desc = g("description") if g("description") is not None else g("summary")
        out.append({"title": title, "url": link, "date": d, "source": source, "summary": strip(desc.text if desc is not None else "")})
    return out

def update_news():
    cutoff = NOW - timedelta(days=7)
    items, seen = [], set()
    for source, url in FEEDS:
        try:
            for e in fetch_feed(source, url):
                if not e["date"] or e["date"] < cutoff or not e["title"] or not e["url"]: continue
                text = e["title"] + " " + e["summary"]
                tags = [t for t, rx in (("ai", AI), ("biz", BIZ), ("pol", POL)) if rx.search(text)]
                if not tags: continue
                key = re.sub(r"\W+", "", e["title"].lower())[:60]
                if key in seen: continue
                seen.add(key)
                e["tags"] = tags
                # rank: AI + business first, then recency
                e["score"] = len(tags) + (2 if "ai" in tags else 0)
                items.append(e)
            print("ok  feed", source)
        except Exception as ex:
            print("ERR feed", source, ex, file=sys.stderr)
    if not items:
        print("No news fetched; keeping previous file."); return
    items.sort(key=lambda e: (e["score"], e["date"]), reverse=True)
    items = sorted(items[:25], key=lambda e: e["date"], reverse=True)
    for e in items: e["date"] = e["date"].strftime("%Y-%m-%d"); e.pop("score")
    save("news", {"updated": NOW.isoformat(), "items": items})

# ---------------- PAPERS (Crossref) ----------------
# (name, ISSN, in UTD24, in FT50). Verify list membership against the official lists.
JOURNALS = [
    ("Management Science", "0025-1909", 1, 1),
    ("Manufacturing & Service Operations Management", "1523-4614", 1, 1),
    ("Operations Research", "0030-364X", 1, 1),
    ("Journal of Operations Management", "0272-6963", 1, 1),
    ("Production and Operations Management", "1059-1478", 0, 1),
    ("MIS Quarterly", "0276-7783", 1, 1),
    ("Information Systems Research", "1047-7047", 1, 1),
    ("Journal of Management Information Systems", "0742-1222", 1, 0),
    ("Marketing Science", "0732-2399", 1, 1),
    ("Strategic Management Journal", "0143-2095", 1, 1),
    ("Organization Science", "1047-7039", 1, 1),
]
QUERY = "health care OR healthcare OR hospital OR physician OR patient OR telemedicine"

def update_papers():
    since = (NOW - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
    items = []
    for name, issn, utd, ft in JOURNALS:
        try:
            params = {"query.bibliographic": QUERY, "filter": "issn:%s,from-pub-date:%s,type:journal-article" % (issn, since),
                      "sort": "published", "order": "desc", "rows": "4",
                      "select": "title,author,issued,DOI,container-title", "mailto": os.environ.get("CONTACT_EMAIL", "you@example.com")}
            data = json.loads(get("https://api.crossref.org/works?" + urllib.parse.urlencode(params)))
            for w in data["message"]["items"]:
                if not w.get("title"): continue
                y = (w.get("issued", {}).get("date-parts") or [[None]])[0][0]
                authors = ", ".join(" ".join(filter(None, [a.get("given"), a.get("family")])) for a in w.get("author", [])[:4])
                if len(w.get("author", [])) > 4: authors += " et al."
                items.append({"title": strip(w["title"][0], 200), "authors": authors, "journal": name, "year": y,
                              "url": "https://doi.org/" + w["DOI"], "utd": bool(utd), "ft": bool(ft)})
            print("ok  journal", name)
        except Exception as ex:
            print("ERR journal", name, ex, file=sys.stderr)
    if not items:
        print("No papers fetched; keeping previous file."); return
    items.sort(key=lambda p: p["year"] or 0, reverse=True)
    save("papers", {"updated": NOW.isoformat(), "items": items[:40]})

# ---------------- JOBS (Adzuna, optional) ----------------
JOB_QUERIES = ["healthcare AI", "clinical informatics", "healthcare data scientist", "digital health product manager"]

def update_jobs():
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        print("No Adzuna keys set; skipping jobs (search links still work)."); return
    items, seen = [], set()
    for q in JOB_QUERIES:
        try:
            p = {"app_id": app_id, "app_key": app_key, "what": q, "max_days_old": 7, "results_per_page": 10, "sort_by": "date"}
            data = json.loads(get("https://api.adzuna.com/v1/api/jobs/us/search/1?" + urllib.parse.urlencode(p)))
            for j in data.get("results", []):
                if j["id"] in seen: continue
                seen.add(j["id"])
                items.append({"title": j["title"].replace("<strong>", "").replace("</strong>", ""),
                              "company": (j.get("company") or {}).get("display_name", ""),
                              "location": (j.get("location") or {}).get("display_name", ""),
                              "url": j["redirect_url"], "date": j["created"][:10]})
            print("ok  jobs", q)
        except Exception as ex:
            print("ERR jobs", q, ex, file=sys.stderr)
    if items:
        items.sort(key=lambda j: j["date"], reverse=True)
        save("jobs", {"updated": NOW.isoformat(), "items": items[:30]})

if __name__ == "__main__":
    update_news(); update_papers(); update_jobs()
