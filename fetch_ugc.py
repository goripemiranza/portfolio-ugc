#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_ugc.py (v5)

Objectifs :
1) Récupérer les items du profil (USER) + du groupe (GROUP)
2) Ajouter aussi les items des membres "staff" du groupe (selon rôles élevés)
3) Renseigner (quand possible) le prix via l'Economy API
4) Ne jamais faire échouer le workflow : si 429 => on garde les JSON existants

Notes importantes :
- Roblox rate-limit très fort les IP de GitHub Actions (HTTP 429). Ce script "fail-open".
- Les infos (prix/dates) se remplissent progressivement grâce au cache JSON.
"""

import json
import time
import random
import datetime
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from typing import Any, Dict, List, Optional, Set, Tuple

USER_ID = 828726934
GROUP_ID = 16981319

CATALOG_LIST = "https://catalog.roblox.com/v1/search/items"
ECONOMY_DETAILS = "https://economy.roblox.com/v2/assets/{asset_id}/details"
GROUP_ROLES = "https://groups.roblox.com/v1/groups/{group_id}/roles"
GROUP_ROLE_USERS = "https://groups.roblox.com/v1/groups/{group_id}/roles/{role_id}/users?limit=100&sortOrder=Asc&cursor={cursor}"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "PortfolioUGCFetch/5.0 (+https://roblox.com)",
}

class RateLimited(Exception):
    pass

# Stop rapidement si trop de 429 dans le run
RATE_LIMIT_HITS = 0
RATE_LIMIT_BUDGET = 4  # au-delà => on stop la section

# Staff selection (ajuste si besoin)
STAFF_RANK_MIN = 200
STAFF_ROLE_NAME_HINTS = ("owner", "admin", "staff", "dev", "developer", "ugc", "artist", "mod")
STAFF_USER_CAP = 60  # cap de membres staff à scanner (anti-spam API)

# Economy enrichment caps (anti-429)
ECONOMY_ENRICH_CAP_USER = 20
ECONOMY_ENRICH_CAP_GROUP = 25

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

def iso_to_ts(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        s = iso.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(s)
        return int(dt.timestamp())
    except Exception:
        return None

def load_cache(path: str) -> Dict[int, Dict[str, Any]]:
    """
    Cache par assetId -> {created, price}
    """
    j = read_json(path) or {}
    out: Dict[int, Dict[str, Any]] = {}
    for it in (j.get("items") or []):
        aid = it.get("assetId")
        if not isinstance(aid, int):
            continue
        out[aid] = {}
        if isinstance(it.get("created"), str) and it.get("created"):
            out[aid]["created"] = it["created"]
        if isinstance(it.get("price"), (int, float)):
            out[aid]["price"] = int(it["price"])
    return out

def http_get_json(url: str, timeout: int = 30, max_retries: int = 2) -> Dict[str, Any]:
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

                print(f"[http] 429 -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries})")
                time.sleep(min(10.0, sleep_s))

                if attempt == max_retries - 1:
                    raise RateLimited("429 after retries") from e
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

def pick_first_str(d: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[str]:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v:
            return v
    return None

def pick_first_int(d: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[int]:
    for k in keys:
        v = d.get(k)
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
    return None

def fetch_catalog_items(creator_type: int, creator_target_id: int, limit: int = 30, max_pages: int = 200) -> List[Dict[str, Any]]:
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
        j = http_get_json(url)

        data = j.get("data", []) or []
        for d in data:
            # Certains items peuvent avoir assetId en plus de id
            aid = pick_first_int(d, ("assetId", "asset_id"))
            if aid is None:
                aid = pick_first_int(d, ("id",))
            if aid is None:
                continue

            name = pick_first_str(d, ("name", "itemName", "title")) or f"Item {aid}"

            asset_type = None
            at = d.get("assetType")
            if isinstance(at, dict):
                asset_type = pick_first_str(at, ("name",))
            asset_type = asset_type or pick_first_str(d, ("assetTypeName", "itemType", "type")) or "UGC"

            # price might be present for on-sale
            price = pick_first_int(d, ("price", "lowestPrice", "priceInRobux", "priceInRobux"))
            created = pick_first_str(d, ("created", "Created", "createdUtc", "createdAt"))

            items.append({
                "assetId": int(aid),
                "name": name,
                "type": asset_type,
                "price": price,
                "created": created,
            })

        cursor = j.get("nextPageCursor") or ""
        if not cursor:
            break

        time.sleep(0.65)

    # dedupe by assetId
    seen: Set[int] = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        if it["assetId"] in seen:
            continue
        seen.add(it["assetId"])
        out.append(it)
    return out

def economy_enrich(items: List[Dict[str, Any]], cache: Dict[int, Dict[str, Any]], cap: int) -> None:
    """
    Enrich created + price from economy details, limited per run.
    """
    used = 0
    for it in items:
        aid = it["assetId"]

        # Cache first
        c = cache.get(aid, {})
        if not it.get("created") and isinstance(c.get("created"), str):
            it["created"] = c["created"]
        if not isinstance(it.get("price"), int) and isinstance(c.get("price"), int):
            it["price"] = c["price"]

        # If still missing, call economy (limited)
        if used >= cap:
            continue
        if it.get("created") and isinstance(it.get("price"), int):
            continue

        try:
            url = ECONOMY_DETAILS.format(asset_id=aid)
            j = http_get_json(url, max_retries=1)

            # Created
            created = pick_first_str(j, ("Created", "created", "createdUtc", "created_at", "createdAt"))
            if created and not it.get("created"):
                it["created"] = created

            # Price fields (best-effort, depends on item type)
            p = pick_first_int(j, ("PriceInRobux", "priceInRobux", "Price", "price"))
            if isinstance(p, int):
                it["price"] = p

            # update cache
            cache.setdefault(aid, {})
            if it.get("created"):
                cache[aid]["created"] = it["created"]
            if isinstance(it.get("price"), int):
                cache[aid]["price"] = it["price"]

        except Exception:
            pass

        used += 1
        time.sleep(0.35)

def finalize(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for it in items:
        it["createdTs"] = iso_to_ts(it.get("created"))
    items.sort(key=lambda x: (x.get("createdTs") or -1, x["assetId"]), reverse=True)
    return items

def fetch_group_staff_user_ids(group_id: int) -> List[int]:
    """
    Récupère une liste de userIds "staff" (rôles élevés / noms de rôles).
    Cap à STAFF_USER_CAP.
    """
    try:
        roles = http_get_json(GROUP_ROLES.format(group_id=group_id)).get("roles", []) or []
    except Exception:
        return []

    picked_role_ids: List[int] = []
    for r in roles:
        if not isinstance(r, dict):
            continue
        role_id = r.get("id")
        rank = r.get("rank")
        name = (r.get("name") or "").lower()

        if isinstance(role_id, int):
            if isinstance(rank, int) and rank >= STAFF_RANK_MIN:
                picked_role_ids.append(role_id)
            elif any(h in name for h in STAFF_ROLE_NAME_HINTS):
                picked_role_ids.append(role_id)

    # unique, higher ranks first (best effort)
    picked_role_ids = list(dict.fromkeys(picked_role_ids))[:10]

    user_ids: List[int] = []
    seen: Set[int] = set()

    for role_id in picked_role_ids:
        cursor = ""
        for _ in range(5):  # pagination cap
            try:
                url = GROUP_ROLE_USERS.format(group_id=group_id, role_id=role_id, cursor=urllib.parse.quote(cursor))
                j = http_get_json(url, max_retries=1)
                for u in (j.get("data") or []):
                    uid = u.get("userId")
                    if isinstance(uid, int) and uid not in seen:
                        seen.add(uid)
                        user_ids.append(uid)
                        if len(user_ids) >= STAFF_USER_CAP:
                            return user_ids
                cursor = j.get("nextPageCursor") or ""
                if not cursor:
                    break
                time.sleep(0.25)
            except Exception:
                break

    return user_ids

def safe_write_if_no_previous(path: str) -> None:
    prev = read_json(path)
    if prev is None:
        write_json(path, {"generatedAt": now_iso(), "items": []})

def safe_update_user() -> None:
    cache = load_cache("data_user.json")
    try:
        items = fetch_catalog_items(creator_type=1, creator_target_id=USER_ID)
        economy_enrich(items, cache, cap=ECONOMY_ENRICH_CAP_USER)
        items = finalize(items)
        write_json("data_user.json", {"generatedAt": now_iso(), "items": items})
        print(f"[ok] USER items={len(items)}")
    except RateLimited:
        print("[warn] USER rate-limited => keep previous")
        safe_write_if_no_previous("data_user.json")
    except Exception as e:
        print(f"[warn] USER error => keep previous ({e})")
        safe_write_if_no_previous("data_user.json")

def safe_update_group_with_staff() -> None:
    cache = load_cache("data_group.json")
    try:
        group_items = fetch_catalog_items(creator_type=2, creator_target_id=GROUP_ID)

        # staff members UGC (best-effort, can be empty if rate-limited)
        staff_ids = fetch_group_staff_user_ids(GROUP_ID)
        staff_items: List[Dict[str, Any]] = []
        for uid in staff_ids:
            try:
                # limit pages per staff to reduce load (still captures most creators)
                staff_items.extend(fetch_catalog_items(creator_type=1, creator_target_id=uid, max_pages=8))
                time.sleep(0.35)
            except Exception:
                continue

        # merge + dedupe
        merged: Dict[int, Dict[str, Any]] = {}
        for it in (group_items + staff_items):
            merged[it["assetId"]] = it
        items = list(merged.values())

        economy_enrich(items, cache, cap=ECONOMY_ENRICH_CAP_GROUP)
        items = finalize(items)

        write_json("data_group.json", {"generatedAt": now_iso(), "items": items})
        print(f"[ok] GROUP+STAFF items={len(items)} (group={len(group_items)} staff={len(staff_items)} staffUsers={len(staff_ids)})")

    except RateLimited:
        print("[warn] GROUP rate-limited => keep previous")
        safe_write_if_no_previous("data_group.json")
    except Exception as e:
        print(f"[warn] GROUP error => keep previous ({e})")
        safe_write_if_no_previous("data_group.json")

def main() -> None:
    # start jitter (avoid being sync with other GH runners)
    time.sleep(6.0 + random.random() * 10.0)

    safe_update_user()

    # pause before group
    time.sleep(10.0 + random.random() * 12.0)

    safe_update_group_with_staff()

if __name__ == "__main__":
    main()
