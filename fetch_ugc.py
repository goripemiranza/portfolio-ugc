# fetch_ugc.py
# Roblox Marketplace v2 – fetch all onsale items (user + group)

import requests
import json
import time

USER_ID = 0      # <-- PUT YOUR USER ID
GROUP_ID = 0     # <-- PUT YOUR GROUP ID

OUTPUT_USER = "data_user.json"
OUTPUT_GROUP = "data_group.json"

BASE_URL = "https://catalog.roblox.com/v2/search/items/details"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def fetch_items(creator_type, creator_id):
    items = []
    cursor = ""
    while True:
        params = {
            "Category": "All",
            "Subcategory": "All",
            "SalesTypeFilter": "1",  # OnSale
            "CreatorType": creator_type,
            "CreatorTargetId": creator_id,
            "Limit": 30,
            "Cursor": cursor
        }
        r = requests.get(BASE_URL, params=params, headers=HEADERS)
        if r.status_code != 200:
            break
        data = r.json()
        for item in data.get("data", []):
            if item.get("price", 0) > 0:
                items.append(item)
        cursor = data.get("nextPageCursor")
        if not cursor:
            break
        time.sleep(0.2)
    return items

user_items = fetch_items("User", USER_ID)
group_items = fetch_items("Group", GROUP_ID)

with open(OUTPUT_USER, "w", encoding="utf-8") as f:
    json.dump(user_items, f, indent=2)

with open(OUTPUT_GROUP, "w", encoding="utf-8") as f:
    json.dump(group_items, f, indent=2)

print(f"Wrote {OUTPUT_USER} ({len(user_items)} items)")
print(f"Wrote {OUTPUT_GROUP} ({len(group_items)} items)")
