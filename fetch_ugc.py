#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_ugc.py (v3 - anti-boucle 429)

Tu vois des lignes en boucle du style:
  [http] HTTP 429 -> sleep ...

=> Roblox rate-limit les IP de GitHub Actions (datacenter).
v3 corrige ça en mode "fail-open":
- On tente quelques retries, puis on ARRÊTE de marteler l'API.
- Si c'est rate-limité, on garde le dernier JSON existant (le site reste OK).
- Le workflow finit en succès (pas de job bloqué pendant des minutes).

Le site (index.html) lit:
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

CATALOG_LIST = "https://catalog.roblox.com/v1/search/items"
ECONOMY_DETAILS = "https://economy.roblox.com/v2/assets/{asset_id}/details"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "PortfolioUGCFetch/3.0 (+https://roblox.com)",
}

class RateLimited(Exception):
    pass

# ---------- IO ----------
def read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

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

# ---------- HTTP ----------
def http_get_json(url: str, timeout: int = 30, max_retries: int = 4, max_sleep: float = 60.0) -> Dict[str, Any]:
    """
    Retries on 429/5xx a few times, then gives up with RateLimited.
    IMPORTANT: on 429 we stop quickly to avoid infinite loops.
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

            if code == 429:
                # Respect Retry-After, but don't loop forever
                retry_after = None
                try:
                    retry_after = e.headers.get("Retry-After")
                except Exception:
                    retry_after = None

                if retry_after and str(retry_after).strip().isdigit():
                    sleep_s = float(int(retry_after))
                else:
                    sleep_s = 6.0 + random.random() * 2.5

                # increase a bit each attempt, but cap
                sleep_s = min(max_sleep, sleep_s + attempt * 6.0)

                print(f"[http] 429 -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_s)

                if attempt == max_retries - 1:
                    raise RateLimited(f"429 Too Many Requests for url={url}") from e
                continue

            if code in (500, 502, 503, 504):
                sleep_s = min(max_sleep, (2.0 * (2 ** attempt)) + random.random() * 1.5)
                print(f"[http] HTTP {code} -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(sleep_s)
                continue

            raise

        except URLError as e:
            last_err = e
            sleep_s = min(30.0, 2.0 + attempt * 2.5 + random.random())
            print(f"[http] URLError -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
            time.sleep(sleep_s)
            continue

        except Exception as e:
            last_err = e
            sleep_s = min(30.0, 2.0 + attempt * 2.5 + random.random())
            print(f"[http] Error -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
            time.sleep(sleep_s)
            continue

    raise RuntimeError(f"GET failed after retries: {url} / last_err={last_err}")

# ---------- Roblox ----------
def fetch_all_catalog_items(creator_type: int, creator_target_id: int, limit: int = 30, max_pages: int = 250) -> List[Dict[str, Any]]:
    """
    Endpoint: https://catalog.roblox.com/v1/search/items
    Pagination via cursor.
    """
    items: List[Dict[str, Any]] = []
    cursor: str = ""

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

        url = CATALOG_LIST + "?" + urllib.parse.urlencode(params)

        j = http_get_json(url, max_retries=4, max_sleep=60.0)
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

        time.sleep(0.45)  # slow down for stability

    # dedupe
    seen = set()
    dedup = []
    for it in items:
        if it["assetId"] in seen:
            continue
        seen.add(it["assetId"])
        dedup.append(it)
    return dedup

def fetch_created_from_economy(asset_id: int) -> Optional[str]:
    # economy endpoint can also rate-limit; keep it very light
    try:
        url = ECONOMY_DETAILS.format(asset_id=asset_id)
        j = http_get_json(url, max_retries=2, max_sleep=40.0)
        for k in ("Created", "created", "createdUtc", "created_at", "createdAt"):
            v = j.get(k)
            if isinstance(v, str) and v:
                return v
    except Exception:
        return None
    return None

def enrich_created_dates(items: List[Dict[str, Any]], cache: Dict[int, str], hard_cap: int = 12) -> None:
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

def safe_update(label: str, creator_type: int, creator_target_id: int, json_path: str) -> bool:
    """
    Try update. If rate-limited / error => keep previous JSON and return False.
    Never crashes the workflow.
    """
    prev = read_json(json_path) or {"generatedAt": None, "items": []}
    prev_gen = prev.get("generatedAt")
    prev_items = prev.get("items") or []

    cache = load_created_cache(json_path)

    try:
        items = fetch_all_catalog_items(creator_type, creator_target_id)
        enrich_created_dates(items, cache, hard_cap=12)
        items = finalize(items)

        write_json(json_path, {"generatedAt": now_iso(), "items": items})
        print(f"[ok] {label}: items={len(items)}")
        return True

    except RateLimited as e:
        # Keep previous data
        print(f"[warn] {label}: rate-limited (429). Keeping previous JSON.")
        if prev_gen is None:
            write_json(json_path, {"generatedAt": now_iso(), "items": []})
        else:
            # keep file as-is (no overwrite)
            pass
        return False

    except Exception as e:
        print(f"[warn] {label}: error. Keeping previous JSON. err={e}")
        if prev_gen is None:
            write_json(json_path, {"generatedAt": now_iso(), "items": []})
        else:
            pass
        return False

def main() -> None:
    # Random start delay to avoid hitting Roblox at same time as other runners
    time.sleep(6.0 + random.random() * 8.0)

    # USER
    safe_update("USER", 1, USER_ID, "data_user.json")

    # Small delay before GROUP
    time.sleep(10.0 + random.random() * 10.0)

    # GROUP
    safe_update("GROUP", 2, GROUP_ID, "data_group.json")

if __name__ == "__main__":
    main()
