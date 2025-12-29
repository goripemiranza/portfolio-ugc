#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fetch_ugc.py (v15)
- Récupère TOUTES les créations Avatar d'un USER + d'un GROUPE (accessoires / vêtements / animations / corps)
- Ne garde QUE les items EN VENTE et PAYANTS (PriceInRobux > 0)
- Ajoute favorites (favoris) si dispo via Catalog, sinon fallback léger
- Génère: data_user.json et data_group.json
"""

from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# -------------------- CONFIG --------------------
USER_ID  = 828726934   # <= à modifier si besoin
GROUP_ID = 16981319    # <= à modifier si besoin

# Catalog v2: CreatorType (numérique)
CREATOR_USER  = 1
CREATOR_GROUP = 2

CATALOG_BASES = [
    "https://catalog.roblox.com",
    "https://catalog.roproxy.com",
]
ECONOMY_BASES = [
    "https://economy.roblox.com",
    "https://economy.roproxy.com",
]
THUMBS_BASES = [
    "https://thumbnails.roblox.com",
    "https://thumbnails.roproxy.com",
]
FAV_BASES = [
    "https://www.roblox.com",
    "https://www.roproxy.com",
]

CATALOG_SEARCH_PATH     = "/v2/search/items/details"
ECONOMY_DETAILS_PATH    = "/v2/assets/{asset_id}/details"
THUMBS_ASSET_PATH       = "/v1/assets"
FAV_COUNT_PATH          = "/v1/favorites/assets/{asset_id}/count"

UA = "portfolio-ugc-bot/15 (+https://github.com/goripemiranza/portfolio-ugc)"

# -------------------- Roblox AssetTypes (Avatar Shop) --------------------
ASSET_TYPE_NAME: Dict[int, str] = {
    # Accessories
    8:  "Hat",
    41: "HairAccessory",
    42: "FaceAccessory",
    43: "NeckAccessory",
    44: "ShoulderAccessory",
    45: "FrontAccessory",
    46: "BackAccessory",
    47: "WaistAccessory",
    57: "EarAccessory",
    58: "EyeAccessory",
    76: "EyebrowAccessory",
    77: "EyelashAccessory",

    # Clothing (classic)
    2:  "TShirt",
    11: "Shirt",
    12: "Pants",

    # Clothing (layered)
    64: "TShirtAccessory",
    65: "ShirtAccessory",
    66: "PantsAccessory",
    67: "JacketAccessory",
    68: "SweaterAccessory",
    69: "ShortsAccessory",
    70: "LeftShoeAccessory",
    71: "RightShoeAccessory",
    72: "DressSkirtAccessory",

    # Body
    17: "Head",
    18: "Face",
    79: "DynamicHead",

    # Animations
    24: "Animation",
    48: "ClimbAnimation",
    49: "DeathAnimation",
    50: "FallAnimation",
    51: "IdleAnimation",
    52: "JumpAnimation",
    53: "RunAnimation",
    54: "SwimAnimation",
    55: "WalkAnimation",
    56: "PoseAnimation",
    61: "EmoteAnimation",
    78: "MoodAnimation",
}

ALLOWED_ASSET_TYPE_IDS: Set[int] = set(ASSET_TYPE_NAME.keys())

# tuning
LIMIT = 30
MAX_PAGES = 120
SLEEP_BETWEEN_CALLS = (0.20, 0.45)


# -------------------- utils --------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _sleep():
    time.sleep(random.uniform(*SLEEP_BETWEEN_CALLS))

def read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None

def write_json_atomic(path: str, payload: Dict[str, Any]) -> None:
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

def http_get_json_with_fallback(
    bases: List[str],
    path: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    timeout: int = 30,
    retries: int = 6,
) -> Any:
    query = ""
    if params:
        query = "?" + urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)

    last_err: Optional[Exception] = None

    # randomize bases a bit
    bases = list(bases)
    random.shuffle(bases)

    for base in bases:
        url = base + path + query
        for attempt in range(1, retries + 1):
            try:
                req = Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
                with urlopen(req, timeout=timeout) as r:
                    raw = r.read().decode("utf-8", errors="replace")
                return json.loads(raw)
            except HTTPError as e:
                last_err = e
                code = getattr(e, "code", None)
                if code == 429 or code in (500, 502, 503, 504):
                    time.sleep(min(20.0, 1.2 * attempt + random.random() * 2.0))
                    continue
                break
            except (URLError, TimeoutError) as e:
                last_err = e
                time.sleep(min(20.0, 1.1 * attempt + random.random() * 2.0))
                continue
            except Exception as e:
                last_err = e
                time.sleep(min(20.0, 1.1 * attempt + random.random() * 2.0))
                continue

    raise RuntimeError(f"HTTP failed for {path}: {last_err}")

def chunked(lst: List[int], size: int) -> List[List[int]]:
    return [lst[i:i+size] for i in range(0, len(lst), size)]


# -------------------- Catalog fetch (IDs + favorites seed) --------------------
def fetch_creator_seeds(creator_type: int, creator_target_id: int) -> Dict[int, Dict[str, Any]]:
    """
    Retour: assetId -> {favoriteCount, assetTypeId, name}
    """
    out: Dict[int, Dict[str, Any]] = {}
    cursor: Optional[str] = None

    for _ in range(MAX_PAGES):
        params = {
            "CreatorType": creator_type,
            "CreatorTargetId": creator_target_id,
            "SortType": 6,               # RecentlyCreated
            "Limit": LIMIT,
            "Category": 1,               # Avatar Shop
            "includeNotForSale": "true",
            "Cursor": cursor,
        }

        j = http_get_json_with_fallback(CATALOG_BASES, CATALOG_SEARCH_PATH, params)
        data = j.get("data") or []
        for it in data:
            if not isinstance(it, dict):
                continue
            if it.get("itemType") != "Asset":
                continue

            try:
                aid = int(it.get("id"))
            except Exception:
                continue

            at = it.get("assetType")
            try:
                at_id = int(at) if at is not None else 0
            except Exception:
                at_id = 0

            out[aid] = {
                "favoriteCount": int(it.get("favoriteCount") or 0),
                "assetTypeId": at_id,
                "name": it.get("name") or "",
            }

        cursor = j.get("nextPageCursor")
        if not cursor:
            break
        _sleep()

    return out


# -------------------- Economy details --------------------
def fetch_asset_details(asset_id: int) -> Dict[str, Any]:
    path = ECONOMY_DETAILS_PATH.format(asset_id=asset_id)
    return http_get_json_with_fallback(ECONOMY_BASES, path, None)

def creator_matches(details: Dict[str, Any], expected_type: str, expected_id: int) -> bool:
    c = details.get("Creator") or {}
    c_id = c.get("Id")
    c_type = c.get("CreatorType") or c.get("Type") or c.get("type")
    # normalize
    ct = str(c_type or "").strip().lower()
    try:
        return int(c_id) == int(expected_id) and ct == str(expected_type).strip().lower()
    except Exception:
        return False

def is_paid_and_for_sale(details: Dict[str, Any]) -> Tuple[bool, int]:
    if details.get("IsForSale") is not True:
        return (False, 0)
    price = details.get("PriceInRobux")
    if not isinstance(price, int):
        return (False, 0)
    if price <= 0:
        return (False, 0)
    return (True, price)

def get_created(details: Dict[str, Any]) -> str:
    return str(details.get("Created") or "")

def get_type(details: Dict[str, Any], seed: Dict[str, Any]) -> Tuple[int, str]:
    at = details.get("AssetTypeId") or seed.get("assetTypeId") or 0
    try:
        at_id = int(at)
    except Exception:
        at_id = 0
    return at_id, ASSET_TYPE_NAME.get(at_id, f"AssetType{at_id}")


# -------------------- Thumbnails --------------------
def fetch_thumbnails(asset_ids: List[int], size: str = "420x420") -> Dict[int, str]:
    out: Dict[int, str] = {}
    if not asset_ids:
        return out

    for batch in chunked(asset_ids, 100):
        params = {
            "assetIds": ",".join(str(x) for x in batch),
            "size": size,
            "format": "Png",
            "isCircular": "false",
        }
        j = http_get_json_with_fallback(THUMBS_BASES, THUMBS_ASSET_PATH, params, timeout=30, retries=6)
        for it in (j.get("data") or []):
            try:
                aid = int(it.get("targetId"))
                url = it.get("imageUrl") or ""
                state = it.get("state") or ""
                if url and (state == "Completed" or not state):
                    out[aid] = url
            except Exception:
                pass
        _sleep()

    return out


# -------------------- Favorites fallback --------------------
def fetch_favorite_count(asset_id: int) -> int:
    path = FAV_COUNT_PATH.format(asset_id=asset_id)
    try:
        j = http_get_json_with_fallback(FAV_BASES, path, None, timeout=20, retries=3)
        if isinstance(j, int):
            return int(j)
        if isinstance(j, dict) and "count" in j:
            return int(j["count"])
    except Exception:
        pass
    return 0


# -------------------- Build JSON --------------------
def build_items_for_creator(creator_type_num: int, creator_id: int) -> List[Dict[str, Any]]:
    expected_type_str = "User" if creator_type_num == CREATOR_USER else "Group"

    seeds = fetch_creator_seeds(creator_type_num, creator_id)
    asset_ids = sorted(seeds.keys(), reverse=True)

    items: List[Dict[str, Any]] = []
    for i, aid in enumerate(asset_ids):
        seed = seeds.get(aid) or {}

        try:
            details = fetch_asset_details(aid)
        except Exception:
            continue

        # sécurité: seulement ce creator
        if not creator_matches(details, expected_type_str, creator_id):
            continue

        ok, price = is_paid_and_for_sale(details)
        if not ok:
            continue

        at_id, at_name = get_type(details, seed)
        if at_id not in ALLOWED_ASSET_TYPE_IDS:
            continue

        favorites = int(seed.get("favoriteCount") or 0)
        if favorites <= 0:
            favorites = fetch_favorite_count(aid)

        name = str(details.get("Name") or seed.get("name") or "")
        created = get_created(details)

        items.append({
            "assetId": aid,
            "name": name,
            "type": at_name,
            "assetTypeId": at_id,
            "created": created,
            "price": price,
            "favorites": favorites,
            "thumb": "",  # inject later
        })

        if (i + 1) % 10 == 0:
            _sleep()

    # inject thumbs (rbxcdn)
    thumb_map = fetch_thumbnails([it["assetId"] for it in items])
    for it in items:
        it["thumb"] = thumb_map.get(it["assetId"], "")

    # sort newest by created (fallback assetId)
    def sort_key(x: Dict[str, Any]) -> Tuple[str, int]:
        return (str(x.get("created") or ""), int(x.get("assetId") or 0))
    items.sort(key=sort_key, reverse=True)
    return items


def update_file(out_path: str, creator_type_num: int, creator_id: int) -> None:
    prev = read_json(out_path)
    prev_items = prev.get("items") if isinstance(prev, dict) else None

    try:
        items = build_items_for_creator(creator_type_num, creator_id)
        if not items and isinstance(prev_items, list) and prev_items:
            # évite de vider si l'API a un souci temporaire
            return

        write_json_atomic(out_path, {"generatedAt": now_iso(), "items": items})
        print(f"[ok] {out_path}: {len(items)} item(s) en vente")
    except Exception as e:
        print(f"[warn] {out_path}: keep previous ({e})")
        if prev is None:
            write_json_atomic(out_path, {"generatedAt": now_iso(), "items": []})


def main() -> None:
    # petit jitter anti-burst
    time.sleep(2.0 + random.random() * 4.0)

    print("Fetching USER creations (on-sale only)...")
    update_file("data_user.json", CREATOR_USER, USER_ID)

    time.sleep(2.5 + random.random() * 5.0)

    print("Fetching GROUP creations (on-sale only)...")
    update_file("data_group.json", CREATOR_GROUP, GROUP_ID)

    print("Done.")

if __name__ == "__main__":
    main()
