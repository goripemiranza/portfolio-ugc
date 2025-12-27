#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génère 2 fichiers utilisés par index.html :
- data_user.json  (UGC créés par l'utilisateur lulu8203)
- data_group.json (UGC créés par le groupe Powerful Artists)
"""
import json
import time
import datetime
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

USER_ID = 828726934
GROUP_ID = 16981319

CATALOG_ENDPOINT = "https://catalog.roblox.com/v1/search/items/details"
ECONOMY_DETAILS = "https://economy.roblox.com/v2/assets/{asset_id}/details"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "PortfolioUGCFetch/1.0 (+https://roblox.com)",
}

def http_get_json(url: str, timeout: int = 30) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers=HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read().decode("utf-8", errors="replace")
    return json.loads(data)

def iso_to_ts(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        s = iso.replace("Z", "+00:00")
        dt = datetime.datetime.fromisoformat(s)
        return int(dt.timestamp())
    except Exception:
        return None

def fetch_created_from_economy(asset_id: int) -> Optional[str]:
    try:
        url = ECONOMY_DETAILS.format(asset_id=asset_id)
        j = http_get_json(url)
        for k in ("Created", "created", "createdUtc", "created_at", "createdAt"):
            v = j.get(k)
            if isinstance(v, str) and v:
                return v
    except Exception:
        return None
    return None

def fetch_all_catalog_items(creator_type: int, creator_target_id: int, limit: int = 30, max_pages: int = 160) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    cursor: str = ""

    for _ in range(max_pages):
        params = {
            "CreatorType": str(creator_type),           # 1 user, 2 group
            "CreatorTargetId": str(creator_target_id),
            "Limit": str(limit),
            "IncludeNotForSale": "true",
        }
        if cursor:
            params["Cursor"] = cursor

        url = CATALOG_ENDPOINT + "?" + urllib.parse.urlencode(params)
        j = http_get_json(url)
        data = j.get("data", []) or []

        for d in data:
            asset_id = d.get("id")
            if not isinstance(asset_id, int):
                continue

            name = d.get("name") or f"Item {asset_id}"
            asset_type = None
            at = d.get("assetType")
            if isinstance(at, dict):
                asset_type = at.get("name")

            price = d.get("price")
            if not isinstance(price, (int, float)):
                price = None

            created = None
            for k in ("created", "Created", "createdUtc", "createdAt"):
                v = d.get(k)
                if isinstance(v, str) and v:
                    created = v
                    break

            items.append({
                "assetId": asset_id,
                "name": name,
                "type": asset_type or d.get("itemType") or "UGC",
                "price": int(price) if isinstance(price, (int, float)) else None,
                "created": created,
            })

        cursor = j.get("nextPageCursor") or ""
        if not cursor:
            break

        time.sleep(0.15)

    seen = set()
    dedup = []
    for it in items:
        if it["assetId"] in seen:
            continue
        seen.add(it["assetId"])
        dedup.append(it)
    return dedup

def enrich_created_dates(items: List[Dict[str, Any]]) -> None:
    missing = [it for it in items if not it.get("created")]
    for it in missing:
        created = fetch_created_from_economy(it["assetId"])
        if created:
            it["created"] = created
        time.sleep(0.10)

def finalize(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for it in items:
        it["createdTs"] = iso_to_ts(it.get("created"))
    items.sort(key=lambda x: (x.get("createdTs") or -1, x["assetId"]), reverse=True)
    return items

def write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def main() -> None:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    user_items = fetch_all_catalog_items(creator_type=1, creator_target_id=USER_ID)
    group_items = fetch_all_catalog_items(creator_type=2, creator_target_id=GROUP_ID)

    enrich_created_dates(user_items)
    enrich_created_dates(group_items)

    user_items = finalize(user_items)
    group_items = finalize(group_items)

    write_json("data_user.json", {"generatedAt": now_iso, "items": user_items})
    write_json("data_group.json", {"generatedAt": now_iso, "items": group_items})

    print("OK: data_user.json + data_group.json")

if __name__ == "__main__":
    main()
