#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_ugc.py (v14) — TOUS LES ITEMS EN VENTE (User + Group) + THUMBNAILS (rbxcdn) + FAVORIS

✅ Fonctionne sur GitHub Actions (stdlib uniquement: urllib)
✅ Cherche tous les assets "CommunityCreations" du créateur (profil + groupe)
✅ Filtre STRICT: uniquement achetables (IsForSale=true ET PriceInRobux>0)
✅ Ajoute thumb via thumbnails API (rbxcdn) => images affichées sur ton site
✅ Ajoute favorites via catalog favorites count endpoint
✅ Sortie: data_user.json + data_group.json au format:
   { "updated": "...Z", "generatedAt": "...Z", "items": [ {assetId,name,type,price,created,thumb,favorites}, ... ] }
"""

import json
import time
import random
import datetime
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ========= CONFIG =========
USER_ID = 828726934      # <-- METS TON USER ID
GROUP_ID = 16981319     # <-- METS TON GROUP ID

OUT_USER = "data_user.json"
OUT_GROUP = "data_group.json"

# Max pages of catalog search (30 items/page). Increase if needed.
MAX_PAGES = 60
SLEEP_BETWEEN_CALLS = 0.35  # seconds (anti rate-limit)
# ==========================

# Fallback bases (roproxy helps if Roblox blocks direct calls sometimes)
CATALOG_BASES = ["https://catalog.roblox.com", "https://catalog.roproxy.com"]
ECONOMY_BASES = ["https://economy.roblox.com", "https://economy.roproxy.com"]
THUMB_BASES = ["https://thumbnails.roblox.com", "https://thumbnails.roproxy.com"]

CATALOG_SEARCH_PATH = "/v2/search/items/details"
ECON_ASSET_DETAILS_PATH = "/v2/assets/{asset_id}/details"
THUMB_ASSETS_PATH = "/v1/assets"
FAV_COUNT_PATH = "/v1/favorites/assets/{asset_id}/count"

# NOTE: fallback thumb (may not render everywhere) — we still prefer rbxcdn from thumbnails API
THUMB_FALLBACK = "https://www.roblox.com/asset-thumbnail/image?assetId={asset_id}&width=420&height=420&format=png"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (PortfolioUGC v14; GitHub Actions)"
}

# Avatar/UGC + animations + body parts
ALLOWED_ASSET_TYPE_IDS: Set[int] = {
    # Classic clothing
    2, 11, 12,

    # Accessories
    8, 41, 42, 43, 44, 45, 46, 47,
    57, 58, 76, 77,

    # Layered clothing
    64, 65, 66, 67, 68, 69, 70, 71, 72,

    # Body parts / heads
    17, 18, 27, 28, 29, 30, 31, 79,

    # Packages
    32,

    # Animations
    24, 48, 49, 50, 51, 52, 53, 54, 55, 56, 61, 78,
}

ASSET_TYPE_NAME: Dict[int, str] = {
    2: "TShirt",
    11: "Shirt",
    12: "Pants",

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

    64: "TShirtAccessory",
    65: "ShirtAccessory",
    66: "PantsAccessory",
    67: "JacketAccessory",
    68: "SweaterAccessory",
    69: "ShortsAccessory",
    70: "LeftShoeAccessory",
    71: "RightShoeAccessory",
    72: "DressSkirtAccessory",

    17: "Head",
    18: "Face",
    27: "Torso",
    28: "RightArm",
    29: "LeftArm",
    30: "LeftLeg",
    31: "RightLeg",
    79: "DynamicHead",

    32: "Package",

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


def now_iso() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
            return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def write_json_atomic(path: str, payload: Dict[str, Any]) -> None:
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def http_get_json(base: str, path: str, params: Dict[str, Any], timeout: int = 30) -> Dict[str, Any]:
    qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = base + path + ("?" + qs if qs else "")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def http_get_json_with_fallback(bases: List[str], path: str, params: Dict[str, Any], timeout: int = 30, max_retries: int = 4) -> Dict[str, Any]:
    last_err: Optional[Exception] = None
    for base in bases:
        for _ in range(max_retries):
            try:
                return http_get_json(base, path, params, timeout=timeout)
            except (HTTPError, URLError, TimeoutError, ValueError) as e:
                last_err = e
                time.sleep(0.4 + random.random() * 0.6)
    raise last_err or RuntimeError("http_get_json_with_fallback failed")


def fetch_creator_asset_ids(creator_type: int, creator_target_id: int, limit: int = 30, max_pages: int = MAX_PAGES) -> List[int]:
    ids: List[int] = []
    cursor = ""

    for _ in range(max_pages):
        params: Dict[str, Any] = {
            "CreatorType": creator_type,         # 1=user, 2=group
            "CreatorTargetId": creator_target_id,
            "SortType": 6,                       # RecentlyCreated
            "Limit": limit,
            "categoryFilter": "CommunityCreations",
            "includeNotForSale": "true",
        }
        if cursor:
            params["Cursor"] = cursor

        j = http_get_json_with_fallback(CATALOG_BASES, CATALOG_SEARCH_PATH, params, timeout=30, max_retries=5)

        data = j.get("data") or []
        if isinstance(data, list):
            for it in data:
                if not isinstance(it, dict):
                    continue
                aid = it.get("id") or it.get("assetId")
                if isinstance(aid, int):
                    ids.append(aid)

        cursor = j.get("nextPageCursor") or ""
        if not cursor:
            break

        time.sleep(SLEEP_BETWEEN_CALLS + random.random() * 0.25)

    # de-dupe keep order
    seen: Set[int] = set()
    out: List[int] = []
    for x in ids:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def fetch_asset_details_if_for_sale(asset_id: int) -> Optional[Dict[str, Any]]:
    path = ECON_ASSET_DETAILS_PATH.format(asset_id=asset_id)
    j = http_get_json_with_fallback(ECONOMY_BASES, path, {}, timeout=30, max_retries=5)

    # strict: must be purchasable
    if j.get("IsForSale") is not True:
        return None
    price = j.get("PriceInRobux")
    if not isinstance(price, int) or price <= 0:
        return None

    asset_type_id = j.get("AssetTypeId")
    if not isinstance(asset_type_id, int):
        return None
    if asset_type_id not in ALLOWED_ASSET_TYPE_IDS:
        return None

    name = j.get("Name") or f"Item {asset_id}"
    created = j.get("Created") or None

    return {
        "assetId": asset_id,
        "name": name,
        "type": ASSET_TYPE_NAME.get(asset_type_id, f"AssetType {asset_type_id}"),
        "price": price,
        "created": created,
        "thumb": THUMB_FALLBACK.format(asset_id=asset_id),  # replaced by rbxcdn if possible
        "favorites": None,  # filled later
    }


def fetch_thumbnails(asset_ids: List[int], size: str = "420x420", fmt: str = "Png") -> Dict[int, str]:
    out: Dict[int, str] = {}
    if not asset_ids:
        return out

    batch_size = 100
    for i in range(0, len(asset_ids), batch_size):
        batch = asset_ids[i:i + batch_size]
        params = {
            "assetIds": ",".join(str(x) for x in batch),
            "size": size,
            "format": fmt,
            "isCircular": "false",
        }
        j = http_get_json_with_fallback(THUMB_BASES, THUMB_ASSETS_PATH, params, timeout=30, max_retries=6)
        for it in (j.get("data") or []):
            if not isinstance(it, dict):
                continue
            tid = it.get("targetId")
            url = it.get("imageUrl")
            if isinstance(tid, int) and isinstance(url, str) and url.startswith("http"):
                out[tid] = url

        time.sleep(0.25 + random.random() * 0.25)

    return out


def fetch_favorite_count(asset_id: int) -> Optional[int]:
    # Docs: GET https://catalog.roblox.com/v1/favorites/assets/{assetId}/count
    path = FAV_COUNT_PATH.format(asset_id=asset_id)
    j = http_get_json_with_fallback(CATALOG_BASES, path, {}, timeout=30, max_retries=4)

    # Can be number or {count: n} depending on proxy
    if isinstance(j, int):
        return j
    if isinstance(j, dict):
        for k in ("count", "favoriteCount", "favoritesCount", "favorites"):
            v = j.get(k)
            if isinstance(v, int):
                return v
    return None


def update_file(out_path: str, creator_type: int, creator_target_id: int) -> None:
    prev = read_json(out_path)
    prev_items = prev.get("items") if isinstance(prev, dict) else None
    prev_map = {it.get("assetId"): it for it in prev_items} if isinstance(prev_items, list) else {}

    asset_ids = fetch_creator_asset_ids(creator_type, creator_target_id)
    if not asset_ids and prev_items:
        # avoid nuking if Roblox API rate-limited
        print(f"[warn] {out_path}: empty asset list -> keep previous")
        return

    items: List[Dict[str, Any]] = []
    for idx, aid in enumerate(asset_ids):
        cached = prev_map.get(aid)

        # Use cache sometimes (fast), but refresh regularly
        if isinstance(cached, dict) and isinstance(cached.get("price"), int) and isinstance(cached.get("name"), str):
            if idx % 6 != 0:
                items.append(cached)
                continue

        det = fetch_asset_details_if_for_sale(aid)
        if det is not None:
            items.append(det)

        time.sleep(SLEEP_BETWEEN_CALLS + random.random() * 0.35)

    if not items and prev_items:
        print(f"[warn] {out_path}: 0 items after filter -> keep previous")
        return

    # Thumbs (rbxcdn)
    thumb_map = fetch_thumbnails([it["assetId"] for it in items])
    for it in items:
        aid = it["assetId"]
        it["thumb"] = thumb_map.get(aid, it.get("thumb") or THUMB_FALLBACK.format(asset_id=aid))

    # Favorites (best effort)
    for i, it in enumerate(items):
        aid = int(it["assetId"])
        # cache favorites if present, refresh 1/5
        if isinstance(it.get("favorites"), int) and (i % 5 != 0):
            continue
        try:
            it["favorites"] = fetch_favorite_count(aid)
        except Exception:
            it["favorites"] = it.get("favorites")
        time.sleep(0.18 + random.random() * 0.22)

    # sort newest-ish by created, fallback by assetId
    def sort_key(it: Dict[str, Any]) -> Tuple[int, int]:
        ts = -1
        c = it.get("created")
        if isinstance(c, str) and c:
            try:
                ts = int(datetime.datetime.fromisoformat(c.replace("Z", "+00:00")).timestamp())
            except Exception:
                ts = -1
        return (ts, int(it.get("assetId", 0)))

    items.sort(key=sort_key, reverse=True)

    stamp = now_iso()
    payload = {
        "updated": stamp,
        "generatedAt": stamp,
        "items": items
    }
    write_json_atomic(out_path, payload)
    print(f"Wrote {out_path} ({len(items)} items)")


def main() -> None:
    # random warmup (avoid burst rate-limit on every run)
    time.sleep(2.0 + random.random() * 4.0)
    update_file(OUT_USER, 1, USER_ID)
    time.sleep(2.0 + random.random() * 4.0)
    update_file(OUT_GROUP, 2, GROUP_ID)


if __name__ == "__main__":
    main()
