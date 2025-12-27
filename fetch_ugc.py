#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_ugc.py (v2 - stable GitHub Actions)

Pourquoi ça plantait ?
- GitHub Actions se prend parfois un blocage (HTTP 429) sur catalog.roblox.com, surtout sur /v1/search/items/details.
- Résultat : le workflow échoue et ton site reste vide.

Fix v2 :
1) Utilise l'endpoint plus léger : https://catalog.roblox.com/v1/search/items
2) Si le GROUP fetch est rate-limit (429) => on NE PLANTE PAS :
   - on garde le dernier data_group.json existant (site reste fonctionnel)
3) Re-tries/backoff sur 429/5xx
4) Les dates de création se remplissent progressivement (economy endpoint limité), et sont mises en cache.

Fichiers générés :
- data_user.json
- data_group.json
"""

import json
import time
import random
import datetime
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from typing import Any, Dict, List, Optional, Tuple

USER_ID = 828726934
GROUP_ID = 16981319

# Endpoint "léger" (liste + pagination)
CATALOG_LIST = "https://catalog.roblox.com/v1/search/items"
# Détails (date) : plus rate-limité, donc on le limite
ECONOMY_DETAILS = "https://economy.roblox.com/v2/assets/{asset_id}/details"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "PortfolioUGCFetch/2.0 (+https://roblox.com)",
}

# ---------- helpers ----------
def read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def iso_to_ts(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        s = iso.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(s)
        return int(dt.timestamp())
    except Exception:
        return None

def load_created_cache(path: str) -> Dict[int, str]:
    j = read_json(path) or {}
    out: Dict[int, str] = {}
    for it in (j.get("items") or []):
        aid = it.get("assetId")
        created = it.get("created")
        if isinstance(aid, int) and isinstance(created, str) and created:
            out[aid] = created
    return out

def http_get_json(url: str, timeout: int = 30, max_retries: int = 10) -> Dict[str, Any]:
    """
    Robust GET with retries for 429/5xx and transient errors.
    Uses Retry-After when available, and increases delay if repeated.
    """
    last_err: Optional[Exception] = None
    base_extra = 0.0

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8", errors="replace")
            return json.loads(raw)

        except HTTPError as e:
            last_err = e
            code = getattr(e, "code", None)

            if code in (429, 500, 502, 503, 504):
                retry_after = None
                try:
                    retry_after = e.headers.get("Retry-After")
                except Exception:
                    retry_after = None

                if retry_after and str(retry_after).strip().isdigit():
                    # si Roblox dit 5s mais qu'on le reprend 10 fois, on augmente progressivement
                    base = float(int(retry_after))
                    base_extra += base * 0.75
                    sleep_s = min(120.0, base + base_extra + random.random() * 1.5)
                else:
                    sleep_s = min(120.0, (2.0 * (2 ** attempt)) + random.random() * 1.8)

                print(f"[http] HTTP {code} -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_s)
                continue

            raise

        except URLError as e:
            last_err = e
            sleep_s = min(60.0, (1.5 * (2 ** attempt)) + random.random())
            print(f"[http] URLError -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
            time.sleep(sleep_s)
            continue

        except Exception as e:
            last_err = e
            sleep_s = min(60.0, (1.5 * (2 ** attempt)) + random.random())
            print(f"[http] Error -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
            time.sleep(sleep_s)
            continue

    raise RuntimeError(f"GET failed after {max_retries} retries: {url} / last_err={last_err}")

# ---------- Roblox fetch ----------
def fetch_created_from_economy(asset_id: int) -> Optional[str]:
    try:
        url = ECONOMY_DETAILS.format(asset_id=asset_id)
        j = http_get_json(url, max_retries=6)
        for k in ("Created", "created", "createdUtc", "created_at", "createdAt"):
            v = j.get(k)
            if isinstance(v, str) and v:
                return v
    except Exception:
        return None
    return None

def fetch_all_catalog_items_v1(creator_type: int, creator_target_id: int, limit: int = 30, max_pages: int = 250) -> List[Dict[str, Any]]:
    """
    Endpoint:
      https://catalog.roblox.com/v1/search/items
    Pagination via cursor.
    """
    items: List[Dict[str, Any]] = []
    cursor: str = ""

    for _ in range(max_pages):
        params = {
            "category": "1",
            "creatorType": str(creator_type),            # 1 user, 2 group
            "creatorTargetId": str(creator_target_id),
            "includeNotForSale": "true",
            "limit": str(limit),
        }
        if cursor:
            params["cursor"] = cursor

        url = CATALOG_LIST + "?" + urllib.parse.urlencode(params)
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

        # cursor
        cursor = j.get("nextPageCursor") or j.get("nextPageCursor".lower()) or ""
        if not cursor:
            break

        time.sleep(0.35)

    # Deduplicate by assetId
    seen = set()
    dedup = []
    for it in items:
        if it["assetId"] in seen:
            continue
        seen.add(it["assetId"])
        dedup.append(it)
    return dedup

def enrich_created_dates(items: List[Dict[str, Any]], cache: Dict[int, str], hard_cap: int = 20) -> None:
    """
    Fill missing created dates using:
    1) cache from previous JSON
    2) economy details (LIMITED per run)
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
            continue

        created = fetch_created_from_economy(aid)
        if created:
            it["created"] = created
            cache[aid] = created

        used += 1
        time.sleep(0.25)

def finalize(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for it in items:
        it["createdTs"] = iso_to_ts(it.get("created"))
    items.sort(key=lambda x: (x.get("createdTs") or -1, x["assetId"]), reverse=True)
    return items

# ---------- Safe update per section ----------
def safe_update(label: str, creator_type: int, creator_target_id: int, json_path: str) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Returns: (success, items, generatedAt)
    If blocked / fails => keep previous json (success=False but no crash).
    """
    prev = read_json(json_path) or {"generatedAt": None, "items": []}
    prev_items = prev.get("items") or []
    prev_gen = prev.get("generatedAt") or None

    cache = load_created_cache(json_path)

    try:
        items = fetch_all_catalog_items_v1(creator_type=creator_type, creator_target_id=creator_target_id)
        enrich_created_dates(items, cache, hard_cap=20)
        items = finalize(items)

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        write_json(json_path, {"generatedAt": now_iso, "items": items})
        print(f"[ok] {label}: items={len(items)}")
        return True, items, now_iso

    except Exception as e:
        # Keep previous file untouched (no overwrite) if it exists,
        # BUT if file doesn't exist yet, write an empty payload so the site still loads.
        print(f"[warn] {label}: fetch failed -> keeping previous data. err={e}")

        if prev_gen is None:
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
            write_json(json_path, {"generatedAt": now_iso, "items": []})
            return False, [], now_iso

        return False, prev_items, str(prev_gen)

def main() -> None:
    # User first (often works), Group after (sometimes rate-limited)
    safe_update("USER", creator_type=1, creator_target_id=USER_ID, json_path="data_user.json")
    # small random delay before group to reduce bursts from shared runners
    time.sleep(2.5 + random.random() * 2.0)
    safe_update("GROUP", creator_type=2, creator_target_id=GROUP_ID, json_path="data_group.json")

if __name__ == "__main__":
    main()
