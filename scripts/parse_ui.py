# -*- coding: utf-8 -*-
import re
import xml.etree.ElementTree as ET
from pathlib import Path

p = Path(r"C:\Users\1\Desktop\Youtube\kyro_apk\kyro_ui_home.xml")
root = ET.fromstring(p.read_text(encoding="utf-8"))
texts = []
for n in root.iter("node"):
    t = (n.attrib.get("text") or "").strip()
    d = (n.attrib.get("content-desc") or "").strip()
    if t:
        texts.append(t)
    elif d:
        texts.append(f"[{d}]")
seen = set()
out = []
for t in texts:
    if t in seen:
        continue
    seen.add(t)
    out.append(t)
print("TEXTS:")
for t in out[:90]:
    print("-", t)
need = [
    "Kyro",
    "Сейчас",
    "План",
    "Можно",
    "Учиться",
    "Любая",
    "До 15",
    "Библиотека",
    "Папки",
    "Профиль",
    "Вечер",
]
print("\nNEED:")
for k in need:
    hit = any(k.lower() in t.lower() for t in out)
    print(("OK" if hit else "MISS"), k)
