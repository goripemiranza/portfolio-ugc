# fetch_ugc.py
# Roblox Marketplace v2 – NO external libs (urllib only)

import json
import time
import urllib.request
import urllib.parse

USER_ID = 828726934      # PUT YOUR USER ID
GROUP_ID = 16981319     # PUT YOUR GROUP ID

OUTPUT_USER = "data_user.json"
OUTPUT_GROUP = "data_group.json"

BASE_URL = "https://catalog.roblox.com/v2/search/items/details"

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
        url = BASE_URL + "?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url) as r:
                data = json.loads(r.read().decode())
        except Exception:
            break

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
