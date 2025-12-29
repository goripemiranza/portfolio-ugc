#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
fetch_ugc.py (v12) — CREATIONS PROFIL + GROUPE (UGC + ANIMATIONS + AUTRES)

Objectif:
- Récupérer TOUTES les créations publiées du profil + du groupe (pas seulement "en vente").
- Garder une image (rbxcdn) via l'API thumbnails pour affichage sur un site statique.
- Sortie: data_user.json + data_group.json

Schéma item:
{
  "assetId": 123,
  "name": "...",
  "assetTypeId": 24,
  "assetTypeName": "Animation",
  "isForSale": false,
  "price": null,
  "created": "2025-01-01T00:00:00Z",
  "thumb": "https://tr.rbxcdn.com/...."
}
'''

import json
import time
import random
import datetime
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

USER_ID = 828726934
GROUP_ID = 16981319

CATALOG_BASES = ["https://catalog.roblox.com", "https://catalog.roproxy.com"]
ECONOMY_BASES = ["https://economy.roblox.com", "https://economy.roproxy.com"]
THUMB_BASES   = ["https://thumbnails.roblox.com", "https://thumbnails.roproxy.com"]

CATALOG_SEARCH_PATH = "/v2/search/items/details"
ECON_ASSET_DETAILS_PATH = "/v2/assets/{asset_id}/details"
THUMB_ASSETS_PATH = "/v1/assets"

# Fallback (au cas où thumbnails API ne renvoie rien)
THUMB_FALLBACK = "https://www.roblox.com/asset-thumbnail/image?assetId={asset_id}&width=420&height=420&format=png"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "PortfolioUGCFetch/12.0 (+https://roblox.com)",
}

# Map partiel: on garde les plus utiles; le reste -> "AssetType <id>"
ASSET_TYPE_NAME: Dict[int, str] = {
    1: "Image",
    2: "TShirt",
    3: "Audio",
    4: "Mesh",
    5: "Lua",
    6: "HTML",
    7: "Text",
    8: "Hat",
    9: "Place",
    10: "Model",
    11: "Shirt",
    12: "Pants",
    13: "Decal",
    17: "Gear",
    18: "Badge",
    19: "GroupEmblem",
    24: "Animation",
    # Accessories / Layered Clothing (UGC)
    41: "HairAccessory",
    42: "FaceAccessory",
    43: "NeckAccessory",
    44: "ShoulderAccessory",
    45: "FrontAccessory",
    46: "BackAccessory",
    47: "WaistAccessory",
    64: "TShirtAccessory",
    65: "ShirtAccessory",
    66: "PantsAccessory",
    67: "JacketAccessory",
    68: "SweaterAccessory",
    69: "ShortsAccessory",
    70: "LeftShoeAccessory",
    71: "RightShoeAccessory",
    72: "DressSkirtAccessory",
}

def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

def read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
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
    params: Dict[str, Any],
    timeout: int = 30,
    max_retries: int = 6
) -> Dict[str, Any]:
    last_err: Optional[Exception] = None
    query = urllib.parse.urlencode(params) if params else ""

    for attempt in range(max_retries):
        random.shuffle(bases)
        for base in bases:
            url = f"{base}{path}" + (f"?{query}" if query else "")
            try:
                req = urllib.request.Request(url, headers=HEADERS, method="GET")
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    raw = r.read().decode("utf-8", errors="replace")
                return json.loads(raw)

            except HTTPError as e:
                last_err = e
                code = getattr(e, "code", None)

                if code == 429 or code in (500, 502, 503, 504):
                    retry_after = None
                    try:
                        retry_after = e.headers.get("Retry-After")
                    except Exception:
                        retry_after = None

                    if retry_after and str(retry_after).strip().isdigit():
                        sleep_s = float(int(retry_after))
                    else:
                        sleep_s = 5.0 + random.random() * 4.0
                    sleep_s = min(90.0, sleep_s + attempt * 9.0)

                    print(f"[http] {code} -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries}) {base}")
                    time.sleep(sleep_s)
                    continue

                raise

            except URLError as e:
                last_err = e
                sleep_s = 3.0 + random.random() * 3.0
                print(f"[http] URLError -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries}) {base}")
                time.sleep(sleep_s)
                continue

            except Exception as e:
                last_err = e
                sleep_s = 3.0 + random.random() * 3.0
                print(f"[http] Error -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries}) {base}")
                time.sleep(sleep_s)
                continue

    raise RuntimeError(f"GET failed after retries. last_err={last_err}")

def fetch_creator_asset_ids(creator_type: int, creator_target_id: int, limit: int = 30, max_pages: int = 25) -> List[int]:
    '''
    CreatorType: 1=user, 2=group
    On prend "RecentlyCreated" et includeNotForSale=true pour récupérer le maximum.
    '''
    ids: List[int] = []
    cursor = ""

    for _ in range(max_pages):
        params: Dict[str, Any] = {
            "CreatorType": creator_type,
            "CreatorTargetId": creator_target_id,
            "SortType": 6,                 # RecentlyCreated
            "Limit": limit,
            "Category": 1,
            "includeNotForSale": "true",
        }
        if cursor:
            params["Cursor"] = cursor

        j = http_get_json_with_fallback(CATALOG_BASES, CATALOG_SEARCH_PATH, params)
        data = j.get("data") or []
        for it in data:
            if not isinstance(it, dict):
                continue
            if it.get("itemType") != "Asset":
                continue
            asset_id = it.get("id")
            if isinstance(asset_id, int):
                ids.append(asset_id)

        cursor = j.get("nextPageCursor") or ""
        if not cursor:
            break

        time.sleep(0.8 + random.random() * 0.5)

    # Deduplicate while preserving order
    seen: Set[int] = set()
    out: List[int] = []
    for x in ids:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out

def asset_type_name(asset_type_id: Optional[int]) -> str:
    if isinstance(asset_type_id, int) and asset_type_id in ASSET_TYPE_NAME:
        return ASSET_TYPE_NAME[asset_type_id]
    return f"AssetType {asset_type_id}" if asset_type_id is not None else "Asset"

def fetch_asset_details(asset_id: int) -> Optional[Dict[str, Any]]:
    '''
    Economy details: donne IsForSale, PriceInRobux, Name, Created, AssetTypeId, ...
    On garde même si offsale.
    '''
    path = ECON_ASSET_DETAILS_PATH.format(asset_id=asset_id)
    j = http_get_json_with_fallback(ECONOMY_BASES, path, {}, timeout=30, max_retries=6)

    name = j.get("Name") or f"Asset {asset_id}"
    created = j.get("Created") or None

    asset_type_id = j.get("AssetTypeId")
    if not isinstance(asset_type_id, int):
        asset_type_id = None

    is_for_sale = (j.get("IsForSale") is True)
    price = j.get("PriceInRobux")
    if not isinstance(price, int):
        price = None

    return {
        "assetId": asset_id,
        "name": name,
        "assetTypeId": asset_type_id,
        "assetTypeName": asset_type_name(asset_type_id),
        "isForSale": is_for_sale,
        "price": price,
        "created": created,
        "thumb": THUMB_FALLBACK.format(asset_id=asset_id),  # remplacé par rbxcdn si possible
    }

def fetch_thumbnails(asset_ids: List[int], size: str = "420x420", fmt: str = "Png") -> Dict[int, str]:
    out: Dict[int, str] = {}
    if not asset_ids:
        return out

    batch_size = 100
    for i in range(0, len(asset_ids), batch_size):
        batch = asset_ids[i:i+batch_size]
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
            state = it.get("state")
            if isinstance(tid, int) and isinstance(url, str) and url and state == "Completed":
                out[tid] = url
        time.sleep(0.5 + random.random() * 0.4)

    return out

def update_file(out_path: str, creator_type: int, creator_target_id: int) -> None:
    prev = read_json(out_path)
    prev_items = prev.get("items") if isinstance(prev, dict) else None
    prev_map: Dict[int, Dict[str, Any]] = {}
    if isinstance(prev_items, list):
        for it in prev_items:
            if isinstance(it, dict) and isinstance(it.get("assetId"), int):
                prev_map[int(it["assetId"])] = it

    try:
        asset_ids = fetch_creator_asset_ids(creator_type, creator_target_id)
        if not asset_ids and prev_items:
            print(f"[warn] {out_path}: empty asset list -> keep previous")
            return

        items: List[Dict[str, Any]] = []
        for idx, aid in enumerate(asset_ids):
            cached = prev_map.get(aid)

            # Cache: on réutilise 7/8 pour réduire les appels API
            if isinstance(cached, dict) and isinstance(cached.get("name"), str) and idx % 8 != 0:
                items.append(cached)
                continue

            det = fetch_asset_details(aid)
            if det is not None:
                items.append(det)

            time.sleep(0.55 + random.random() * 0.45)

        if not items and prev_items:
            print(f"[warn] {out_path}: 0 items -> keep previous")
            return

        # Thumbnails rbxcdn
        thumb_map = fetch_thumbnails([it["assetId"] for it in items])
        for it in items:
            aid = it["assetId"]
            it["thumb"] = thumb_map.get(aid, it.get("thumb") or THUMB_FALLBACK.format(asset_id=aid))

        # Sort newest-ish by created, fallback by assetId
        def sort_key(it: Dict[str, Any]) -> Tuple[int, int]:
            ts = -1
            c = it.get("created")
            if isinstance(c, str) and c:
                try:
                    ts = int(datetime.datetime.fromisoformat(c.replace("Z","+00:00")).timestamp())
                except Exception:
                    ts = -1
            return (ts, int(it.get("assetId", 0)))
        items.sort(key=sort_key, reverse=True)

        write_json_atomic(out_path, {"generatedAt": now_iso(), "items": items})
        print(f"[ok] {out_path}: {len(items)} créations (profil/groupe)")

    except Exception as e:
        print(f"[warn] {out_path}: keep previous ({e})")
        if prev is None:
            write_json_atomic(out_path, {"generatedAt": now_iso(), "items": []})

def main() -> None:
    time.sleep(4.0 + random.random() * 10.0)
    update_file("data_user.json", 1, USER_ID)
    time.sleep(8.0 + random.random() * 14.0)
    update_file("data_group.json", 2, GROUP_ID)

if __name__ == "__main__":
    main()
