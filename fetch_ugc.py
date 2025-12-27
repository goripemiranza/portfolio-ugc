#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_ugc.py (v6) — On-sale only + thumbs in JSON (no client CORS)

Pourquoi :
- GitHub Pages (site statique) ne peut PAS appeler catalog.roblox.com / thumbnails.roblox.com en JS
  à cause de CORS (pas de Access-Control-Allow-Origin).
- Donc : on récupère les données côté GitHub Actions (serveur) et on écrit data_user.json / data_group.json.
- Le site lit uniquement ces JSON => 0 CORS côté visiteurs.

Ce script récupère UNIQUEMENT les items mis en vente :
- includeNotForSale=false
- on garde seulement ceux avec price numérique

Bonus :
- On hydrate les thumbnails via thumbnails.roblox.com côté GitHub Actions et on stocke 'thumb' dans le JSON.
  Ainsi le site n'a pas besoin de fetch thumbnail API (CORS), il affiche l'image directement.

⚠️ Rate-limit :
- Roblox peut renvoyer 429 depuis GitHub Actions. On "fail-open" :
  si erreur => on garde le JSON précédent (le site continue de marcher).
"""

import json
import time
import random
import datetime
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from typing import Any, Dict, List, Optional, Set

USER_ID = 828726934
GROUP_ID = 16981319

CATALOG_LIST = "https://catalog.roblox.com/v1/search/items"
THUMBS = "https://thumbnails.roblox.com/v1/assets"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "PortfolioUGCFetch/6.0 (+https://roblox.com)",
}

class RateLimited(Exception):
    pass

RATE_LIMIT_HITS = 0
RATE_LIMIT_BUDGET = 10

def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

def read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def http_get_json(url: str, timeout: int = 30, max_retries: int = 4) -> Dict[str, Any]:
    global RATE_LIMIT_HITS
    last_err: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", errors="replace")
            return json.loads(raw)

        except HTTPError as e:
            last_err = e
            code = getattr(e, "code", None)

            if code == 429:
                RATE_LIMIT_HITS += 1
                if RATE_LIMIT_HITS >= RATE_LIMIT_BUDGET:
                    raise RateLimited(f"429 budget reached ({RATE_LIMIT_HITS})") from e

                retry_after = None
                try:
                    retry_after = e.headers.get("Retry-After")
                except Exception:
                    retry_after = None

                if retry_after and str(retry_after).strip().isdigit():
                    sleep_s = float(int(retry_after))
                else:
                    sleep_s = 4.0 + random.random() * 2.0

                sleep_s = min(25.0, sleep_s + attempt * 4.0)
                print(f"[http] 429 -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_s)
                continue

            if code in (500, 502, 503, 504):
                sleep_s = 3.0 + random.random() * 2.0
                print(f"[http] HTTP {code} -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_s)
                continue

            raise

        except URLError as e:
            last_err = e
            sleep_s = 2.0 + random.random() * 2.0
            print(f"[http] URLError -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
            time.sleep(sleep_s)
            continue

        except Exception as e:
            last_err = e
            sleep_s = 2.0 + random.random() * 2.0
            print(f"[http] Error -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
            time.sleep(sleep_s)
            continue

    raise RuntimeError(f"GET failed: {url} / last_err={last_err}")

def pick_int(d: Dict[str, Any], keys: List[str]) -> Optional[int]:
    for k in keys:
        v = d.get(k)
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
    return None

def pick_str(d: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v:
            return v
    return None

def fetch_on_sale_catalog(creator_type: int, creator_target_id: int, limit: int = 30, max_pages: int = 120) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    cursor = ""

    for _ in range(max_pages):
        params = {
            "category": "1",
            "creatorType": str(creator_type),
            "creatorTargetId": str(creator_target_id),
            "includeNotForSale": "false",
            "limit": str(limit),
        }
        if cursor:
            params["cursor"] = cursor

        url = CATALOG_LIST + "?" + urllib.parse.urlencode(params)
        j = http_get_json(url)

        for d in (j.get("data") or []):
            aid = pick_int(d, ["assetId", "id"])
            if aid is None:
                continue

            price = pick_int(d, ["price", "priceInRobux", "lowestPrice", "PriceInRobux"])
            if price is None:
                # on-sale only => needs numeric price
                continue

            name = pick_str(d, ["name", "itemName", "title"]) or f"Item {aid}"

            at = d.get("assetType") if isinstance(d.get("assetType"), dict) else {}
            typ = pick_str(at, ["name"]) or pick_str(d, ["assetTypeName", "itemType", "type"]) or "UGC"

            created = pick_str(d, ["created", "Created", "createdUtc", "createdAt"])

            items.append({
                "assetId": int(aid),
                "name": name,
                "type": typ,
                "price": int(price),
                "created": created,
            })

        cursor = j.get("nextPageCursor") or ""
        if not cursor:
            break

        time.sleep(0.45)

    # dedupe
    seen: Set[int] = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        if it["assetId"] in seen:
            continue
        seen.add(it["assetId"])
        out.append(it)

    # sort newest-ish: created if present else by assetId
    def key(it):
        ts = None
        if isinstance(it.get("created"), str) and it["created"]:
            try:
                ts = int(datetime.datetime.fromisoformat(it["created"].replace("Z","+00:00")).timestamp())
            except Exception:
                ts = None
        return (ts if ts is not None else -1, it["assetId"])
    out.sort(key=key, reverse=True)
    return out

def hydrate_thumbs(items: List[Dict[str, Any]]) -> None:
    ids = [it["assetId"] for it in items if isinstance(it.get("assetId"), int)]
    if not ids:
        return

    # thumbnails API supports batching; keep conservative
    B = 50
    for i in range(0, len(ids), B):
        chunk = ids[i:i+B]
        qs = urllib.parse.urlencode({
            "assetIds": ",".join(str(x) for x in chunk),
            "size": "420x420",
            "format": "Png",
            "isCircular": "false",
        })
        url = THUMBS + "?" + qs
        try:
            j = http_get_json(url, max_retries=3, timeout=30)
            m: Dict[int, str] = {}
            for t in (j.get("data") or []):
                tid = t.get("targetId")
                img = t.get("imageUrl")
                st = t.get("state")
                if isinstance(tid, int) and isinstance(img, str) and st == "Completed":
                    m[tid] = img
            for it in items:
                aid = it["assetId"]
                if aid in m:
                    it["thumb"] = m[aid]
        except Exception:
            pass
        time.sleep(0.25)

def safe_update(path: str, creator_type: int, creator_target_id: int) -> None:
    prev = read_json(path)
    try:
        items = fetch_on_sale_catalog(creator_type, creator_target_id)
        hydrate_thumbs(items)
        write_json(path, {"generatedAt": now_iso(), "items": items})
        print(f"[ok] {path}: {len(items)} items (on-sale)")
    except Exception as e:
        print(f"[warn] {path}: keep previous ({e})")
        if prev is None:
            write_json(path, {"generatedAt": now_iso(), "items": []})

def main() -> None:
    # jitter
    time.sleep(3.0 + random.random() * 7.0)
    safe_update("data_user.json", 1, USER_ID)
    time.sleep(4.0 + random.random() * 6.0)
    safe_update("data_group.json", 2, GROUP_ID)

if __name__ == "__main__":
    main()
