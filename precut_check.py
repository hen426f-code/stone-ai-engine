# -*- coding: utf-8 -*-
"""בודק לפני חיתוך: "לא חותכים טעות".
בודק את החתיכות ואת הסידור על הלוחות לפני שה-DXF יוצא למכונה, ומחשב ניצול לוחות.
errors = דברים שבוודאות ייצאו לא נכון אם חותכים. warnings = לבדיקה, אפשר להתעלם."""

EPS = 0.05          # ס"מ
MIN_RIM_CM = 5      # פס חומר צר מזה בין פתח לשפה נוטה להישבר


def _poly_area(pts):
    a = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def _inside(pt, poly):
    x, y = pt
    inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _opening_rect(op, depth):
    """מלבן הפתח בס"מ ביחס לפינה השמאלית-קדמית של החתיכה, כמו שה-DXF מצייר אותו."""
    cx = op["from_left_cm"]
    cy = op["fromFront"] + op["h"] / 2 if op.get("fromFront") is not None else depth / 2
    return (cx - op["w"] / 2, cy - op["h"] / 2, cx + op["w"] / 2, cy + op["h"] / 2)


def _name(p, i):
    lab = p.get("label") or "חתיכה"
    return "%s %d (%g×%g)" % (lab, i + 1, p["len"], p["depth"])


def piece_area_cm2(p):
    if p.get("outline_pts"):
        return _poly_area([(x / 10, y / 10) for x, y in p["outline_pts"]])
    return p["len"] * p["depth"]


def check(pieces, slabs, mat):
    errors, warnings = [], []
    sL, sW = mat["slabL"], mat["slabW"]

    for i, p in enumerate(pieces):
        nm = _name(p, i)
        a, b = sorted((p["len"], p["depth"]))
        if b > sL + EPS or a > sW + EPS:
            errors.append("%s גדולה מהלוח %g×%g. צריך לפצל לפני חיתוך." % (nm, sL, sW))
        if p.get("dropped_openings"):
            warnings.append("%s: %d פתחים בלי רוחב או עומק לא ייחתכו. להשלים מידה אם צריך אותם."
                            % (nm, p["dropped_openings"]))
        for k in p.get("mitre_segs") or []:
            if p.get("outline") and k < len(p["outline"]) and p["outline"][k][2]:
                errors.append("%s: צלע גרונג על קשת. אי אפשר לחתוך קשת בהטיית ראש, צריך לבדוק עם המודד." % nm)
                break
        poly = [(x / 10, y / 10) for x, y in p["outline_pts"]] if p.get("outline_pts") else None
        rects = []
        for j, op in enumerate(p.get("openings") or []):
            if not op.get("w") or not op.get("h"):
                continue
            on = "%s ב%s" % (op.get("kind") or "פתח", nm)
            x0, y0, x1, y1 = r = _opening_rect(op, p["depth"])
            rects.append((on, r))
            if x0 < -EPS or y0 < -EPS or x1 > p["len"] + EPS or y1 > p["depth"] + EPS:
                errors.append("%s יוצא מחוץ לחתיכה. לבדוק את המידות והמיקום של הפתח." % on)
                continue
            if poly and not all(_inside(c, poly) for c in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))):
                errors.append("%s יוצא מחוץ לקו המתאר של החתיכה." % on)
                continue
            rim = min(x0, y0, p["len"] - x1, p["depth"] - y1)
            # שקע חשמל קטן ליד שפת ציפוי זה מצב רגיל, הבדיקה רק לכיור, כיריים ופתחים גדולים
            if rim < MIN_RIM_CM - EPS and "חשמל" not in (op.get("kind") or ""):
                warnings.append("%s: נשאר רק %g ס״מ חומר בין הפתח לשפה. פס צר כזה נוטה להישבר."
                                % (on, round(rim, 1)))
        for k in range(len(rects)):
            for m in range(k + 1, len(rects)):
                (n1, a1), (n2, a2) = rects[k], rects[m]
                if a1[0] < a2[2] - EPS and a2[0] < a1[2] - EPS and a1[1] < a2[3] - EPS and a2[1] < a1[3] - EPS:
                    errors.append("%s ו%s חופפים." % (n1, n2))

    # הסידור על הלוחות: כל חתיכה בתוך הלוח ושום שתי חתיכות לא חופפות
    stats = []
    for si, sl in enumerate(slabs):
        items = [it for sh in sl["rows"] for it in sh["items"]]
        for it in items:
            pc = it["pc"]
            a, b = sorted((pc["len"], pc["depth"]))
            if b > sL + EPS or a > sW + EPS:
                continue  # כבר דווח כחתיכה גדולה מהלוח
            if it["x"] + pc["len"] > sL + EPS or it["y"] + pc["depth"] > sW + EPS:
                msg = "לוח %d: חתיכה %g×%g חורגת משטח הלוח." % (si + 1, pc["len"], pc["depth"])
                if msg not in errors:
                    errors.append(msg)
        for k in range(len(items)):
            for m in range(k + 1, len(items)):
                A, B = items[k], items[m]
                if (A["x"] < B["x"] + B["pc"]["len"] - EPS and B["x"] < A["x"] + A["pc"]["len"] - EPS and
                        A["y"] < B["y"] + B["pc"]["depth"] - EPS and B["y"] < A["y"] + A["pc"]["depth"] - EPS):
                    errors.append("לוח %d: שתי חתיכות חופפות בסידור." % (si + 1))
        used = sum(piece_area_cm2(it["pc"]) for it in items)
        stats.append({"slab": si + 1, "pieces": len(items),
                      "used_pct": round(100 * used / (sL * sW), 1)})

    total_used = sum(piece_area_cm2(p) for p in pieces)
    total_slab = sL * sW * len(slabs)
    summary = {"slabs": len(slabs),
               "pieces_m2": round(total_used / 1e4, 2),
               "slabs_m2": round(total_slab / 1e4, 2),
               "waste_m2": round((total_slab - total_used) / 1e4, 2),
               "used_pct": round(100 * total_used / total_slab, 1) if total_slab else 0,
               "per_slab": stats}
    return {"ok": not errors, "errors": errors, "warnings": warnings, "usage": summary}
