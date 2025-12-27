#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_ugc.py (v8) — UGC only (accessoires/vêtements) + bons IDs (assetId) + noms/prix.

Le bug actuel ("Item 1317..." / pas d'image / pas de nom/prix) vient du fait que l'API renvoie parfois un
"catalog item id" (listing id) différent du vrai assetId. Si on utilise le mauvais id :
- le nom n'est pas récupéré
- l'image ne charge pas
- le prix est vide

v8 :
- utilise /v1/search/items/details (meilleure structure)
- exige un vrai assetId (sinon on ignore l'entrée)
- extrait name + price quand présents
- filtre UGC (types d'accessoires/vêtements) pour ne pas afficher d'autres assets
- écrit thumb = asset-thumbnail URL (fonctionne côté navigateur via <img>)

⚠️ Rate-limit (429) : si ça arrive, on garde le JSON précédent.
"""

import json, time, random, datetime, urllib.parse, urllib.request
from urllib.error import HTTPError, URLError
from typing import Any, Dict, List, Optional, Set, Tuple

USER_ID = 828726934
GROUP_ID = 16981319

CATALOG_DETAILS = "https://catalog.roblox.com/v1/search/items/details"
THUMB_TEMPLATE = "https://www.roblox.com/asset-thumbnail/image?assetId={asset_id}&width=420&height=420&format=png"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "PortfolioUGCFetch/8.0 (+https://roblox.com)",
}

class RateLimited(Exception):
    pass

RATE_LIMIT_HITS = 0
RATE_LIMIT_BUDGET = 14

UGC_TYPE_KEYWORDS = (
    "accessory", "hat", "hair", "face", "neck", "shoulder", "front", "back", "waist",
    "shirt", "pants", "tshirt", "jacket", "sweater", "shorts", "dress", "skirt",
)

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

def http_get_json(url: str, timeout: int = 30, max_retries: int = 6) -> Dict[str, Any]:
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
                    sleep_s = 6.0 + random.random() * 3.0
                sleep_s = min(90.0, sleep_s + attempt * 10.0)

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

def pick_int(d: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[int]:
    for k in keys:
        v = d.get(k)
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
    return None

def pick_str(d: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[str]:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v:
            return v
    return None

def deep_find_asset_id(obj: Any) -> Optional[int]:
    if isinstance(obj, dict):
        v = obj.get("assetId")
        if isinstance(v, int):
            return v
        for vv in obj.values():
            out = deep_find_asset_id(vv)
            if isinstance(out, int):
                return out
    elif isinstance(obj, list):
        for it in obj:
            out = deep_find_asset_id(it)
            if isinstance(out, int):
                return out
    return None

def is_ugc_type(type_name: str) -> bool:
    t = (type_name or "").lower()
    return any(k in t for k in UGC_TYPE_KEYWORDS)

def fetch_catalog_details(creator_type: int, creator_target_id: int, limit: int = 30, max_pages: int = 120) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    cursor = ""

    for _ in range(max_pages):
        params = {
            "category": "1",
            "creatorType": str(creator_type),
            "creatorTargetId": str(creator_target_id),
            "includeNotForSale": "true",
            "limit": str(limit),
        }
        if cursor:
            params["cursor"] = cursor

        url = CATALOG_DETAILS + "?" + urllib.parse.urlencode(params)
        j = http_get_json(url)

        for d in (j.get("data") or []):
            if not isinstance(d, dict):
                continue

            asset_id = pick_int(d, ("assetId",))
            if asset_id is None:
                asset_id = deep_find_asset_id(d)
            if asset_id is None:
                continue

            name = pick_str(d, ("name", "itemName", "title")) or f"Item {asset_id}"

            typ = None
            at = d.get("assetType")
            if isinstance(at, dict):
                typ = pick_str(at, ("name",))
            typ = typ or pick_str(d, ("assetTypeName", "itemType", "type")) or "UGC"

            if not is_ugc_type(typ):
                continue

            price = pick_int(d, ("price", "priceInRobux", "lowestPrice", "PriceInRobux"))
            created = pick_str(d, ("created", "Created", "createdUtc", "createdAt"))

            items.append({
                "assetId": int(asset_id),
                "name": name,
                "type": typ,
                "price": int(price) if isinstance(price, int) else None,
                "created": created,
                "thumb": THUMB_TEMPLATE.format(asset_id=int(asset_id)),
            })

        cursor = j.get("nextPageCursor") or ""
        if not cursor:
            break

        time.sleep(0.65)

    seen: Set[int] = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        if it["assetId"] in seen:
            continue
        seen.add(it["assetId"])
        out.append(it)

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

def safe_update(path: str, creator_type: int, creator_target_id: int) -> None:
    prev = read_json(path)
    try:
        items = fetch_catalog_details(creator_type, creator_target_id)
        write_json(path, {"generatedAt": now_iso(), "items": items})
        print(f"[ok] {path}: {len(items)} UGC items")
    except Exception as e:
        print(f"[warn] {path}: keep previous ({e})")
        if prev is None:
            write_json(path, {"generatedAt": now_iso(), "items": []})

def main() -> None:
    time.sleep(4.0 + random.random() * 12.0)
    safe_update("data_user.json", 1, USER_ID)
    time.sleep(8.0 + random.random() * 14.0)
    safe_update("data_group.json", 2, GROUP_ID)

if __name__ == "__main__":
    main()
