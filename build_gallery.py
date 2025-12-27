#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_gallery.py
- Scanne le dossier ./gallery/
- Génère ./gallery.json avec la liste des images (chemins relatifs)
- Tri: par nom de fichier (stable)

Notes:
- Certains noms peuvent contenir des séquences type #U00e9 (utilisées pour représenter des accents).
  On les décode dans la légende pour un rendu plus propre.
- Les URLs restent basées sur les vrais noms de fichiers (le front encode correctement # / espaces / accents).
"""

import json
import re
from pathlib import Path

GALLERY_DIR = Path("gallery")
OUT_JSON = Path("gallery.json")
EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

_u_re = re.compile(r"#U([0-9a-fA-F]{4})")

def decode_u_escapes(s: str) -> str:
    def repl(m):
        try:
            return chr(int(m.group(1), 16))
        except Exception:
            return m.group(0)
    return _u_re.sub(repl, s)

def main() -> None:
    items = []
    if GALLERY_DIR.exists() and GALLERY_DIR.is_dir():
        for p in sorted(GALLERY_DIR.rglob("*")):
            if p.is_file() and p.suffix.lower() in EXTS:
                rel = p.as_posix()  # ex: "gallery/xxx.png"
                cap_raw = p.stem.replace("_", " ").replace("-", " ").strip()
                caption = decode_u_escapes(cap_raw)
                items.append({"url": rel, "caption": caption})
    OUT_JSON.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] {OUT_JSON} -> {len(items)} image(s)")

if __name__ == "__main__":
    main()
