# -*- coding: utf-8 -*-
"""מנוע DXF למכונת GMM — נכתב עם ezdxf לתאימות מלאה (R12 תקני שלם).
פוליליין סגור לכל חתיכה/פתח, שכבה 1000-<מ"מ>, צבע=עדיפות (מעטפת קודם, פתחים אחרונים),
סידור דו-ממדי עם סיבוב אוטומטי."""
import ezdxf

KERF = 0.6
PRIO_ACI = [1, 2, 3, 4, 5, 6, 8, 9, 9, 9]  # avoid 7 (white/black bg issues)
OPENING_ACI = 9

MATERIALS = {
    "porcelan":  {"he": "פורצלן",  "depth": 12, "slabL": 320, "slabW": 160},
    "dekton":    {"he": "דקטון",   "depth": 12, "slabL": 330, "slabW": 150},
    "synthetic": {"he": "סינטטי",  "depth": 20, "slabL": 303, "slabW": 140},
}

def nest_pieces(pieces, slabL, slabW):
    oriented = []
    for p in pieces:
        ln, dp = p["len"], p["depth"]
        if dp > slabW and ln <= slabW:
            ln, dp = dp, ln
        oriented.append({**p, "len": ln, "depth": dp})
    order = sorted(enumerate(oriented), key=lambda t: (-t[1]["depth"], -t[1]["len"]))
    slabs = []; cur = {"rows": [], "usedH": 0.0}; shelf = {"ref": None}
    def new_slab():
        nonlocal cur
        if cur["rows"]: slabs.append(cur)
        cur = {"rows": [], "usedH": 0.0}
    def new_shelf(h):
        if cur["usedH"] + (KERF if cur["rows"] else 0) + h > slabW:
            new_slab()
        y = cur["usedH"] + (KERF if cur["rows"] else 0)
        s = {"y": y, "h": h, "used": 0.0, "items": []}
        cur["rows"].append(s); cur["usedH"] = y + h; shelf["ref"] = s
    for _, pc in order:
        s = shelf["ref"]
        if (s is None or s["used"] + (KERF if s["items"] else 0) + pc["len"] > slabL or pc["depth"] > s["h"]):
            placed = False
            for ss in cur["rows"]:
                if pc["depth"] <= ss["h"] and ss["used"] + (KERF if ss["items"] else 0) + pc["len"] <= slabL:
                    x = ss["used"] + (KERF if ss["items"] else 0)
                    ss["items"].append({"pc": pc, "x": x, "y": ss["y"]}); ss["used"] = x + pc["len"]; placed = True; break
            if placed: continue
            new_shelf(pc["depth"]); s = shelf["ref"]
        x = s["used"] + (KERF if s["items"] else 0)
        s["items"].append({"pc": pc, "x": x, "y": s["y"]}); s["used"] = x + pc["len"]
    if cur["rows"]: slabs.append(cur)
    MINREM = 5
    for s in slabs:
        s["remnants"] = []
        for sh in s["rows"]:
            leftLen = round((slabL - sh["used"]) * 10) / 10
            if leftLen >= MINREM and sh["h"] >= MINREM:
                s["remnants"].append({"x": sh["used"], "y": sh["y"], "w": leftLen, "h": round(sh["h"]*10)/10})
        bottomH = round((slabW - s["usedH"]) * 10) / 10
        if bottomH >= MINREM:
            s["remnants"].append({"x": 0, "y": s["usedH"], "w": slabL, "h": bottomH})
    return slabs

def gen_dxf(pieces, mat):
    cutDepth = mat["depth"] + 1.5  # ירידת Z תמיד עובי+1.5 (המסור נכנס מעט לשטיח הגומי לחיתוך מלא)
    slabs = nest_pieces(pieces, mat["slabL"], mat["slabW"])
    CM = 10
    layer = "1000-" + str(cutDepth).replace(".", "_")
    doc = ezdxf.new("R12")
    if layer not in doc.layers:
        doc.layers.add(layer, color=7)
    msp = doc.modelspace()
    def rect(x, y, w, h, aci):
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        pl = msp.add_polyline2d(pts, dxfattribs={"layer": layer, "color": aci})
        pl.close(True)
    prio = 0; slabBase = 0.0
    for slab in slabs:
        for sh in slab["rows"]:
            for it in sh["items"]:
                pc = it["pc"]; px = it["x"]*CM; py = (slabBase+it["y"])*CM
                pw = pc["len"]*CM; ph = pc["depth"]*CM
                rect(px, py, pw, ph, PRIO_ACI[min(prio, len(PRIO_ACI)-1)]); prio += 1
                for op in pc.get("openings", []):
                    if op.get("w") and op.get("h"):
                        ow = op["w"]*CM; oh = op["h"]*CM
                        cx = px + op["from_left_cm"]*CM
                        cy = (py + op["fromFront"]*CM + oh/2) if op.get("fromFront") is not None else (py + ph/2)
                        rect(cx-ow/2, cy-oh/2, ow, oh, OPENING_ACI)
        slabBase += mat["slabW"] + 15
    import io
    s = io.StringIO(); doc.write(s)
    return s.getvalue(), slabs

if __name__ == "__main__":
    d, slabs = gen_dxf([{"len": 301, "depth": 64, "openings": [{"from_left_cm": 150, "w": 78, "h": 50, "fromFront": 8}]},
                        {"len": 154, "depth": 64, "openings": []}], MATERIALS["porcelan"])
    open("/home/claude/outputs/engine_test.dxf", "w").write(d)
    print("ok, slabs:", len(slabs), "len:", len(d))
