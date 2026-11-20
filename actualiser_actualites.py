#!/usr/bin/env python3
# iPad Mural V3.3 — Générateur des titres d'actualités, Python 3 stdlib uniquement.
# GitHub Actions récupère des flux RSS publics ; l'iPad ne consulte qu'un JSON léger.
# Aucun contenu d'article, secret ou donnée de compte n'est utilisé.
import datetime as dt
import email.utils
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

# Sources choisies pour leurs flux RSS : si l'une échoue, on essaie la suivante.
FEEDS = {
    "belgique": [
        ("RTBF Info", "https://rss.rtbf.be/article/rss/rtbfinfo_homepage.xml"),
        ("RTBF Belgique", "https://rss.rtbf.be/article/rss/highlight_rtbf_info-belgique.xml"),
    ],
    "maurice": [
        ("Le Mauricien", "https://www.lemauricien.com/feed/"),
        ("Le Mauricien - Actualités", "https://www.lemauricien.com/category/actualites/feed/"),
    ],
    "monde": [
        ("France 24", "https://www.france24.com/fr/actualites/rss"),
        ("Le Monde", "https://www.lemonde.fr/rss/une.xml"),
    ],
    "tech": [
        ("Numerama", "https://www.numerama.com/tech/feed/"),
        ("Numerama - Actualités", "https://www.numerama.com/feed/"),
    ],
}
NOW = dt.datetime.now(dt.timezone.utc)
HEADER = {"User-Agent": "Mozilla/5.0 (compatible; iPadMural-RSS/3.3; feed-reader)", "Accept": "application/rss+xml,application/atom+xml,application/xml,text/xml,*/*"}
MAX_SIZE = 1_500_000
MAX_ITEMS = 8


def to_utc(value):
    if not value:
        return None
    value = value.strip()
    try:
        date = email.utils.parsedate_to_datetime(value)
    except (ValueError, TypeError):
        try:
            date = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    if not date.tzinfo:
        date = date.replace(tzinfo=dt.timezone.utc)
    return date.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_title(value):
    value = re.sub(r"<[^>]*>", " ", value or "")
    value = html.unescape(value)
    value = " ".join(value.split())
    return value[:220]


def get_text(elem, *names):
    for name in names:
        node = elem.find(name)
        if node is not None and node.text:
            return node.text.strip()
    return ""


def valid_link(link):
    if not link or len(link) > 1000:
        return False
    u = urlsplit(link)
    return u.scheme == "https" and bool(u.netloc) and not u.username and not u.password and not any(c in link for c in ('<', '>', '"', "'", '\n', '\r', '\t', ' '))


def parse_feed(raw, source):
    root = ET.fromstring(raw)
    records = []
    # Flux RSS 2.0 et RDF/RSS 1.0.
    rss = root.findall("./channel/item")
    if not rss:
        rss = root.findall("{http://purl.org/rss/1.0/}item")
    for item in rss:
        title = clean_title(get_text(item, "title", "{http://purl.org/rss/1.0/}title"))
        url = get_text(item, "link", "{http://purl.org/rss/1.0/}link")
        date = to_utc(get_text(item, "pubDate", "{http://purl.org/dc/elements/1.1/}date", "date"))
        if title and valid_link(url):
            records.append({"title": title, "url": url, "published_at_utc": date, "source": source})
    # Flux Atom 1.0.
    if not records:
        ns = "{http://www.w3.org/2005/Atom}"
        for item in root.findall(ns + "entry"):
            title = clean_title(get_text(item, ns+"title"))
            link = ""
            for node in item.findall(ns+"link"):
                if node.attrib.get("rel", "alternate") == "alternate" and node.attrib.get("href"):
                    link = node.attrib["href"]
                    break
            date = to_utc(get_text(item, ns+"published", ns+"updated"))
            if title and valid_link(link):
                records.append({"title": title, "url": link, "published_at_utc": date, "source": source})
    seen, unique = set(), []
    for item in records:
        key = re.sub(r"\W+", "", item["title"].lower())[:100]
        if key not in seen:
            unique.append(item)
            seen.add(key)
    unique.sort(key=lambda r: r["published_at_utc"] or "", reverse=True)
    return unique[:MAX_ITEMS]


def fetch(url):
    req = urllib.request.Request(url, headers=HEADER)
    with urllib.request.urlopen(req, timeout=12) as response:
        buf = response.read(MAX_SIZE+1)
        if len(buf)>MAX_SIZE:
            raise ValueError("Flux trop volumineux")
        return buf


def old_public_content():
    # Publication GitHub Pages existante, chargée uniquement pour conserver
    # les dernières nouvelles quand un flux est temporairement indisponible.
    url = "https://lordnigma.github.io/ipad-mural/actualites.json"
    try:
        value = json.loads(fetch(url).decode("utf-8"))
        if value.get("version") == 1 and isinstance(value.get("categories"), dict):
            return value
    except (OSError, ValueError, KeyError, UnicodeError, TypeError):
        pass
    return None


def build():
    previous = None
    generated = NOW.isoformat(timespec="seconds").replace("+00:00", "Z")
    result = {"version": 1, "generated_at_utc":generated, "updated_at_utc":None, "categories":{}}
    statuses = []
    successes = []
    for group, sources in FEEDS.items():
        items, chosen = [], ""
        for source, url in sources:
            try:
                items = parse_feed(fetch(url), source)
                if items:
                    chosen = source
                    successes.append(generated)
                    break
                print("INFO:", group, source, "flux vide")
            except (OSError, ValueError, ET.ParseError, UnicodeError, RuntimeError) as exc:
                print("INFO:",group,source,"non disponible (",type(exc).__name__,")")
        if items:
            result["categories"][group] = {"source":chosen, "fetched_at_utc":generated, "items":items, "stale":False}
            statuses.append(group+": "+str(len(items))+" titres")
        else:
            if previous is None:
                previous = old_public_content()
            fallback = (previous or {}).get("categories", {}).get(group, {})
            old_items = fallback.get("items") if isinstance(fallback,dict) else None
            if not isinstance(old_items,list):
                old_items=[]
            fetched = fallback.get("fetched_at_utc") if isinstance(fallback,dict) else None
            result["categories"][group] = {"source":fallback.get("source","") if isinstance(fallback,dict) else "", "fetched_at_utc":fetched, "items":old_items[:MAX_ITEMS], "stale":True}
            statuses.append(group+": flux inaccessible; "+("ancienne copie" if old_items else "aucun titre"))
    # Dernière récupération RÉUSSIE (pas la date du déploiement).
    stamps = [r.get("fetched_at_utc") for r in result["categories"].values() if r.get("fetched_at_utc")]
    if stamps:
        result["updated_at_utc"] = max(stamps)
    print(" | ".join(statuses))
    return result


def main():
    target = Path(sys.argv[1]) if len(sys.argv)>1 else Path("actualites.json")
    target.parent.mkdir(parents=True,exist_ok=True)
    data = build()
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(data,ensure_ascii=False,separators=(",",":"),sort_keys=False)+"\n",encoding="utf-8")
    os.replace(str(temp),str(target))
    print("OK fichier actualites cree:",str(target))

if __name__ == "__main__":
    main()
