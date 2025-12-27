#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fetch_ugc.py (v10) — SORTIE = UNIQUEMENT items en vente (prix disponible)
- Source: Catalog Search API (v2) pour lister les items créés par un User / Group
- Vérification: Economy API (v2/assets/{id}/details) pour savoir si l'item est EN VENTE (IsForSale) et son prix
- Filtre: uniquement UGC "avatar" (accessoires / vêtements) via AssetTypeId (Hat/Accessory/Layered Clothing/Classic clothing)
- Anti 429: backoff + fallback roproxy + cache (garde le JSON précédent si l'API rate-limit)

IDs:
- User lulu8203 = 828726934
- Group Powerful Artists = 16981319

Remarque: Certains créateurs "publient" via un user même si la gestion est dans un groupe.
Si data_group.json reste à 0 alors que vous voyez des items sur le store du groupe, dites-moi
et on passera en mode "liste de creators" (staff) explicitement.
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

USER_ID = 828726934
GROUP_ID = 16981319

CATALOG_BASES = ["https://catalog.roblox.com", "https://catalog.roproxy.com"]
ECONOMY_BASES = ["https://economy.roblox.com", "https://economy.roproxy.com"]

CATALOG_SEARCH_PATH = "/v2/search/items/details"
ECON_ASSET_DETAILS_PATH = "/v2/assets/{asset_id}/details"

THUMB_TEMPLATE = "https://www.roblox.com/asset-thumbnail/image?assetId={asset_id}&width=420&height=420&format=png"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "PortfolioUGCFetch/10.0 (+https://roblox.com)",
}

# AssetTypeId filter (UGC / avatar items)
# Source: Roblox AssetType enum lists these IDs (hat/accessories & layered clothing). 
# We keep a broad set to not miss UGC clothing.
UGC_ASSET_TYPE_IDS: Set[int] = {
    # Classic clothing
    2,   # TShirt
    11,  # Shirt
    12,  # Pants

    # Accessories (classic + UGC)
    8,   # Hat
    41,  # HairAccessory
    42,  # FaceAccessory
    43,  # NeckAccessory
    44,  # ShoulderAccessory
    45,  # FrontAccessory
    46,  # BackAccessory
    47,  # WaistAccessory

    # Layered clothing accessories (UGC)
    64, 65, 66, 67, 68, 69, 70, 71, 72,
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

def http_get_json_with_fallback(bases: List[str], path: str, params: Dict[str, Any], timeout: int = 30, max_retries: int = 6) -> Dict[str, Any]:
    last_err: Optional[Exception] = None
    query = urllib.parse.urlencode(params)

    # Each attempt rotates bases to reduce 429 bursts on one host.
    for attempt in range(max_retries):
        random.shuffle(bases)
        for base in bases:
            url = f"{base}{path}?{query}"
            try:
                req = urllib.request.Request(url, headers=HEADERS, method="GET")
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    raw = r.read().decode("utf-8", errors="replace")
                return json.loads(raw)

            except HTTPError as e:
                last_err = e
                code = getattr(e, "code", None)

                # 429 / 5xx -> backoff and retry
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

                    # progressive backoff
                    sleep_s = min(90.0, sleep_s + attempt * 9.0)
                    print(f"[http] {code} -> sleep {sleep_s:.1f}s (attempt {attempt+1}/{max_retries}) {base}")
                    time.sleep(sleep_s)
                    continue

                # Other HTTP errors: break base rotation and propagate
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

def fetch_creator_asset_ids(creator_type: int, creator_target_id: int, limit: int = 30, max_pages: int = 20) -> List[int]:
    """
    Catalog v2 search endpoint returns objects with:
      - id (assetId)
      - itemType ("Asset" / "Bundle")
      - assetType (number)
      - name, price (sometimes), etc.
    """
    ids: List[int] = []
    cursor = ""

    for _ in range(max_pages):
        params = {
            "CreatorType": creator_type,
            "CreatorTargetId": creator_target_id,
            "SortType": 6,              # RecentlyCreated
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

    # unique preserve order
    seen: Set[int] = set()
    out: List[int] = []
    for x in ids:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out

def fetch_asset_details(asset_id: int) -> Optional[Dict[str, Any]]:
    params = {}  # none
    path = ECON_ASSET_DETAILS_PATH.format(asset_id=asset_id)
    j = http_get_json_with_fallback(ECONOMY_BASES, path, params, timeout=30, max_retries=5)

    # economy details typical fields:
    # Name, PriceInRobux, IsForSale, AssetTypeId, Created, Updated, etc.
    is_for_sale = j.get("IsForSale")
    price = j.get("PriceInRobux")
    asset_type_id = j.get("AssetTypeId")

    if is_for_sale is not True:
        return None
    if not isinstance(price, int):
        return None
    if not isinstance(asset_type_id, int):
        return None
    if asset_type_id not in UGC_ASSET_TYPE_IDS:
        return None

    name = j.get("Name") or f"Item {asset_id}"
    created = j.get("Created") or None

    return {
        "assetId": asset_id,
        "name": name,
        "type": ASSET_TYPE_NAME.get(asset_type_id, f"AssetType {asset_type_id}"),
        "price": price,
        "created": created,
        "thumb": THUMB_TEMPLATE.format(asset_id=asset_id),
    }

def update_file(out_path: str, creator_type: int, creator_target_id: int) -> None:
    prev = read_json(out_path)
    prev_items = prev.get("items") if isinstance(prev, dict) else None
    prev_map = {it.get("assetId"): it for it in prev_items} if isinstance(prev_items, list) else {}

    try:
        asset_ids = fetch_creator_asset_ids(creator_type, creator_target_id)
        # If catalog is rate-limited and returns empty, keep previous (avoid nuking)
        if not asset_ids and prev_items:
            print(f"[warn] {out_path}: empty asset list -> keep previous")
            return

        items: List[Dict[str, Any]] = []
        for idx, aid in enumerate(asset_ids):
            # cache reuse (still on sale?) -> we refresh a bit but keep light: reuse and only refresh some
            cached = prev_map.get(aid)
            if isinstance(cached, dict) and isinstance(cached.get("price"), int) and isinstance(cached.get("name"), str):
                # still verify 1 out of 6 to avoid stale prices
                if idx % 6 != 0:
                    items.append(cached)
                    continue

            det = fetch_asset_details(aid)
            if det is not None:
                items.append(det)

            time.sleep(0.55 + random.random() * 0.45)

        # sort by created desc if available
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
        print(f"[ok] {out_path}: {len(items)} UGC en vente")

    except Exception as e:
        print(f"[warn] {out_path}: keep previous ({e})")
        if prev is None:
            write_json_atomic(out_path, {"generatedAt": now_iso(), "items": []})

def main() -> None:
    # Stagger to avoid hitting the same window as other bots
    time.sleep(4.0 + random.random() * 10.0)
    update_file("data_user.json", 1, USER_ID)
    time.sleep(8.0 + random.random() * 14.0)
    update_file("data_group.json", 2, GROUP_ID)

if __name__ == "__main__":
    main()
