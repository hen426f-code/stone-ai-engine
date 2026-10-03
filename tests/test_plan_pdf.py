# תוכנית החיתוך: אף חתיכה לא נשמטת מרשימת החתיכות, וכל חתיכה ממוספרת על הלוח
import os, sys, re, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pypdf import PdfReader
import app, dxf_engine as DE, prodim_reader as PR, precut_check as PC

MAT = DE.MATERIALS["porcelan"]
raw = [{"len": 150 + i * 5, "depth": 60, "job": "כהן" if i % 2 else "לוי"} for i in range(14)]
pcs = [app.norm_piece(p) for p in raw]
assert all(p["job"] in ("כהן", "לוי") for p in pcs)

with tempfile.TemporaryDirectory() as td:
    pth = os.path.join(td, "p.pdf")
    _, nslabs = PR.render_prodim_plan(pcs, MAT, pth)
    pages = [pg.extract_text() for pg in PdfReader(pth).pages]

piece_pages = [t for t in pages if "חתיכות לחיתוך" in t or "ךותיחל תוכיתח" in t]
slab_pages = pages[len(piece_pages):]
assert len(piece_pages) >= 2, len(piece_pages)          # 14 חתיכות לא נכנסות בעמוד אחד
assert len(pages) == len(piece_pages) + nslabs
tags = sorted(int(n) for t in slab_pages for n in re.findall(r"(\d+)  [\d.]+×", t))
assert tags == list(range(1, 15)), tags                 # כל חתיכה מופיעה פעם אחת על הלוחות

# שם העבודה מופיע בהודעות הבודק
_, slabs = DE.gen_dxf([dict(p) for p in pcs], MAT)
r = PC.check(pcs + [app.norm_piece({"len": 340, "depth": 60, "job": "גור"})], slabs, MAT)
assert any(e.startswith("גור, ") for e in r["errors"]), r["errors"]
print("ok")
