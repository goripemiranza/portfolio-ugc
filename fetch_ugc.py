#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_ugc.py (v9) — Portfolio UGC (User + Group) pour GitHub Pages

Fixes principaux vs v8 :
- L’API /v1/search/items/details renvoie l’assetId dans le champ **id** (pas assetId).
- Le type d’item est un **assetType** numérique → mapping vers un nom lisible (BackAccessory, HairAccessory…).
- Paramètres de requête en PascalCase (Category, CreatorType, CreatorTargetId, IncludeNotForSale, Limit…).
- Anti "0 items" accidentel : si la récupération retourne 0 alors qu’un JSON précédent avait des items,
  on conserve l’ancien fichier (souvent dû à un rate-limit/429 ou une réponse vide temporaire).
- Anti 429 : backoff + bascule automatique vers un endpoint proxy public (catalog.roproxy.com) en fallback.
  (Aucune authentification, uniquement des requêtes publiques.)

Sort :
- SortType=6 (RecentlyCreated) pour obtenir l’ordre le plus récent (tri côté API).

Sorties :
- data_user.json
- data_group.json
"""

from __future__ import annotations
import json
import time
import random
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

USER_ID = 828726934          # lulu8203
GROUP_ID = 16981319          # Powerful Artists

OUT_USER = "data_user.json"
OUT_GROUP = "data_group.json"

# Endpoints (1er = officiel, 2e = fallback proxy public)
CATALOG_BASES = [
    "https://catalog.roblox.com",
    "https://catalog.roproxy.com",
]

CATALOG_PATH = "/v1/search/items/details"

# AssetType IDs (Roblox) -> nom lisible (subset utile UGC)
ASSET_TYPE_NAME: Dict[int, str] = {
    2: "TShirt",
    8: "Hat",
    11: "Shirt",
    12: "Pants",
    17: "Head",
    18: "Face",
    19: "Gear",
    41: "HairAccessory",
    42: "FaceAccessory",
    43: "NeckAccessory",
    44: "ShoulderAccessory",
    45: "FrontAccessory",
    46: "BackAccessory",
    47: "WaistAccessory",
    57: "EarAccessory",
    58: "EyeAccessory",
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
    79: "DynamicHead",
}

# Filtre "UGC portfolio" (avatar items + gear)
UGC_ASSET_TYPE_IDS = set([
    2, 8, 11, 12, 19,
    41, 42, 43, 44, 45, 46, 47,
    57, 58,
    64, 65, 66, 67, 68, 69, 70, 71, 72,
    76, 77, 79,
])

@dataclass
class HttpResult:
    ok: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    status: Optional[int] = None
    used_base: Optional[str] = None

def _thumb_url(asset_id: int) -> str:
    # Pas de fetch JS → juste <img src="...">, donc pas de CORS
    return f"https://www.roblox.com/asset-thumbnail/image?assetId={asset_id}&width=420&height=420&format=png"

def http_get_json(url: str, timeout: float = 25.0) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ugc-portfolio-bot/1.0 (+github-actions)",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", errors="replace")
        return json.loads(raw)

def get_with_backoff(url: str, max_retries: int = 6) -> HttpResult:
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            j = http_get_json(url)
            if isinstance(j, dict) and j.get("errors"):
                # API retourne parfois {errors:[...]}
                return HttpResult(ok=False, data=j, error="api_errors", status=None)
            return HttpResult(ok=True, data=j)
        except urllib.error.HTTPError as e:
            status = int(getattr(e, "code", 0) or 0)
            last_err = f"HTTP {status}"
            if status == 429:
                # backoff exponentiel + jitter
                sleep_s = min(60.0, (2.0 ** (attempt - 1)) * 2.5) + random.uniform(0.0, 1.8)
                print(f"[http] 429 -> sleep {sleep_s:.1f}s (attempt {attempt}/{max_retries})")
                time.sleep(sleep_s)
                continue
            try:
                body = e.read().decode("utf-8", errors="replace")
                last_err = f"HTTP {status}: {body[:200]}"
            except Exception:
                last_err = f"HTTP {status}"
            break
        except Exception as e:
            last_err = str(e)
            sleep_s = min(20.0, 2.0 * attempt) + random.uniform(0.0, 0.8)
            print(f"[http] err -> sleep {sleep_s:.1f}s (attempt {attempt}/{max_retries}) :: {e}")
            time.sleep(sleep_s)

    return HttpResult(ok=False, error=last_err, status=None)

def build_catalog_url(base: str, creator_type: int, creator_target_id: int, cursor: str = "", limit: int = 30) -> str:
    params = {
        "Category": "1",                 # "All" (on filtre ensuite par assetTypeId)
        "CreatorType": str(creator_type),        # 1 user / 2 group
        "CreatorTargetId": str(creator_target_id),
        "IncludeNotForSale": "true",
        "SortType": "6",                 # RecentlyCreated (catalog sort enum)
        "Limit": str(limit),
    }
    if cursor:
        params["Cursor"] = cursor
    return base + CATALOG_PATH + "?" + urllib.parse.urlencode(params)

def fetch_creator_items(creator_type: int, creator_target_id: int, max_pages: int = 20) -> Tuple[List[Dict[str, Any]], str]:
    """
    Retourne (items, used_base).
    Bascule automatiquement vers roproxy si 429/erreur sur l'endpoint officiel.
    """
    used_base = CATALOG_BASES[0]
    base_index = 0

    cursor = ""
    out: List[Dict[str, Any]] = []

    page = 0
    while page < max_pages:
        page += 1
        url = build_catalog_url(CATALOG_BASES[base_index], creator_type, creator_target_id, cursor=cursor, limit=30)

        r = get_with_backoff(url, max_retries=6)

        if not r.ok:
            # Si on est sur l'officiel, on tente le fallback 1 fois tout de suite
            if base_index == 0:
                print(f"[warn] fetch failed on official -> try fallback proxy once :: {r.error}")
                base_index = 1
                used_base = CATALOG_BASES[1]
                continue
            raise RuntimeError(f"GET failed: {url} / {r.error}")

        j = r.data or {}
        used_base = CATALOG_BASES[base_index]

        data = j.get("data") or []
        if not isinstance(data, list):
            data = []

        for d in data:
            if not isinstance(d, dict):
                continue
            if d.get("itemType") != "Asset":
                continue

            asset_id = d.get("id")
            if not isinstance(asset_id, int):
                continue

            asset_type_id = d.get("assetType")
            if isinstance(asset_type_id, str) and asset_type_id.isdigit():
                asset_type_id = int(asset_type_id)

            # Filtre UGC (portfolio)
            if not isinstance(asset_type_id, int) or asset_type_id not in UGC_ASSET_TYPE_IDS:
                continue

            name = d.get("name") if isinstance(d.get("name"), str) else None
            price = d.get("price") if isinstance(d.get("price"), int) else None
            is_offsale = bool(d.get("isOffSale")) if "isOffSale" in d else None
            price_status = d.get("priceStatus") if isinstance(d.get("priceStatus"), str) else None

            out.append({
                "assetId": asset_id,
                "name": name,
                "assetTypeId": asset_type_id,
                "assetTypeName": ASSET_TYPE_NAME.get(asset_type_id, f"AssetType{asset_type_id}"),
                "price": price,
                "isOffSale": is_offsale,
                "priceStatus": price_status,
                "thumb": _thumb_url(asset_id),
            })

        cursor = j.get("nextPageCursor") or ""
        if not cursor:
            break

        # petite pause entre pages (évite bursts)
        time.sleep(0.7 + random.uniform(0.0, 0.4))

    # dé-dup (au cas où)
    seen = set()
    dedup = []
    for it in out:
        aid = it["assetId"]
        if aid in seen:
            continue
        seen.add(aid)
        dedup.append(it)

    # rank (ordre API) : 1 = plus récent
    for i, it in enumerate(dedup, start=1):
        it["rank"] = i

    return dedup, used_base

def read_previous_count(path: str) -> int:
    try:
        p = Path(path)
        if not p.exists():
            return 0
        j = json.loads(p.read_text(encoding="utf-8"))
        items = j.get("items") or []
        return len(items) if isinstance(items, list) else 0
    except Exception:
        return 0

def write_json_safely(path: str, payload: dict) -> None:
    tmp = Path(path + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(Path(path))

def main() -> None:
    # Jitter au début (réduit les collisions avec d'autres workflows)
    time.sleep(random.uniform(1.5, 4.0))

    # USER
    prev_u = read_previous_count(OUT_USER)
    user_items, user_base = fetch_creator_items(creator_type=1, creator_target_id=USER_ID)
    if len(user_items) == 0 and prev_u > 0:
        print(f"[warn] {OUT_USER}: 0 item (prev={prev_u}) -> keep previous")
    else:
        write_json_safely(OUT_USER, {
            "source": "catalog.v1.search.items.details",
            "usedBase": user_base,
            "creator": {"type": "User", "id": USER_ID},
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "items": user_items,
        })
        print(f"[ok] {OUT_USER}: {len(user_items)} item(s) (base={user_base})")

    # Petite pause
    time.sleep(1.2 + random.uniform(0.0, 0.6))

    # GROUP
    prev_g = read_previous_count(OUT_GROUP)
    group_items, group_base = fetch_creator_items(creator_type=2, creator_target_id=GROUP_ID)
    if len(group_items) == 0 and prev_g > 0:
        print(f"[warn] {OUT_GROUP}: 0 item (prev={prev_g}) -> keep previous")
    else:
        write_json_safely(OUT_GROUP, {
            "source": "catalog.v1.search.items.details",
            "usedBase": group_base,
            "creator": {"type": "Group", "id": GROUP_ID},
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "items": group_items,
        })
        print(f"[ok] {OUT_GROUP}: {len(group_items)} item(s) (base={group_base})")

if __name__ == "__main__":
    main()
