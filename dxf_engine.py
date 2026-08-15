# -*- coding: utf-8 -*-
"""מנוע DXF למכונת GMM — פורמט מאומת: R12, פוליליין סגור לכל חתיכה/פתח,
שכבה 1000-<מ"מ>, צבע=עדיפות (מעטפת קודם, פתחים אחרונים), סידור דו-ממדי עם סיבוב."""

KERF = 0.6
PRIO_ACI = [1, 2, 3, 4, 5, 6, 7, 8, 9, 9]
OPENING_ACI = 9

MATERIALS = {
    "porcelan":  {"he": "פורצלן",  "depth": 12, "slabL": 320, "slabW": 160},
    "dekton":    {"he": "דקטון",   "depth": 12, "slabL": 330, "slabW": 150},
    "synthetic": {"he": "סינטטי",  "depth": 20, "slabL": 303, "slabW": 140},
}

def nest_pieces(pieces, slabL, slabW):
    """סידור מדפים בגובה משתנה + סיבוב אוטומטי אם חתיכה עמוקה מרוחב הלוח."""
    oriented = []
    for p in pieces:
        ln, dp = p["len"], p["depth"]
        if dp > slabW and ln <= slabW:
            ln, dp = dp, ln
        oriented.append({**p, "len": ln, "depth": dp})
    order = sorted(enumerate(oriented), key=lambda t: (-t[1]["depth"], -t[1]["len"]))
    slabs = []
    cur = {"rows": [], "usedH": 0.0}
    def new_slab():
        nonlocal cur
        if cur["rows"]:
            slabs.append(cur)
        cur = {"rows": [], "usedH": 0.0}
    shelf = {"ref": None}
    def new_shelf(h):
        if cur["usedH"] + (KERF if cur["rows"] else 0) + h > slabW:
            new_slab()
        y = cur["usedH"] + (KERF if cur["rows"] else 0)
        s = {"y": y, "h": h, "used": 0.0, "items": []}
        cur["rows"].append(s); cur["usedH"] = y + h
        shelf["ref"] = s
    for _, pc in order:
        s = shelf["ref"]
        if (s is None or s["used"] + (KERF if s["items"] else 0) + pc["len"] > slabL
                or pc["depth"] > s["h"]):
            placed = False
            for ss in cur["rows"]:
                if pc["depth"] <= ss["h"] and ss["used"] + (KERF if ss["items"] else 0) + pc["len"] <= slabL:
                    x = ss["used"] + (KERF if ss["items"] else 0)
                    ss["items"].append({"pc": pc, "x": x, "y": ss["y"]}); ss["used"] = x + pc["len"]
                    placed = True; break
            if placed:
                continue
            new_shelf(pc["depth"]); s = shelf["ref"]
        x = s["used"] + (KERF if s["items"] else 0)
        s["items"].append({"pc": pc, "x": x, "y": s["y"]}); s["used"] = x + pc["len"]
    if cur["rows"]:
        slabs.append(cur)
    MINREM = 5
    for s in slabs:
        s["remnants"] = []
        for shelf_ in s["rows"]:
            leftLen = round((slabL - shelf_["used"]) * 10) / 10
            if leftLen >= MINREM and shelf_["h"] >= MINREM:
                s["remnants"].append({"x": shelf_["used"], "y": shelf_["y"], "w": leftLen, "h": round(shelf_["h"] * 10) / 10})
        bottomH = round((slabW - s["usedH"]) * 10) / 10
        if bottomH >= MINREM:
            s["remnants"].append({"x": 0, "y": s["usedH"], "w": slabL, "h": bottomH})
    return slabs

def gen_dxf(pieces, mat):
    """pieces: [{len, depth, openings:[{from_left_cm,w,h,fromFront?}]}]. mat: MATERIALS entry."""
    cutDepth = mat["depth"]
    slabs = nest_pieces(pieces, mat["slabL"], mat["slabW"])
    CM = 10
    layer = "1000-" + str(cutDepth).replace(".", "_")
    handle = [0x100]
    def H():
        handle[0] += 1
        return format(handle[0], "X")
    ents = []
    def poly(pts, aci):
        s = "0\nPOLYLINE\n5\n%s\n8\n%s\n6\nCONTINUOUS\n62\n%d\n66\n1\n10\n0.0\n20\n0.0\n30\n0.0\n70\n1\n" % (H(), layer, aci)
        for (x, y) in pts:
            s += "0\nVERTEX\n5\n%s\n8\n%s\n6\nCONTINUOUS\n10\n%s\n20\n%s\n30\n0.0\n70\n0\n" % (H(), layer, x, y)
        s += "0\nSEQEND\n5\n%s\n8\n%s\n" % (H(), layer)
        ents.append(s)
    prio = 0; slabBase = 0.0
    for si, slab in enumerate(slabs):
        for shelf_ in slab["rows"]:
            for it in shelf_["items"]:
                pc = it["pc"]; x = it["x"]; y = it["y"]
                px = x * CM; py = (slabBase + y) * CM; pw = pc["len"] * CM; ph = pc["depth"] * CM
                envP = min(prio, 7); prio += 1
                poly([(px, py), (px + pw, py), (px + pw, py + ph), (px, py + ph)], PRIO_ACI[envP])
                for op in pc.get("openings", []):
                    if op.get("w") and op.get("h"):
                        ow = op["w"] * CM; oh = op["h"] * CM
                        cx = px + op["from_left_cm"] * CM
                        cy = (py + op["fromFront"] * CM + oh / 2) if op.get("fromFront") is not None else (py + ph / 2)
                        poly([(cx - ow / 2, cy - oh / 2), (cx + ow / 2, cy - oh / 2),
                              (cx + ow / 2, cy + oh / 2), (cx - ow / 2, cy + oh / 2)], OPENING_ACI)
        slabBase += mat["slabW"] + 15
    header = "0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1009\n9\n$INSUNITS\n70\n4\n0\nENDSEC\n"
    tables = ("0\nSECTION\n2\nTABLES\n0\nTABLE\n2\nLTYPE\n70\n1\n0\nLTYPE\n2\nCONTINUOUS\n70\n0\n3\nSolid line\n72\n65\n73\n0\n40\n0.0\n0\nENDTAB\n"
              "0\nTABLE\n2\nLAYER\n70\n1\n0\nLAYER\n2\n%s\n70\n0\n62\n7\n6\nCONTINUOUS\n0\nENDTAB\n0\nENDSEC\n" % layer)
    body = "0\nSECTION\n2\nENTITIES\n" + "".join(ents) + "0\nENDSEC\n0\nEOF\n"
    return header + tables + body, slabs

if __name__ == "__main__":
    d, slabs = gen_dxf([{"len": 301, "depth": 64, "openings": [{"from_left_cm": 150, "w": 78, "h": 50, "fromFront": 8}]},
                        {"len": 154, "depth": 64, "openings": []},
                        {"len": 68, "depth": 64, "openings": []}], MATERIALS["porcelan"])
    open("/home/claude/outputs/engine_test.dxf", "w").write(d)
    print("slabs:", len(slabs), "remnants:", [s["remnants"] for s in slabs])
