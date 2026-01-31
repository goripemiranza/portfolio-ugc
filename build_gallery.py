import os
import json
import re
import unicodedata
from datetime import datetime, timezone

ROOT_CANDIDATES = ["gallery", "Gallery", "GALLERY"]

EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

def strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))

_num_re = re.compile(r"(\d+)")

def sort_key(filename: str):
    base = os.path.basename(filename)
    m = _num_re.search(base)
    n = int(m.group(1)) if m else 10**9
    return (n, base.lower())

def find_root():
    for r in ROOT_CANDIDATES:
        if os.path.isdir(r):
            return r
    return None

def main():
    root = find_root()
    if not root:
        out = {"updated": datetime.now(timezone.utc).isoformat(), "images": []}
        with open("gallery.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("No gallery folder found. Wrote empty gallery.json")
        return

    images = []

    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in EXTS:
                continue
            rel = os.path.join(dirpath, fn).replace("\\", "/")
            images.append({"url": rel})

    images.sort(key=lambda x: sort_key(x["url"]))

    out = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "images": images,
    }

    with open("gallery.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote gallery.json (images={len(images)})")

if __name__ == "__main__":
    main()
