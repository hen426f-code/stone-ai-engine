# בדיקות לבודק שלפני החיתוך
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app, dxf_engine as DE, precut_check as PC

MAT = DE.MATERIALS["porcelan"]   # 320×160

def run(raw):
    pcs = [app.norm_piece(p) for p in raw]
    _, slabs = DE.gen_dxf([dict(p) for p in pcs], MAT)
    return PC.check(pcs, slabs, MAT)

# תקין: חתיכה עם כיור באמצע
r = run([{"len": 300, "depth": 62, "openings": [{"kind": "כיור", "from_left_cm": 150, "w": 50, "h": 40}]}])
assert r["ok"] and not r["warnings"], r
assert r["usage"]["slabs"] == 1 and r["usage"]["used_pct"] == round(100 * 300 * 62 / (320 * 160), 1)

# חתיכה ארוכה מהלוח
r = run([{"len": 340, "depth": 62}])
assert not r["ok"] and any("גדולה מהלוח" in e for e in r["errors"]), r

# פתח שיוצא מהחתיכה
r = run([{"len": 100, "depth": 60, "openings": [{"from_left_cm": 90, "w": 30, "h": 20}]}])
assert any("מחוץ לחתיכה" in e for e in r["errors"]), r

# שני פתחים חופפים
r = run([{"len": 200, "depth": 60, "openings": [{"kind": "כיור", "from_left_cm": 80, "w": 50, "h": 40},
                                                {"kind": "כיריים", "from_left_cm": 110, "w": 50, "h": 40}]}])
assert any("חופפים" in e for e in r["errors"]), r

# פס צר בין הפתח לשפה: כיור קרוב לחזית
r = run([{"len": 200, "depth": 60, "openings": [{"from_left_cm": 100, "w": 50, "h": 40, "from_front_cm": 22}]}])
assert r["ok"] and any("2 ס״מ" in w for w in r["warnings"]), r

# פתח בלי מידה
r = run([{"len": 200, "depth": 60, "openings": [{"kind": "כיור", "from_left_cm": 100}]}])
assert any("לא ייחתכו" in w for w in r["warnings"]), r

# פתח מחוץ למתאר של חתיכת L (בתוך המלבן החוסם, מחוץ לצורה)
L = [(0, 0), (2000, 0), (2000, 600), (600, 600), (600, 1500), (0, 1500)]
p = {"len": 200, "depth": 150, "outline": [(x, y, 0) for x, y in L], "outline_pts": L,
     "openings": [{"from_left_cm": 150, "w": 30, "h": 20, "from_front_cm": 110}]}
r = run([p])
assert any("קו המתאר" in e for e in r["errors"]), r
print("ok")
