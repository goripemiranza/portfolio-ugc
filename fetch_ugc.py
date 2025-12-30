#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_ugc.py (v13) — Portfolio Roblox

Objectif:
- Récupérer TOUTES les créations (Profil + Groupe) via Catalog v2 (categoryFilter=CommunityCreations)
- Garder UNIQUEMENT ce qui est achetable (IsForSale=true + PriceInRobux>0)
- Exclure les limited sold-out (uniquement si IsLimited/IsLimitedUnique=true ET Remaining<=0)
- Ajouter thumbnails (rbxcdn) + nombre de favoris (catalog /v1/favorites/assets/{assetId}/count)

Sortie:
- data_user.json
- data_group.json

Format item:
{
  "assetId": 123,
  "name": "...",
  "type": "Hat" | "FaceAccessory" | "EmoteAnimation" | ...,
  "price": 100,
  "created": "2025-12-27T23:11:28.7307839Z",
  "thumb": "https://tr.rbxcdn.com/....png",
  "favorites": 12345
}
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
import urllib.request
from urllib.error import HTTPError, URLError


# ===== CONFIG (à modifier si besoin) =====
USER_ID = 4473141104          # lulu8203
GROUP_ID = 32801371           # Powerful Artists

OUT_USER = "data_user.json"
OUT_GROUP = "data_group.json"

REQUEST_TIMEOUT = 20
SLEEP_BETWEEN_CALLS = 0.12
RETRIES_PER_BASE = 3

# Catalog search (Avatar Shop)
CATALOG_BASES = ["https://catalog.roblox.com", "https://catalog.roproxy.com"]
CATALOG_V2_SEARCH_PATH = "/v2/search/items/details"

# Asset details (price/onsale/type/created)
ECONOMY_BASES = ["https://economy.roblox.com", "https://economy.roproxy.com"]
ECON_ASSET_DETAILS_PATH = "/v2/assets/{asset_id}/details"

# Thumbnails
THUMB_BASES = ["https://thumbnails.roblox.com", "https://thumbnails.roproxy.com"]
THUMB_ASSETS_PATH = "/v1/assets"

# Favorites count (Open Cloud catalog)
FAV_BASES = ["https://catalog.roblox.com", "https://catalog.roproxy.com"]
FAV_COUNT_PATH = "/v1/favorites/assets/{asset_id}/count"

# Pagination + limits
LIMIT = 30
MAX_PAGES = 50  # safety

# Types autorisés (Avatar Shop) — uniquement filtres existants Roblox
ALLOWED_ASSET_TYPE_IDS = {
    # Accessoires (classiques)
    8,   # Hat
    41,  # HairAccessory
    42,  # FaceAccessory
    43,  # NeckAccessory
    44,  # ShoulderAccessory
    45,  # FrontAccessory
    46,  # BackAccessory
    47,  # WaistAccessory

    # Accessoires (nouveaux)
    57,  # EarAccessory
    58,  # EyeAccessory
    76,  # EyebrowAccessory
    77,  # EyelashAccessory

    # Têtes / animations spéciales
    78,  # MoodAnimation
    79,  # DynamicHead

    # Makeup
    88,  # FaceMakeup
    89,  # LipMakeup
    90,  # EyeMakeup

    # Layered clothing
    64, 65, 66, 67, 68, 69, 70, 71, 72,

    # Vêtements classiques (au cas où)
    2,   # TShirt
    11,  # Shirt
    12,  # Pants

    # Animations
    24,  # Animation
    48, 49, 50, 51, 52, 53, 54, 55, 56,  # Climb/Death/Fall/Idle/Jump/Run/Swim/Walk/Pose
    61,  # EmoteAnimation
}

ASSET_TYPE_NAME = {
    2: "TShirt",
    8: "Hat",
    11: "Shirt",
    12: "Pants",
    24: "Animation",
    41: "HairAccessory",
    42: "FaceAccessory",
    43: "NeckAccessory",
    44: "ShoulderAccessory",
    45: "FrontAccessory",
    46: "BackAccessory",
    47: "WaistAccessory",
    48: "ClimbAnimation",
    49: "DeathAnimation",
    50: "FallAnimation",
    51: "IdleAnimation",
    52: "JumpAnimation",
    53: "RunAnimation",
    54: "SwimAnimation",
    55: "WalkAnimation",
    56: "PoseAnimation",
    57: "EarAccessory",
    58: "EyeAccessory",
    61: "EmoteAnimation",
    64: "TShirtAccessory",
    65: "ShirtAccessory",
    66: "PantsAccessory",
    67: "JacketAccessory",
    68: "SweaterAccessory",
    69: "ShortsAccessory",
    70: "LeftShoeAccessory",
    71: "RightShoeAccessory",
    72: "DressSkirtAccessory",
    76: "EyebrowAccessory",
    77: "EyelashAccessory",
    78: "MoodAnimation",
    79: "DynamicHead",
    88: "FaceMakeup",
    89: "LipMakeup",
    90: "EyeMakeup",
}

HEADERS = {
    "User-Agent": "portfolio-ugc-bot/1.0",
    "Accept": "application/json,text/plain,*/*",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _http_get_json(url: str, timeout: int) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers=HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def get_json_with_bases(bases: List[str], path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params = params or {}
    last_err: Optional[Exception] = None

    qs = urlencode(params, doseq=True)
    suffix = f"{path}?{qs}" if qs else path

    for base in bases:
        url = base + suffix
        for attempt in range(RETRIES_PER_BASE):
            try:
                return _http_get_json(url, timeout=REQUEST_TIMEOUT)
            except HTTPError as e:
                last_err = e
                code = getattr(e, "code", None)
                if code in (429, 500, 502, 503, 504):
                    time.sleep(0.4 + attempt * 0.6)
                    continue
                break
            except (URLError, TimeoutError, ValueError) as e:
                last_err = e
                time.sleep(0.25 + attempt * 0.35)
                continue

    raise RuntimeError(f"HTTP failed for {path} — last error: {last_err}")


# ===== Catalog search (creator -> asset IDs) =====
def _catalog_page(cursor: str, creator_type: int, creator_target_id: int, category_filter: Optional[str] = "CommunityCreations") -> Dict[str, Any]:
    """
    V2 search accepte plusieurs casings selon les changements.
    On tente d'abord en lowercase, sinon PascalCase.
    """
    base_params_lc: Dict[str, Any] = {
        "creatorType": creator_type,
        "creatorTargetId": creator_target_id,
        "sortType": 6,       # RecentlyCreated
        "limit": LIMIT,
    }
    if category_filter:
        base_params_lc["categoryFilter"] = category_filter
    if cursor:
        base_params_lc["cursor"] = cursor

    try:
        j = get_json_with_bases(CATALOG_BASES, CATALOG_V2_SEARCH_PATH, params=base_params_lc)
        if isinstance(j, dict) and ("data" in j or "nextPageCursor" in j):
            return j
    except Exception:
        pass

    base_params_pc: Dict[str, Any] = {
        "CreatorType": creator_type,
        "CreatorTargetId": creator_target_id,
        "SortType": 6,
        "Limit": LIMIT,
    }
    if category_filter:
        base_params_pc["categoryFilter"] = category_filter
    if cursor:
        base_params_pc["Cursor"] = cursor

    return get_json_with_bases(CATALOG_BASES, CATALOG_V2_SEARCH_PATH, params=base_params_pc)


def fetch_creator_asset_ids(creator_type: int, creator_target_id: int) -> List[int]:
    def run(category_filter: Optional[str]) -> List[int]:
        ids: List[int] = []
        seen = set()
        cursor = ""

        for _ in range(MAX_PAGES):
            j = _catalog_page(cursor, creator_type, creator_target_id, category_filter=category_filter)

            for it in (j.get("data") or []):
                # itemType = "Asset" / "Bundle"
                if (it.get("itemType") or "Asset") != "Asset":
                    continue
                asset_id = it.get("id")
                if isinstance(asset_id, int) and asset_id not in seen:
                    seen.add(asset_id)
                    ids.append(asset_id)

            cursor = j.get("nextPageCursor") or ""
            if not cursor:
                break

            time.sleep(SLEEP_BETWEEN_CALLS)

        return ids

    # 1) CommunityCreations (UGC / Avatar Shop)
    ids = run("CommunityCreations")

    # 2) fallback (si Roblox change le filtre)
    if not ids:
        ids = run(None)

    return ids



# ===== Details + filter "achetable" =====
def fetch_asset_details_if_purchasable(asset_id: int) -> Optional[Dict[str, Any]]:
    j = get_json_with_bases(ECONOMY_BASES, ECON_ASSET_DETAILS_PATH.format(asset_id=asset_id))

    is_for_sale = j.get("IsForSale") is True
    price = j.get("PriceInRobux")
    asset_type_id = j.get("AssetTypeId")
    name = j.get("Name") or f"Item {asset_id}"
    created = j.get("Created") or None

    # Limited sold-out (seulement si limited)
    is_limited = (j.get("IsLimited") is True) or (j.get("IsLimitedUnique") is True)
    remaining = j.get("Remaining")
    if is_limited and isinstance(remaining, int) and remaining <= 0:
        return None

    if not is_for_sale:
        return None
    if not isinstance(price, int) or price <= 0:
        return None

    if not isinstance(asset_type_id, int) or asset_type_id not in ALLOWED_ASSET_TYPE_IDS:
        return None

    return {
        "assetId": asset_id,
        "name": name,
        "type": ASSET_TYPE_NAME.get(asset_type_id, f"AssetType {asset_type_id}"),
        "price": price,
        "created": created,
        "thumb": None,       # filled later
        "favorites": None,   # filled later
    }


def fetch_thumbnails(asset_ids: List[int], size: str = "420x420", fmt: str = "Png") -> Dict[int, str]:
    if not asset_ids:
        return {}
    params = {
        "assetIds": ",".join(str(x) for x in asset_ids),
        "returnPolicy": "PlaceHolder",
        "size": size,
        "format": fmt,
        "isCircular": "false",
    }
    j = get_json_with_bases(THUMB_BASES, THUMB_ASSETS_PATH, params=params)
    out: Dict[int, str] = {}
    for row in (j.get("data") or []):
        aid = row.get("targetId")
        url = row.get("imageUrl")
        if isinstance(aid, int) and isinstance(url, str) and url:
            out[aid] = url
    return out


def fetch_favorites_count(asset_id: int) -> Optional[int]:
    """
    Endpoint officiel (Open Cloud catalog):
    GET /v1/favorites/assets/{assetId}/count
    """
    j = get_json_with_bases(FAV_BASES, FAV_COUNT_PATH.format(asset_id=asset_id))
    # selon l'API: {"favoritesCount": 123} ou {"count": 123}
    if isinstance(j, dict):
        v = j.get("favoritesCount")
        if isinstance(v, int):
            return v
        v2 = j.get("count")
        if isinstance(v2, int):
            return v2
    if isinstance(j, int):
        return j
    return None


def update_file(creator_type: int, creator_target_id: int, out_path: str) -> None:
    # Step 1: list ids
    ids = fetch_creator_asset_ids(creator_type, creator_target_id)

    # Step 2: details + filter
    items: List[Dict[str, Any]] = []
    for aid in ids:
        try:
            d = fetch_asset_details_if_purchasable(aid)
        except Exception:
            d = None
        if d:
            items.append(d)
        time.sleep(SLEEP_BETWEEN_CALLS)

    # Step 3: thumbnails batch
    thumbs = fetch_thumbnails([it["assetId"] for it in items])
    for it in items:
        it["thumb"] = thumbs.get(it["assetId"])

    # Step 4: favorites per item
    for it in items:
        try:
            it["favorites"] = fetch_favorites_count(it["assetId"])
        except Exception:
            it["favorites"] = None
        time.sleep(SLEEP_BETWEEN_CALLS)

    # Step 5: sort
    items.sort(key=lambda x: (x.get("created") or ""), reverse=True)

    payload = {
        "updated": now_iso(),
        "items": items,
    }

    write_json_atomic(out_path, payload)
    print(f"Wrote {out_path} ({len(items)} items)")


def main() -> None:
    update_file(1, USER_ID, OUT_USER)   # User
    update_file(2, GROUP_ID, OUT_GROUP) # Group


if __name__ == "__main__":
    main()
