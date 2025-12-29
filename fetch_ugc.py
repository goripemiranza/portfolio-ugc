#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fetch_ugc.py
- Récupère TOUTES les créations Avatar (accessoires / vêtements / animations / corps) d'un USER + d'un GROUPE
- Génère: data_user.json et data_group.json
- Ajoute favorites (favoris) pour affichage dans le portfolio

Notes:
- Catalog v2 ne supporte pas toujours Category/Subcategory correctement.
- Approche robuste: requêtes par AssetTypeIds + pagination cursor + dédoublonnage.
"""

from __future__ import annotations

import json
import time
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# -------------------- CONFIG --------------------
USER_ID  = 828726934   # <= modifie si besoin
GROUP_ID = 16981319    # <= modifie si besoin

# CreatorType pour le Catalog API v2
CREATOR_USER  = "User"
CREATOR_GROUP = "Group"

# API bases (fallback)
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

CATALOG_SEARCH_PATH = "/v2/search/items/details"
ECONOMY_DETAILS_PATH = "/v2/assets/{asset_id}/details"
THUMBS_ASSET_PATH = "/v1/assets"

# Favorites count (optionnel). On privilégie "favoriteCount" renvoyé par /v2/search.
FAV_COUNT_PATH = "/v1/favorites/assets/{asset_id}/count"
FAV_BASES = [
    "https://catalog.roblox.com",
    "https://catalog.roproxy.com",
]

# Roblox AssetType (avatar / marketplace)
# Source: Enum.AssetType (et listages publics)
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

ALLOWED_ASSET_TYPE_IDS: List[int] = sorted(ASSET_TYPE_NAME.keys())

# Search tuning
LIMIT = 30
MAX_PAGES = 60
SLEEP_BETWEEN_CALLS = (0.18, 0.38)

UA = "portfolio-ugc-bot/13 (+https://github.com/goripemiranza/portfolio-ugc)"


# -------------------- HTTP helpers --------------------
def _sleep():
    time.sleep(random.uniform(*SLEEP_BETWEEN_CALLS))


def http_get_json_with_fallback(
    bases: List[str],
    path: str,
    params: Optional[Dict[str, Any]] = None,
    *,
    retries: int = 5,
    timeout: int = 30,
) -> Any:
    last_err: Optional[Exception] = None

    query = ""
    if params:
        query = "?" + urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)

    for base in bases:
        url = base + path + query
        attempt = 0
        while attempt <= retries:
            attempt += 1
            try:
                req = Request(url, headers={"User-Agent": UA})
                with urlopen(req, timeout=timeout) as r:
                    data = r.read().decode("utf-8", errors="replace")
                    return json.loads(data)
            except HTTPError as e:
                # 429: rate limited
                if e.code == 429:
                    wait = min(8.0, 0.6 * attempt + random.random())
                    time.sleep(wait)
                    continue
                last_err = e
                break
            except (URLError, TimeoutError) as e:
                last_err = e
                wait = min(8.0, 0.6 * attempt + random.random())
                time.sleep(wait)
                continue

    raise RuntimeError(f"HTTP failed for {path}: {last_err}")


# -------------------- Catalog fetch --------------------
def chunked(lst: List[int], size: int) -> List[List[int]]:
    return [lst[i:i+size] for i in range(0, len(lst), size)]


def fetch_catalog_assets_for_creator(
    creator_type: str,
    creator_target_id: int,
    asset_type_ids: List[int],
) -> Dict[int, Dict[str, Any]]:
    """
    Retourne un dict: assetId -> seed info (favoriteCount, assetType, name, price, etc)
    """
    out: Dict[int, Dict[str, Any]] = {}

    def fetch_with_asset_type_ids(asset_type_ids_param: str) -> None:
        cursor: Optional[str] = None
        for _ in range(MAX_PAGES):
            params = {
                "categoryFilter": "CommunityCreations",
                "CreatorType": creator_type,
                "CreatorTargetId": creator_target_id,
                "SortType": 6,                 # RecentlyCreated
                "Limit": LIMIT,
                "includeNotForSale": "true",
                "AssetTypeIds": asset_type_ids_param,
                "Cursor": cursor,
            }

            j = http_get_json_with_fallback(CATALOG_BASES, CATALOG_SEARCH_PATH, params)
            data = j.get("data") or []
            for it in data:
                if it.get("itemType") != "Asset":
                    continue
                aid = int(it.get("id"))
                at = int(it.get("assetType") or 0)
                if at and at not in ALLOWED_ASSET_TYPE_IDS:
                    continue

                out[aid] = {
                    "favoriteCount": int(it.get("favoriteCount") or 0),
                    "assetTypeId": at,
                    "name": it.get("name") or "",
                    "price": it.get("price"),
                    "priceStatus": it.get("priceStatus"),
                }

            cursor = j.get("nextPageCursor")
            if not cursor:
                break
            _sleep()

    # On chunk pour limiter les appels.
    # Si jamais la liste "AssetTypeIds=1,2,3" n'est pas supportée, on fallback en 1 par 1.
    for chunk in chunked(asset_type_ids, 10):
        try:
            fetch_with_asset_type_ids(",".join(str(x) for x in chunk))
        except Exception:
            for single in chunk:
                try:
                    fetch_with_asset_type_ids(str(single))
                except Exception:
                    pass
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
    # Normalisation
    if isinstance(c_type, str):
        c_type = c_type.capitalize()
    try:
        return int(c_id) == int(expected_id) and str(c_type) == str(expected_type)
    except Exception:
        return False


def get_price(details: Dict[str, Any]) -> int:
    # PriceInRobux est le plus fréquent
    for k in ("PriceInRobux", "Price", "price"):
        v = details.get(k)
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            return int(v)
    # Free/offsale -> 0
    return 0


def get_created(details: Dict[str, Any]) -> str:
    return str(details.get("Created") or details.get("created") or "")


def get_type(details: Dict[str, Any]) -> Tuple[int, str]:
    at = details.get("AssetTypeId") or details.get("AssetType") or details.get("assetTypeId") or 0
    try:
        at_id = int(at)
    except Exception:
        at_id = 0
    return at_id, ASSET_TYPE_NAME.get(at_id, f"AssetType{at_id}")


# -------------------- Thumbnails --------------------
def fetch_thumbnails(asset_ids: List[int], size: str = "420x420") -> Dict[int, str]:
    if not asset_ids:
        return {}

    out: Dict[int, str] = {}
    # batch (API accepte souvent une liste)
    for batch in chunked(asset_ids, 100):
        params = {
            "assetIds": ",".join(str(x) for x in batch),
            "size": size,
            "format": "Png",
            "isCircular": "false",
        }
        j = http_get_json_with_fallback(THUMBS_BASES, THUMBS_ASSET_PATH, params)
        for it in (j.get("data") or []):
            try:
                aid = int(it.get("targetId"))
                url = it.get("imageUrl") or ""
                out[aid] = url
            except Exception:
                pass
        _sleep()
    return out


# -------------------- Favorites fallback --------------------
def fetch_favorite_count(asset_id: int) -> int:
    path = FAV_COUNT_PATH.format(asset_id=asset_id)
    try:
        j = http_get_json_with_fallback(FAV_BASES, path, None, retries=2, timeout=15)
        if isinstance(j, int):
            return int(j)
        if isinstance(j, dict) and "count" in j:
            return int(j["count"])
    except Exception:
        pass
    return 0


# -------------------- Build JSON --------------------
def build_items_for_creator(creator_type: str, creator_id: int) -> List[Dict[str, Any]]:
    seeds = fetch_catalog_assets_for_creator(creator_type, creator_id, ALLOWED_ASSET_TYPE_IDS)
    asset_ids = sorted(seeds.keys(), reverse=True)

    thumbs = fetch_thumbnails(asset_ids)

    items: List[Dict[str, Any]] = []
    for i, aid in enumerate(asset_ids):
        try:
            details = fetch_asset_details(aid)
        except Exception:
            continue

        # sécurité: on garde uniquement ce qui appartient bien au creator
        if not creator_matches(details, creator_type, creator_id):
            continue

        at_id, at_name = get_type(details)
        if at_id not in ALLOWED_ASSET_TYPE_IDS:
            continue

        seed = seeds.get(aid) or {}
        favorites = int(seed.get("favoriteCount") or 0)
        if favorites == 0:
            # fallback léger
            favorites = fetch_favorite_count(aid)

        item = {
            "assetId": aid,
            "name": str(details.get("Name") or seed.get("name") or ""),
            "type": at_name,
            "assetTypeId": at_id,
            "created": get_created(details),
            "price": get_price(details),
            "thumb": thumbs.get(aid, ""),
            "favorites": favorites,
        }
        items.append(item)

        # throttle
        if (i + 1) % 10 == 0:
            _sleep()

    # tri final: plus récent
    items.sort(key=lambda x: x.get("created") or "", reverse=True)
    return items


def write_json(path: str, items: List[Dict[str, Any]]) -> None:
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    print("Fetching USER creations...")
    user_items = build_items_for_creator(CREATOR_USER, USER_ID)
    print(f"USER items: {len(user_items)}")

    print("Fetching GROUP creations...")
    group_items = build_items_for_creator(CREATOR_GROUP, GROUP_ID)
    print(f"GROUP items: {len(group_items)}")

    write_json("data_user.json", user_items)
    write_json("data_group.json", group_items)

    print("Done.")


if __name__ == "__main__":
    main()
