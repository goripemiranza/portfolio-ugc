#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génère 2 fichiers utilisés par index.html :
- data_user.json  (UGC créés par l'utilisateur lulu8203)
- data_group.json (UGC créés par le groupe Powerful Artists)

⚠️ Fix principal :
- Gestion des erreurs 429 (Too Many Requests) avec retries + backoff
- Limitation des appels "economy details" (date de création) par run
- Réutilisation des dates déjà connues depuis les JSON existants (cache)

Résultat :
- Le workflow GitHub Actions ne plante plus.
- Les dates se remplissent progressivement au fil des runs (et restent ensuite en cache).
"""

import json
import time
import random
import datetime
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from typing import Any, Dict, List, Optional

USER_ID = 828726934
GROUP_ID = 16981319

CATALOG_ENDPOINT = "https://catalog.roblox.com/v1/search/items/details"
ECONOMY_DETAILS = "https://economy.roblox.com/v2/assets/{asset_id}/details"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "PortfolioUGCFetch/1.1 (+https://roblox.com)",
}

# --- Network helpers ---
def http_get_json(url: str, timeout: int = 30, max_retries: int = 8) -> Dict[str, Any]:
    """
    Robust GET with retries for 429/5xx and transient errors.
    Uses Retry-After header when available.
    """
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

            # Rate limit / transient server errors
            if code in (429, 500, 502, 503, 504):
                retry_after = None
                try:
                    retry_after = e.headers.get("Retry-After")
                except Exception:
                    retry_after = None

                if retry_after and str(retry_after).strip().isdigit():
                    sleep_s = min(90.0, float(int(retry_after)))
                else:
                    # exponential backoff + jitter
                    sleep_s = min(90.0, (1.6 * (2 ** attempt)) + random.random() * 1.3)

                print(f"[http] HTTP {code} on {url} -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_s)
                continue

            # other HTTP errors: fail fast
            raise

        except URLError as e:
            last_err = e
            sleep_s = min(60.0, (1.2 * (2 ** attempt)) + random.random())
            print(f"[http] URLError on {url} -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
            time.sleep(sleep_s)
            continue

        except Exception as e:
            last_err = e
            sleep_s = min(60.0, (1.2 * (2 ** attempt)) + random.random())
            print(f"[http] Error on {url} -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
            time.sleep(sleep_s)
            continue

    raise RuntimeError(f"GET failed after {max_retries} retries: {url} / last_err={last_err}")

def iso_to_ts(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        s = iso.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(s)
        return int(dt.timestamp())
    except Exception:
        return None

# --- Cache (reuse known dates from previous JSON) ---
def load_created_cache(path: str) -> Dict[int, str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            j = json.load(f)
        out: Dict[int, str] = {}
        for it in (j.get("items") or []):
            aid = it.get("assetId")
            created = it.get("created")
            if isinstance(aid, int) and isinstance(created, str) and created:
                out[aid] = created
        return out
    except Exception:
        return {}

# --- Roblox fetch ---
def fetch_created_from_economy(asset_id: int) -> Optional[str]:
    """
    Economy details is slower + rate limited.
    We call it sparingly and cache results.
    """
    try:
        url = ECONOMY_DETAILS.format(asset_id=asset_id)
        j = http_get_json(url)
        for k in ("Created", "created", "createdUtc", "created_at", "createdAt"):
            v = j.get(k)
            if isinstance(v, str) and v:
                return v
    except Exception:
        return None
    return None

def fetch_all_catalog_items(creator_type: int, creator_target_id: int, limit: int = 30, max_pages: int = 200) -> List[Dict[str, Any]]:
    """
    Pulls all catalog items for given creator (user or group), paginated.
    """
    items: List[Dict[str, Any]] = []
    cursor: str = ""

    for page in range(max_pages):
        params = {
            "CreatorType": str(creator_type),           # 1 user, 2 group
            "CreatorTargetId": str(creator_target_id),
            "Limit": str(limit),
            "IncludeNotForSale": "true",
        }
        if cursor:
            params["Cursor"] = cursor

        url = CATALOG_ENDPOINT + "?" + urllib.parse.urlencode(params)
        j = http_get_json(url)

        data = j.get("data", []) or []
        for d in data:
            asset_id = d.get("id")
            if not isinstance(asset_id, int):
                continue

            name = d.get("name") or f"Item {asset_id}"
            asset_type = None
            at = d.get("assetType")
            if isinstance(at, dict):
                asset_type = at.get("name")

            price = d.get("price")
            if not isinstance(price, (int, float)):
                price = None

            created = None
            for k in ("created", "Created", "createdUtc", "createdAt"):
                v = d.get(k)
                if isinstance(v, str) and v:
                    created = v
                    break

            items.append({
                "assetId": asset_id,
                "name": name,
                "type": asset_type or d.get("itemType") or "UGC",
                "price": int(price) if isinstance(price, (int, float)) else None,
                "created": created,
            })

        cursor = j.get("nextPageCursor") or ""
        if not cursor:
            break

        # gentle pacing between catalog pages (helps 429)
        time.sleep(0.25)

    # Deduplicate by assetId
    seen = set()
    dedup = []
    for it in items:
        if it["assetId"] in seen:
            continue
        seen.add(it["assetId"])
        dedup.append(it)
    return dedup

def enrich_created_dates(items: List[Dict[str, Any]], cache: Dict[int, str], hard_cap: int = 35) -> None:
    """
    Fill missing created dates using:
    1) cache from previous JSON
    2) economy details (limited per run to avoid 429)
    """
    used = 0
    for it in items:
        if it.get("created"):
            continue
        aid = it["assetId"]

        if aid in cache:
            it["created"] = cache[aid]
            continue

        if used >= hard_cap:
            continue  # keep missing, will be filled in later runs

        created = fetch_created_from_economy(aid)
        if created:
            it["created"] = created
            cache[aid] = created
        used += 1

        # pacing economy calls
        time.sleep(0.20)

def finalize(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for it in items:
        it["createdTs"] = iso_to_ts(it.get("created"))

    # Sort: newest first. Missing dates go to bottom (createdTs=None -> -1)
    items.sort(key=lambda x: (x.get("createdTs") or -1, x["assetId"]), reverse=True)
    return items

def write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def main() -> None:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    # Load cache from previous JSON (if any)
    user_cache = load_created_cache("data_user.json")
    group_cache = load_created_cache("data_group.json")

    print("[1/4] Fetch USER catalog…")
    user_items = fetch_all_catalog_items(creator_type=1, creator_target_id=USER_ID)
    print(f"  user_items={len(user_items)}")

    print("[2/4] Fetch GROUP catalog…")
    group_items = fetch_all_catalog_items(creator_type=2, creator_target_id=GROUP_ID)
    print(f"  group_items={len(group_items)}")

    # Fill missing created dates carefully (limit calls per run)
    print("[3/4] Enrich created dates (limited)…")
    enrich_created_dates(user_items, user_cache, hard_cap=35)
    enrich_created_dates(group_items, group_cache, hard_cap=35)

    user_items = finalize(user_items)
    group_items = finalize(group_items)

    write_json("data_user.json", {"generatedAt": now_iso, "items": user_items})
    write_json("data_group.json", {"generatedAt": now_iso, "items": group_items})

    print("[4/4] OK: data_user.json + data_group.json updated")

if __name__ == "__main__":
    main()
