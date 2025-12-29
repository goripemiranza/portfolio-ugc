#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fetch Roblox creator items (profil + groupe), keep ONLY purchasable items (onsale + price > 0),
and write JSON files used by the portfolio.

Outputs:
- data_user.json
- data_group.json
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
import urllib.request


# ===== CONFIG =====
USER_ID = 4473141104          # lulu8203
GROUP_ID = 32801371           # Powerful Artists

OUT_USER = "data_user.json"
OUT_GROUP = "data_group.json"

# Roblox endpoints (with roproxy fallback)
CATALOG_BASES = [
    "https://catalog.roblox.com",
    "https://catalog.roproxy.com",
]
ECONOMY_BASES = [
    "https://economy.roblox.com",
    "https://economy.roproxy.com",
]
THUMB_BASES = [
    "https://thumbnails.roblox.com",
    "https://thumbnails.roproxy.com",
]

# Important: keep thumbnails big enough for zoom
THUMB_SIZE = "768x768"
THUMB_FORMAT = "Png"
THUMB_IS_CIRCULAR = "false"

# ===== SALE FILTER (strict) =====
# Must be purchasable on the Roblox website (not experience-only):
# SaleLocationType examples (devforum): 1=MarketplaceOnly, 5=Marketplace+AllExperiences, 7=Marketplace+ExperiencesById
ALLOWED_SALE_LOCATION_TYPES = {1, 5, 7}

# Only avatar shop + animations types.
# (Includes classic + layered clothing, accessories, body parts, avatar animations, dynamic head, eyebrow/eyelash)
ALLOWED_ASSET_TYPE_IDS = {
    # Accessories
    8, 41, 42, 43, 44, 45, 46, 47, 57, 58, 76, 77,
    # Clothing (classic)
    2, 11, 12,
    # Layered clothing
    64, 65, 66, 67, 68, 69, 70, 71, 72,
    # Body
    17, 18, 27, 28, 29, 30, 31, 79,
    # Animations
    24, 48, 49, 50, 51, 52, 53, 54, 55, 56, 61, 78,
}

ASSET_TYPE_NAME: Dict[int, str] = {
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

    # Clothing (classic)
    2: "TShirt",
    11: "Shirt",
    12: "Pants",

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

    # Body
    17: "Head",
    18: "Face",
    27: "Torso",
    28: "RightArm",
    29: "LeftArm",
    30: "LeftLeg",
    31: "RightLeg",
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

ASSET_TYPE_FR: Dict[int, str] = {
    # Accessories
    8: "Chapeau",
    41: "Cheveux",
    42: "Visage",
    43: "Cou",
    44: "Épaule",
    45: "Avant",
    46: "Dos",
    47: "Taille",
    57: "Oreilles",
    58: "Yeux",
    76: "Sourcils",
    77: "Cils",
    # Clothing
    2: "T‑Shirt (classique)",
    11: "Haut (classique)",
    12: "Pantalon (classique)",
    64: "T‑Shirt (layered)",
    65: "Haut (layered)",
    66: "Pantalon (layered)",
    67: "Veste",
    68: "Pull",
    69: "Short",
    70: "Chaussure (G)",
    71: "Chaussure (D)",
    72: "Robe / Jupe",
    # Body
    17: "Tête",
    18: "Face",
    27: "Torse",
    28: "Bras (D)",
    29: "Bras (G)",
    30: "Jambe (G)",
    31: "Jambe (D)",
    79: "Tête dynamique",
    # Animations
    24: "Animation",
    48: "Anim • Climb",
    49: "Anim • Death",
    50: "Anim • Fall",
    51: "Anim • Idle",
    52: "Anim • Jump",
    53: "Anim • Run",
    54: "Anim • Swim",
    55: "Anim • Walk",
    56: "Anim • Pose",
    61: "Anim • Emote",
    78: "Anim • Mood",
}

CATEGORY_BY_TYPE: Dict[int, str] = {}
for _i in (8, 41, 42, 43, 44, 45, 46, 47, 57, 58, 76, 77):
    CATEGORY_BY_TYPE[_i] = "ACCESSORIES"
for _i in (2, 11, 12, 64, 65, 66, 67, 68, 69, 70, 71, 72):
    CATEGORY_BY_TYPE[_i] = "CLOTHING"
for _i in (17, 18, 27, 28, 29, 30, 31, 79):
    CATEGORY_BY_TYPE[_i] = "BODY"
for _i in (24, 48, 49, 50, 51, 52, 53, 54, 55, 56, 61, 78):
    CATEGORY_BY_TYPE[_i] = "ANIMATIONS"


# ===== HTTP HELPERS =====
def _http_get(base: str, path: str, params: Optional[Dict[str, Any]] = None, timeout: int = 12) -> Tuple[int, str]:
    url = base + path
    if params:
        qs = urlencode({k: v for k, v in params.items() if v is not None})
        url = url + ("?" if "?" not in url else "&") + qs

    req = urllib.request.Request(url, headers={
        "User-Agent": "portfolio-ugc/1.0 (+https://github.com/)",
        "Accept": "application/json,text/plain,*/*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        code = resp.getcode()
        body = resp.read().decode("utf-8", errors="replace")
        return code, body


def get_json_with_fallback(bases: List[str], path: str, params: Optional[Dict[str, Any]] = None, retries: int = 2) -> Any:
    last_err: Optional[Exception] = None
    for base in bases:
        for attempt in range(retries + 1):
            try:
                code, body = _http_get(base, path, params=params)
                if code >= 400:
                    raise RuntimeError(f"HTTP {code}")
                return json.loads(body)
            except Exception as e:
                last_err = e
                time.sleep(0.25 + 0.25 * attempt)
                continue
    raise RuntimeError(f"Request failed for {path}: {last_err}")


def get_text_with_fallback(bases: List[str], path: str, params: Optional[Dict[str, Any]] = None, retries: int = 2) -> str:
    last_err: Optional[Exception] = None
    for base in bases:
        for attempt in range(retries + 1):
            try:
                code, body = _http_get(base, path, params=params)
                if code >= 400:
                    raise RuntimeError(f"HTTP {code}")
                return body.strip()
            except Exception as e:
                last_err = e
                time.sleep(0.25 + 0.25 * attempt)
                continue
    raise RuntimeError(f"Request failed for {path}: {last_err}")


# ===== ROBLOX FETCH =====
def fetch_creator_catalog_assets(creator_type: int, creator_target_id: int, limit: int = 120, max_pages: int = 60) -> List[Dict[str, Any]]:
    """
    Uses Catalog V2 search to list items created by a user/group.
    We keep the raw fields we need (id, favoriteCount, etc.).
    """
    cursor = ""
    out: List[Dict[str, Any]] = []

    for _ in range(max_pages):
        params = {
            "CreatorType": creator_type,
            "CreatorTargetId": creator_target_id,
            "Limit": limit,
            "Cursor": cursor or None,
            "includeNotForSale": "true",
            "salesTypeFilter": 1,  # "All" in Roblox website params
        }

        data = get_json_with_fallback(CATALOG_BASES, "/v2/search/items/details", params=params)

        items = data.get("data", []) if isinstance(data, dict) else []
        for it in items:
            if it.get("itemType") != "Asset":
                continue
            out.append(it)

        cursor = data.get("nextPageCursor") if isinstance(data, dict) else None
        if not cursor:
            break

        time.sleep(0.15)

    # Dedupe by id (keep max favoriteCount)
    by_id: Dict[int, Dict[str, Any]] = {}
    for it in out:
        try:
            aid = int(it.get("id"))
        except Exception:
            continue
        prev = by_id.get(aid)
        if not prev:
            by_id[aid] = it
        else:
            try:
                by_id[aid]["favoriteCount"] = max(int(prev.get("favoriteCount", 0)), int(it.get("favoriteCount", 0)))
            except Exception:
                pass
    return list(by_id.values())


def fetch_economy_details(asset_id: int) -> Optional[Dict[str, Any]]:
    try:
        return get_json_with_fallback(ECONOMY_BASES, f"/v2/assets/{asset_id}/details")
    except Exception:
        return None


def is_purchasable(details: Dict[str, Any]) -> bool:
    if details.get("IsForSale") is not True:
        return False

    price = details.get("PriceInRobux")
    if not isinstance(price, int) or price <= 0:
        return False

    sale_loc = details.get("SaleLocationType")
    if isinstance(sale_loc, int) and sale_loc not in ALLOWED_SALE_LOCATION_TYPES:
        return False

    return True


def fetch_favorite_count(asset_id: int) -> Optional[int]:
    """
    Catalog favorite count endpoint:
    /v1/favorites/assets/{assetId}/count

    Response can be:
    - JSON number
    - JSON object (rare)
    - plain number (text)
    """
    try:
        raw = get_text_with_fallback(CATALOG_BASES, f"/v1/favorites/assets/{asset_id}/count")
    except Exception:
        return None

    try:
        val = json.loads(raw)
    except Exception:
        try:
            return int(raw)
        except Exception:
            return None

    if isinstance(val, int):
        return val
    if isinstance(val, dict):
        for k in ("favoritesCount", "favoriteCount", "count", "data"):
            v = val.get(k)
            if isinstance(v, int):
                return v
    return None


def fetch_thumbnails(asset_ids: List[int]) -> Dict[int, str]:
    out: Dict[int, str] = {}
    if not asset_ids:
        return out

    chunk = 100
    for i in range(0, len(asset_ids), chunk):
        part = asset_ids[i:i+chunk]
        params = {
            "assetIds": ",".join(str(x) for x in part),
            "size": THUMB_SIZE,
            "format": THUMB_FORMAT,
            "isCircular": THUMB_IS_CIRCULAR,
        }
        data = get_json_with_fallback(THUMB_BASES, "/v1/assets", params=params)
        for row in data.get("data", []) if isinstance(data, dict) else []:
            try:
                aid = int(row.get("targetId"))
                url = row.get("imageUrl")
                if isinstance(url, str) and url:
                    out[aid] = url
            except Exception:
                continue
        time.sleep(0.12)

    return out


def build_items(creator_type: int, creator_target_id: int) -> List[Dict[str, Any]]:
    catalog_items = fetch_creator_catalog_assets(creator_type, creator_target_id)

    fav_from_catalog: Dict[int, int] = {}
    for it in catalog_items:
        try:
            aid = int(it.get("id"))
            fav = int(it.get("favoriteCount", 0))
            if fav >= 0:
                fav_from_catalog[aid] = fav
        except Exception:
            continue

    results: List[Dict[str, Any]] = []
    asset_ids: List[int] = []

    for it in catalog_items:
        try:
            asset_id = int(it.get("id"))
        except Exception:
            continue

        details = fetch_economy_details(asset_id)
        if not details:
            continue

        atid = details.get("AssetTypeId")
        if not isinstance(atid, int) or atid not in ALLOWED_ASSET_TYPE_IDS:
            continue

        if not is_purchasable(details):
            continue

        fav = fetch_favorite_count(asset_id)
        if fav is None:
            fav = fav_from_catalog.get(asset_id, 0)

        name = details.get("Name") if isinstance(details.get("Name"), str) else (it.get("name") or f"Item {asset_id}")
        created = details.get("Created") if isinstance(details.get("Created"), str) else ""
        price = details.get("PriceInRobux") if isinstance(details.get("PriceInRobux"), int) else None

        row = {
            "assetId": asset_id,
            "name": name,
            "assetTypeId": atid,
            "assetTypeName": ASSET_TYPE_NAME.get(atid, f"Type{atid}"),
            "typeFr": ASSET_TYPE_FR.get(atid, "Autre"),
            "category": CATEGORY_BY_TYPE.get(atid, "ALL"),
            "price": price,
            "favorites": int(fav) if isinstance(fav, int) and fav >= 0 else 0,
            "created": created,
            "thumb": "",
        }

        results.append(row)
        asset_ids.append(asset_id)

        time.sleep(0.06)

    thumbs = fetch_thumbnails(asset_ids)
    for r in results:
        r["thumb"] = thumbs.get(r["assetId"], "")

    def _ts(s: str) -> float:
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.timestamp()
        except Exception:
            return 0.0

    results.sort(key=lambda x: (_ts(x.get("created", "")), x.get("assetId", 0)), reverse=True)
    return results


def write_json(path: str, payload: Dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    user_items = build_items(creator_type=1, creator_target_id=USER_ID)
    group_items = build_items(creator_type=2, creator_target_id=GROUP_ID)

    write_json(OUT_USER, {"generatedAt": now, "items": user_items})
    write_json(OUT_GROUP, {"generatedAt": now, "items": group_items})

    print(f"OK: {OUT_USER} ({len(user_items)} items), {OUT_GROUP} ({len(group_items)} items)")


if __name__ == "__main__":
    main()
