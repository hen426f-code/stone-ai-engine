# אורך קווי החיתוך והגרונג בקובץ המכונה, לדוח ייצור
import os, sys, io, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf
import app, dxf_engine as DE

MAT = DE.MATERIALS["porcelan"]

def lengths(raw):
    pcs = [app.norm_piece(p) for p in raw]
    txt, _ = DE.gen_dxf([dict(p) for p in pcs], MAT)
    return DE.cut_lengths(txt)

assert lengths([{"len": 100, "depth": 60}]) == {"cut_m": 3.2, "mitre_m": 0.0}
# פתח כיור 50×40 מוסיף 1.8 מטר
assert lengths([{"len": 100, "depth": 60, "openings": [{"kind": "כיור", "from_left_cm": 50, "w": 50, "h": 40}]}])["cut_m"] == 5.0
# צלע קדמית בגרונג נספרת בנפרד
assert lengths([{"len": 100, "depth": 60, "edges": {"front": "mitre"}}]) == {"cut_m": 2.2, "mitre_m": 1.0}

# קשת: חצי עיגול על מיתר של מטר
doc = ezdxf.new("R12")
doc.modelspace().add_polyline2d([(0, 0, 0, 0, 1), (1000, 0)], format="xyseb", dxfattribs={"layer": "1000-13_5"})
s = io.StringIO(); doc.write(s)
assert DE.cut_lengths(s.getvalue())["cut_m"] == round(math.pi / 2, 2)

# כל תשובה של המנוע מחזירה את האורכים בתוך usage
r = app.app.test_client().post("/api/pieces", json={"pieces": [{"len": 100, "depth": 60}], "material": "porcelan"}).get_json()
assert r["check"]["usage"]["cut_m"] == 3.2, r["check"]["usage"]
print("ok")
