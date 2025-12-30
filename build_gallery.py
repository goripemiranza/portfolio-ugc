import os
import json
import re
import unicodedata
from datetime import datetime, timezone

ROOT_CANDIDATES = ["commissions", "Commission", "commission", "COMMISSIONS"]

EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

def strip_accents(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))

def classify(filename: str) -> str:
    name = strip_accents(filename).lower()
    # "texture", "texture 1"
    if name.startswith("texture") or " texture" in name:
        return "textures"
    # "modele", "modele 1", "model", "model 1"
    if name.startswith("modele") or " modele" in name or name.startswith("model") or " model" in name:
        return "models"
    # default
    return "models"

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
        out = {"updated": datetime.now(timezone.utc).isoformat(), "models": [], "textures": []}
        with open("commissions.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("No commissions folder found. Wrote empty commissions.json")
        return

    models = []
    textures = []

    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in EXTS:
                continue
            rel = os.path.join(dirpath, fn).replace("\\", "/")
            bucket = classify(fn)
            if bucket == "textures":
                textures.append(rel)
            else:
                models.append(rel)

    models.sort(key=sort_key)
    textures.sort(key=sort_key)

    out = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "models": models,
        "textures": textures,
    }

    with open("commissions.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Wrote commissions.json (models={len(models)} textures={len(textures)})")

if __name__ == "__main__":
    main()
