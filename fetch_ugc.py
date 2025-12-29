#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
fetch_ugc.py (v12) — Portfolio Roblox

Objectif :
- Récupérer TOUTES les créations (Profil + Groupe) qui sont réellement achetables
  (en vente + prix > 0 + pas sold-out)
- Inclure les thumbnails rbxcdn (affichables sur GitHub/Cloudflare)
- Inclure le nombre de favoris par item

Sortie :
- data_user.json + data_group.json
  {
    "updated": "2025-12-29T22:26:06Z",
    "items": [
      {"assetId": 123, "name": "...", "type": "BackAccessory", "price": 100, "created": "...", "thumb": "...", "favorites": 999}
    ]
  }
'''

from __future__ import annotations

import json
import os
import time
import datetime as dt
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Set


# ========= CONFIG =========
USER_ID = int(os.getenv("ROBLOX_USER_ID", "828726934"))
GROUP_ID = int(os.getenv("ROBLOX_GROUP_ID", "16981319"))

LIMIT = 30
MAX_PAGES_PER_TYPE = 25  # stop earlier if cursor ends
REQUEST_TIMEOUT = 15
SLEEP_BETWEEN_CALLS = 0.12  # small throttle
RETRIES_PER_BASE = 3

CATALOG_BASES = ["https://catalog.roblox.com", "https://catalog.roproxy.com"]
ECONOMY_BASES = ["https://economy.roblox.com", "https://economy.roproxy.com"]
THUMB_BASES = ["https://thumbnails.roblox.com", "https://thumbnails.roproxy.com"]

# Favorite count endpoint
FAV_BASES = ["https://catalog.roblox.com", "https://catalog.roproxy.com"]
FAV_PATH = "/v1/favorites/assets/{assetId}/count"


# ========= ASSET TYPES (Roblox) =========
# Extension : accessoires + vêtements + têtes + animations (tout ce que Roblox propose côté Avatar)
ALLOWED_ASSET_TYPE_IDS: Set[int] = {
    # Classic clothing
    2, 11, 12,

    # Accessories
    8, 41, 42, 43, 44, 45, 46, 47, 57, 58, 76, 77,

    # Heads / Faces
    17, 18, 79,

    # Layered clothing
    64, 65, 66, 67, 68, 69, 70, 71, 72,

    # Animations
    24, 48, 49, 50, 51, 52, 53, 54, 55, 56, 61, 78,

    # Package (bundle-like)
    32,
}

ASSET_TYPE_NAME: Dict[int, str] = {
    # Classic clothing
    2: "TShirt",
    11: "Shirt",
    12: "Pants",

    # Accessories
    8: "Hat",
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

    # Heads / Faces
    17: "Head",
    18: "Face",
    79: "DynamicHead",

    # Layered clothing
    64: "TShirtAccessory",
    65: "ShirtAccessory",
    66: "PantsAccessory",
    67: "JacketAccessory",
    68: "SweaterAccessory",
    69: "ShortsAccessory",
    70: "LeftShoeAccessory",
    71: "RightShoeAccessory",
    72: "DressSkirtAccessory",

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

    32: "Package",
}


# ========= HTTP =========
def _get_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "portfolio-ugc-bot/1.0"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        data = resp.read().decode("utf-8", errors="replace")
        return json.loads(data)


def get_json_with_bases(bases: List[str], path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    last_err: Optional[Exception] = None
    qs = ""
    if params:
        qs = "?" + urllib.parse.urlencode(params, doseq=True)

    for base in bases:
        url = base.rstrip("/") + path + qs
        for attempt in range(RETRIES_PER_BASE):
            try:
                time.sleep(SLEEP_BETWEEN_CALLS)
                return _get_json(url)
            except Exception as e:
                last_err = e
                time.sleep(0.35 * (attempt + 1))
                continue

    raise RuntimeError(f"GET failed: {path} last_err={last_err}")


# ========= CATALOG SEARCH =========
def fetch_creator_asset_ids_for_type(creator_type: int, creator_target_id: int, asset_type_id: int) -> List[int]:
    ids: List[int] = []
    cursor = ""

    for _ in range(MAX_PAGES_PER_TYPE):
        params: Dict[str, Any] = {
            "CreatorType": creator_type,
            "CreatorTargetId": creator_target_id,
            "SortType": 6,              # RecentlyCreated
            "Limit": LIMIT,
            "Category": 1,
            "includeNotForSale": "true",
            "AssetTypeIds": asset_type_id,
        }
        if cursor:
            params["Cursor"] = cursor

        j = get_json_with_bases(CATALOG_BASES, "/v2/search/items/details", params=params)
        data = j.get("data") or []
        for it in data:
            asset_id = it.get("id")
            if isinstance(asset_id, int):
                ids.append(asset_id)

        cursor = j.get("nextPageCursor") or ""
        if not cursor:
            break

    return ids


def fetch_creator_asset_ids(creator_type: int, creator_target_id: int) -> List[int]:
    # Query once per asset type to avoid missing categories (animations, etc.)
    seen: Set[int] = set()
    out: List[int] = []

    for at in sorted(ALLOWED_ASSET_TYPE_IDS):
        ids = fetch_creator_asset_ids_for_type(creator_type, creator_target_id, at)
        for asset_id in ids:
            if asset_id not in seen:
                seen.add(asset_id)
                out.append(asset_id)

    return out


# ========= DETAILS + FILTER "ACHETABLE" =========
def fetch_asset_details_if_purchasable(asset_id: int) -> Optional[Dict[str, Any]]:
    j = get_json_with_bases(ECONOMY_BASES, f"/v2/assets/{asset_id}/details")

    is_for_sale = bool(j.get("IsForSale"))
    price = j.get("PriceInRobux")
    atid = j.get("AssetTypeId")
    remaining = j.get("Remaining")  # limited items sometimes

    if not is_for_sale:
        return None

    if not isinstance(price, int) or price <= 0:
        return None

    if isinstance(remaining, int) and remaining <= 0:
        return None

    if not isinstance(atid, int) or atid not in ALLOWED_ASSET_TYPE_IDS:
        return None

    name = j.get("Name") or f"Item {asset_id}"
    created = j.get("Created") or None
    type_name = ASSET_TYPE_NAME.get(atid, str(atid))

    return {
        "assetId": asset_id,
        "name": name,
        "type": type_name,
        "price": price,
        "created": created,
    }


# ========= THUMBNAILS (rbxcdn) =========
def fetch_thumbnails(asset_ids: List[int]) -> Dict[int, str]:
    if not asset_ids:
        return {}

    out: Dict[int, str] = {}
    chunk_size = 100
    for i in range(0, len(asset_ids), chunk_size):
        chunk = asset_ids[i:i + chunk_size]
        params = {
            "assetIds": ",".join(str(x) for x in chunk),
            "size": "420x420",
            "format": "Png",
            "isCircular": "false",
        }
        j = get_json_with_bases(THUMB_BASES, "/v1/assets", params=params)
        data = j.get("data") or []
        for it in data:
            aid = it.get("targetId")
            url = it.get("imageUrl")
            if isinstance(aid, int) and isinstance(url, str) and url.startswith("http"):
                out[aid] = url

    return out


# ========= FAVORITES COUNT =========
def fetch_favorite_count(asset_id: int) -> int:
    path = FAV_PATH.format(assetId=asset_id)
    j = get_json_with_bases(FAV_BASES, path)

    if isinstance(j, int):
        return j
    if isinstance(j, dict):
        for key in ("favoritesCount", "favoriteCount", "count", "FavoritesCount"):
            v = j.get(key)
            if isinstance(v, int):
                return v
        for v in j.values():
            if isinstance(v, int):
                return v
    return 0


# ========= PIPELINE =========
def build_dataset(creator_type: int, creator_target_id: int) -> Dict[str, Any]:
    ids = fetch_creator_asset_ids(creator_type, creator_target_id)

    items: List[Dict[str, Any]] = []
    purch_ids: List[int] = []

    for aid in ids:
        det = fetch_asset_details_if_purchasable(aid)
        if not det:
            continue
        items.append(det)
        purch_ids.append(aid)

    thumbs = fetch_thumbnails(purch_ids)

    for it in items:
        aid = it["assetId"]
        it["thumb"] = thumbs.get(aid, "")
        it["favorites"] = fetch_favorite_count(aid)

    def _ts(x: Dict[str, Any]) -> float:
        c = x.get("created")
        if not isinstance(c, str):
            return 0.0
        try:
            return dt.datetime.fromisoformat(c.replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0

    items.sort(key=_ts, reverse=True)

    return {
        "updated": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "items": items,
    }


def write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main() -> None:
    user = build_dataset(creator_type=1, creator_target_id=USER_ID)
    group = build_dataset(creator_type=2, creator_target_id=GROUP_ID)

    write_json("data_user.json", user)
    write_json("data_group.json", group)

    print(f"Wrote data_user.json ({len(user['items'])} items)")
    print(f"Wrote data_group.json ({len(group['items'])} items)")


if __name__ == "__main__":
    main()
