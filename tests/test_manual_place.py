# סידור ידני (מצילום הלוח): המיקום שהמשתמש קבע עובר כמו שהוא ל-DXF, והבדיקה תופסת חפיפה וחריגה.
# וגם: הסידור האוטומטי מוחזר לאתר, ולוח שארית קטן מתקבל רק במצב שארית.
import os, sys, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf
import app

c = app.app.test_client()
pcs = [{"len": 200, "depth": 60, "label": "א"}, {"len": 100, "depth": 60, "label": "ב"}]
base = {"pieces": pcs, "material": "porcelan"}

r = c.post("/api/pieces", json=base).get_json()
assert r["ok"] and r["slabL"] == 320 and r["slabW"] == 160
lay = r["layout"]
assert sorted(it["i"] for s in lay for it in s) == [0, 1]

def rects(dxf):
    doc = ezdxf.read(io.StringIO(dxf)); out = []
    for e in doc.modelspace():
        if e.dxftype() == "POLYLINE":
            xs = [v.dxf.location[0] for v in e.vertices]; ys = [v.dxf.location[1] for v in e.vertices]
            out.append((min(xs), min(ys), max(xs), max(ys)))
    return sorted(out)

# הזזה: החתיכה הקטנה מסובבת בפינה הימנית העליונה, הגדולה באמצע
pl = [{"slab": 0, "x": 50, "y": 40}, {"slab": 0, "x": 260, "y": 60, "rot": True}]
r = c.post("/api/pieces", json=dict(base, placements=pl)).get_json()
assert r["ok"] and r["check"]["ok"], r["check"]
assert rects(r["dxf"]) == sorted([(500, 400, 2500, 1000), (2600, 600, 3200, 1600)]), rects(r["dxf"])
assert r["layout"][0][1]["rot"] and r["layout"][0][1]["len"] == 60

# חפיפה וחריגה נתפסות
r = c.post("/api/pieces", json=dict(base, placements=[{"slab": 0, "x": 0, "y": 0}, {"slab": 0, "x": 150, "y": 10}])).get_json()
assert any("חופפות" in e for e in r["check"]["errors"])
r = c.post("/api/pieces", json=dict(base, placements=[{"slab": 0, "x": -1, "y": 0}, {"slab": 1, "x": 250, "y": 0}])).get_json()
assert sum("חורגת" in e for e in r["check"]["errors"]) == 2 and r["slabs"] == 2

# מיקום חסר = שגיאה ברורה
r = c.post("/api/pieces", json=dict(base, placements=[{"slab": 0, "x": 0, "y": 0}]))
assert r.status_code == 400

# לוח שארית: 70×65 רק במצב שארית
small = {"pieces": [{"len": 60, "depth": 60}], "material": "porcelan", "slabL": 70, "slabW": 65}
assert c.post("/api/pieces", json=small).get_json()["slabL"] == 320
r = c.post("/api/pieces", json=dict(small, remnant=True)).get_json()
assert r["slabL"] == 70 and r["check"]["ok"]
r = c.post("/api/pieces", json=dict(small, remnant=True, slabL=50, slabW=40)).get_json()
assert not r["check"]["ok"]                              # 60 לא נכנס בשארית 50×40
assert c.post("/api/pieces", json=dict(small, remnant=True, slabW=5)).status_code == 400
print("ok")
