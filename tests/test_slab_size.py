# מידות לוח של המפעל גוברות על ברירת המחדל של החומר, רק בטווח סביר. העובי לא משתנה.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app, dxf_engine as DE

m = app._mat({"material": "dekton", "slabL": 320, "slabW": 160})
assert (m["slabL"], m["slabW"], m["depth"]) == (320, 160, DE.MATERIALS["dekton"]["depth"])
assert DE.MATERIALS["dekton"]["slabL"] == 330          # ברירת המחדל לא נדרסה
for bad in ({"slabL": 50, "slabW": 40}, {"slabL": 150, "slabW": 300}, {"slabL": "x", "slabW": 160}, {}):
    m = app._mat(dict(bad, material="porcelan"))
    assert (m["slabL"], m["slabW"]) == (320, 160), bad

c = app.app.test_client()
pcs = [{"len": 300, "depth": 62}]
r1 = c.post("/api/pieces", json={"pieces": pcs, "material": "porcelan"}).get_json()
r2 = c.post("/api/pieces", json={"pieces": pcs, "material": "porcelan", "slabL": 280, "slabW": 160}).get_json()
assert r1["check"]["ok"] and not r2["check"]["ok"]      # 300 לא נכנס בלוח של 280
assert r2["check"]["usage"]["slabs_m2"] == 4.48
print("ok")
