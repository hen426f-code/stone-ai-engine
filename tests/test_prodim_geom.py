# קשתות וצלעות גרונג בקובץ מודד: הקשת נשארת על הצלע הנכונה גם כשהמתאר צויר עם כיוון השעון,
# וצלע כתומה (גרונג) יוצאת לשכבת הזווית בקובץ המכונה.
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf
from ezdxf import bbox
import prodim_reader as PR, dxf_engine as DE, precut_check as PC

MAT = DE.MATERIALS["porcelan"]
tmp = tempfile.mkdtemp()

def piece_file(pts, bulges, colors=None, name="p"):
    d = ezdxf.new("R12"); m = d.modelspace()
    n = len(pts)
    for k in range(n):
        a, b = pts[k], pts[(k + 1) % n]
        c = colors[k] if colors else 3
        if bulges[k]:
            pl = m.add_polyline2d([a, b], dxfattribs={"color": c})
            pl.vertices[0].dxf.bulge = bulges[k]
        else:
            m.add_line(a, b, dxfattribs={"color": c})
    f = os.path.join(tmp, name + ".dxf"); d.saveas(f); return f

# מלבן 1000×600 עם קשת החוצה בצלע הימנית, פעם נגד השעון ופעם עם השעון
ccw = [(0, 0), (1000, 0), (1000, 600), (0, 600)]
for name, pts, bul in (("ccw", ccw, [0, 0.3, 0, 0]),
                       ("cw", ccw[::-1], [0, -0.3, 0, 0])):
    pcs, _ = PR.read_prodim(piece_file(pts, bul, name=name))
    p = pcs[0]
    arcs = [(p["outline"][k], p["outline"][(k + 1) % 4]) for k in range(4) if p["outline"][k][2]]
    assert len(arcs) == 1 and arcs[0][0][0] == arcs[0][1][0] == 1000, (name, p["outline"])
    # בקובץ המכונה: הקשת מוסיפה רוחב רק מימין, כלומר רוחב 1090 ולא קשת בצלע השמאלית
    txt, slabs = DE.gen_dxf([dict(p)], MAT)
    doc = ezdxf.read(__import__("io").StringIO(txt))
    ext = bbox.extents(doc.modelspace())
    assert abs((ext.extmax.x - ext.extmin.x) - 1090) < 1 and abs((ext.extmax.y - ext.extmin.y) - 600) < 1, (name, ext)

# צלע ימנית כתומה (גרונג)
pcs, has_m = PR.read_prodim(piece_file(ccw, [0, 0, 0, 0], colors=[3, 30, 3, 7], name="mitre"))
p = pcs[0]
assert has_m and len(p["mitre_segs"]) == 1, p
k = p["mitre_segs"][0]
a, b = p["outline"][k], p["outline"][(k + 1) % 4]
assert a[0] == b[0] == 1000, p["outline"]
txt, slabs = DE.gen_dxf([dict(p)], MAT)
doc = ezdxf.read(__import__("io").StringIO(txt))
ml = [e for e in doc.modelspace() if e.dxf.layer.startswith("1000DPT")]
assert len(ml) == 1 and ml[0].dxftype() == "LINE", [e.dxftype() for e in ml]
assert abs(ml[0].dxf.start.x - ml[0].dxf.end.x) < 0.01 and abs(abs(ml[0].dxf.start.y - ml[0].dxf.end.y) - 600) < 0.01
assert PC.check([p], slabs, MAT)["ok"]

# גרונג על קשת = שגיאה בבדיקה לפני חיתוך
pcs, _ = PR.read_prodim(piece_file(ccw, [0, 0.3, 0, 0], colors=[3, 30, 3, 7], name="mitre_arc"))
txt, slabs = DE.gen_dxf([dict(pcs[0])], MAT)
assert any("גרונג על קשת" in e for e in PC.check(pcs, slabs, MAT)["errors"])
print("ok")
