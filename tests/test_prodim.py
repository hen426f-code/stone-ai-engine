# -*- coding: utf-8 -*-
"""בדיקת קורא קובץ המודד על קובץ סינתטי. הרצה: python3 tests/test_prodim.py"""
import os, sys, tempfile, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ezdxf
import prodim_reader as PR
import dxf_engine as DE

def _line(msp, a, b, color):
    msp.add_line(a, b, dxfattribs={"color": color})

def build(path):
    d = ezdxf.new("R12"); m = d.modelspace()
    # חתיכה L: צלע חזית ירוקה (עיבוד), שאר הצלעות שחורות (קיר)
    L = [(0, 0), (3000, 0), (3000, 1800), (2400, 1800), (2400, 600), (0, 600)]
    for i in range(len(L)):
        _line(m, L[i], L[(i+1) % len(L)], 3 if i == 0 else 7)
    # כיור כחול סגור בתוך החתיכה, מרכזו 100 ס"מ משמאל ו-30 ס"מ מהחזית
    S = [(600, 100), (1400, 100), (1400, 500), (600, 500)]
    for i in range(4):
        _line(m, S[i], S[(i+1) % 4], 5)
    # שקע חשמל קטן (כחול) — כלל הגודל הופך אותו לחשמל
    E = [(2600, 1000), (2660, 1000), (2660, 1120), (2600, 1120)]
    for i in range(4):
        _line(m, E[i], E[(i+1) % 4], 5)
    # כיור בשלוש צלעות (הבסיס מפוצל לשניים) — הצלע הרביעית מושלמת
    U = [(1600, 550), (1600, 150), (1800, 150), (2000, 150), (2000, 550)]
    for i in range(len(U) - 1):
        _line(m, U[i], U[i+1], 5)
    # קו פתוח בתוך החתיכה — לא נחתך, רק אזהרה
    _line(m, (200, 200), (200, 400), 7); _line(m, (200, 400), (400, 400), 7)
    # חתיכה מלבנית שהקו העליון שלה מפוצל לשניים
    R = [(4000, 0), (5000, 0), (5000, 500), (4500, 500), (4000, 500)]
    for i in range(len(R)):
        _line(m, R[i], R[(i+1) % len(R)], 3)
    d.saveas(path)

def main():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "t.dxf"); build(p)
        pieces, mitre, warns = PR.read_prodim(p, with_warnings=True)
    assert len(pieces) == 2, pieces
    big = max(pieces, key=lambda x: x["len"]); rect = min(pieces, key=lambda x: x["len"])
    assert (big["len"], big["depth"]) == (300.0, 180.0)
    assert len(big["outline"]) == 6 and not big["is_rect"]
    kinds = sorted(o["kind"] for o in big["openings"])
    assert kinds == ["חשמל", "כיור", "כיור"], kinds
    u = next(o for o in big["openings"] if o["kind"] == "כיור" and o["w"] == 40.0)
    assert (u["from_left_cm"], u["from_front_cm"], u["h"]) == (180.0, 35.0, 40.0)
    assert any("שלוש צלעות" in w for w in warns), warns
    sink = next(o for o in big["openings"] if o["kind"] == "כיור" and o["w"] == 80.0)
    assert (sink["from_left_cm"], sink["from_front_cm"], sink["fromFront"], sink["w"], sink["h"]) == (100.0, 30.0, 10.0, 80.0, 40.0)
    assert rect["is_rect"] and len(rect["outline"]) == 4 and (rect["len"], rect["depth"]) == (100.0, 50.0)
    assert any("קו לא סגור" in w for w in warns), warns
    # קובץ המכונה: פוליליין סגור לכל חתיכה ולכל פתח, הכיור במקומו
    txt, _ = DE.gen_dxf([dict(x) for x in pieces], DE.MATERIALS["synthetic"])
    doc = ezdxf.read(io.StringIO(txt))
    pls = [e for e in doc.modelspace() if e.dxftype() == "POLYLINE"]
    assert len(pls) == 5 and all(e.is_closed for e in pls)
    assert {e.dxf.layer for e in pls} == {"1000-21_5"}
    print("ok")

if __name__ == "__main__":
    main()
