# -*- coding: utf-8 -*-
"""קורא קובץ Prodim/פרוליינר: מזהה חתיכות (ירוק=עיבוד) + פתחים לפי צבע,
ומייצר תוכנית חיתוך יפה (בסגנון המחולל של הן) עם כל הפרטים."""
import ezdxf, math
from reportlab.pdfgen import canvas
import gen_lib as G
from gen_lib import (PAGE, PAGE_W, PAGE_H, C_BG, C_LINE, C_MUTED, C_NEUTRAL, C_ACCENT,
                     C_FRONT, C_GAS_F, C_GAS_S, C_SINK_F, C_SINK_S, PIECE_COLORS,
                     draw_header, draw_notes, heb, FONT_NAME, FONT_BOLD, fe_h)
from reportlab.lib.colors import HexColor, white

# ACI צבע -> משמעות (מקרא Prodim של הן)
CUT = 3           # ירוק = עיבוד (מתאר החתיכה)
SEM = {5: ("כיור", C_SINK_F, C_SINK_S), 6: ("כיריים", HexColor("#FCE7F3"), HexColor("#DB2777")),
       4: ("שקע", HexColor("#CFFAFE"), HexColor("#0891B2"))}
MITRE = 30        # כתום = גרונג (נזהה לפי טווח)
IGNORE = {7, 1}   # שחור=קיר, אדום=ארון — עיון בלבד

def _eff_color(e, layer_color):
    c = e.dxf.color
    if c == 256:
        c = layer_color.get(e.dxf.layer, 7)
    return c

def _segments(msp, layer_color, color):
    segs = []
    for e in msp:
        if _eff_color(e, layer_color) != color:
            continue
        if e.dxftype() == "LINE":
            segs.append(((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)))
        elif e.dxftype() == "ARC":
            a0 = math.radians(e.dxf.start_angle); a1 = math.radians(e.dxf.end_angle)
            c0 = (e.dxf.center.x + e.dxf.radius*math.cos(a0), e.dxf.center.y + e.dxf.radius*math.sin(a0))
            c1 = (e.dxf.center.x + e.dxf.radius*math.cos(a1), e.dxf.center.y + e.dxf.radius*math.sin(a1))
            segs.append((c0, c1))
    return segs

def _components(segs, tol=0.8):
    nodes = []; idx = {}
    def nid(p):
        k = (round(p[0]/tol), round(p[1]/tol))
        if k not in idx:
            idx[k] = len(nodes); nodes.append(p)
        return idx[k]
    parent = list(range(0))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    edges = []
    for a, b in segs:
        ia, ib = nid(a), nid(b)
        while len(parent) < len(nodes):
            parent.append(len(parent))
        edges.append((ia, ib))
    while len(parent) < len(nodes):
        parent.append(len(parent))
    for ia, ib in edges:
        parent[find(ia)] = find(ib)
    comp = {}
    for i in range(len(nodes)):
        r = find(i); comp.setdefault(r, []).append(nodes[i])
    return list(comp.values())

def read_prodim(path_or_stream, min_cm=12):
    d = ezdxf.readfile(path_or_stream)
    msp = list(d.modelspace())
    layer_color = {l.dxf.name: l.dxf.color for l in d.layers}
    # חתיכות = רכיבים ירוקים
    green = _segments(msp, layer_color, CUT)
    pieces = []
    for arr in _components(green):
        if len(arr) < 3:
            continue
        xs = [p[0] for p in arr]; ys = [p[1] for p in arr]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        w = (x1-x0)/10; h = (y1-y0)/10
        if w < min_cm or h < min_cm:
            continue
        pieces.append({"len": round(w,1), "depth": round(h,1),
                       "bbox": (x0, y0, x1, y1), "openings": []})
    # פתחים לפי צבע -> משויכים לחתיכה שמכילה אותם
    for aci, (name, fF, sF) in SEM.items():
        for arr in _components(_segments(msp, layer_color, aci)):
            if len(arr) < 3:
                continue
            xs = [p[0] for p in arr]; ys = [p[1] for p in arr]
            ox0, oy0, ox1, oy1 = min(xs), min(ys), max(xs), max(ys)
            ocx, ocy = (ox0+ox1)/2, (oy0+oy1)/2
            for pc in pieces:
                bx0, by0, bx1, by1 = pc["bbox"]
                if bx0 <= ocx <= bx1 and by0 <= ocy <= by1:
                    pc["openings"].append({
                        "kind": name,
                        "from_left_cm": round((ocx-bx0)/10, 1),
                        "from_front_cm": round((ocy-by0)/10, 1),
                        "w": round((ox1-ox0)/10, 1), "h": round((oy1-oy0)/10, 1)})
                    break
    # גרונג (כתום ~30) קיים? סימון כללי
    has_mitre = any(_eff_color(e, layer_color) in (30, 8) for e in msp)
    return pieces, has_mitre

# ------- תוכנית חיתוך יפה ל-Prodim -------
def _draw_piece(c, x, y, w_cm, h_cm, scale, color, num, piece):
    W = w_cm*scale; Hh = h_cm*scale
    c.setFillColor(color); c.setStrokeColor(C_LINE); c.setLineWidth(1.2)
    c.saveState(); c.setFillAlpha(0.20); c.rect(x, y, W, Hh, fill=1, stroke=0); c.restoreState()
    c.rect(x, y, W, Hh, fill=0, stroke=1)
    # מידות
    G.hdim(c, x, y+Hh+10, x+W, f"{w_cm:g}", fs=9)
    G.vdim(c, x-10, y, y+Hh, f"{h_cm:g}", fs=9)
    # מספר
    c.setFillColor(white); c.circle(x+13, y+Hh-13, 9, fill=1, stroke=0)
    c.setFillColor(color); c.setFont(FONT_BOLD, 11); c.drawCentredString(x+13, y+Hh-17, str(num))
    # עיבוד חזית (אם מסומן)
    fe = piece.get("fe_cm")
    if fe:
        fx1 = x + float(piece.get("fe_from_cm", 0)) * scale
        fx2 = min(fx1 + float(fe) * scale, x + W)
        fe_h(c, fx1, fx2, y, f"{float(fe):g}", below=True)
    # פתחים
    for op in piece["openings"]:
        name = op["kind"]
        fF, sF = (C_SINK_F, C_SINK_S)
        if name == "כיריים": fF, sF = HexColor("#FCE7F3"), HexColor("#DB2777")
        elif name == "שקע": fF, sF = HexColor("#CFFAFE"), HexColor("#0891B2")
        ocx = x + op["from_left_cm"]*scale
        ocy = y + op["from_front_cm"]*scale
        ow = op["w"]*scale; oh = op["h"]*scale
        c.setFillColor(fF); c.setStrokeColor(sF); c.setLineWidth(0.8)
        c.rect(ocx-ow/2, ocy-oh/2, ow, oh, fill=1, stroke=1)
        c.setFillColor(sF); c.setFont(FONT_BOLD, 7)
        c.drawCentredString(ocx, ocy-3, heb(f"{name} {op['w']:g}×{op['h']:g}"))

def render_prodim_plan(pieces, mat, out_path, has_mitre=False, job_name="", title=None):
    from dxf_engine import nest_pieces
    slabs = nest_pieces([dict(p) for p in pieces], mat["slabL"], mat["slabW"])
    c = canvas.Canvas(out_path, pagesize=PAGE)
    def bg(): c.setFillColor(C_BG); c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    total = len(slabs) + 1
    # עמוד 1 — רשימת חתיכות
    bg()
    draw_header(c, (job_name+"  ·  " if job_name else "")+(title or "חתיכות לחיתוך"),
                f"{len(pieces)} חתיכות · {mat['he']} · לוח {mat['slabL']}×{mat['slabW']}", 1, total)
    # פריסת החתיכות בשורות
    x = 60; y = PAGE_H-140; rowh = 0; scale = min(0.9, (PAGE_W-120)/max(p['len'] for p in pieces))
    for i, p in enumerate(pieces):
        W = p['len']*scale; Hh = p['depth']*scale
        if x + W > PAGE_W-50:
            x = 60; y -= (rowh + 55); rowh = 0
        if y - Hh < 120:
            break
        _draw_piece(c, x, y-Hh, p['len'], p['depth'], scale, PIECE_COLORS[i % len(PIECE_COLORS)], i+1, p)
        x += W + 55; rowh = max(rowh, Hh)
    notes = ["כל החתיכות מוכנות לחיתוך.",
             "עיבוד חזית מסומן בקו כתום עם הסימן ‖ ואורך העיבוד.",
             "הפתחים (כיור/כיריים/שקע) מסומנים על כל חתיכה עם המידות."]
    if has_mitre: notes.append("שים לב: יש בקובץ חיתוכי גרונג (46°) — מבוצעים בהטיית הראש.")
    draw_notes(c, notes)
    c.showPage()
    # עמודים — סידור על כל לוח
    CM = 10
    for si, slab in enumerate(slabs):
        bg()
        draw_header(c, f"סידור על לוח {si+1}", f"{mat['he']} · {mat['slabL']}×{mat['slabW']} ס\"מ", si+2, total)
        margin = 60; avail_w = PAGE_W-2*margin; avail_h = PAGE_H-200
        sc = min(avail_w/mat['slabL'], avail_h/mat['slabW'])
        ox = margin; oy = 120
        c.setStrokeColor(C_MUTED); c.setLineWidth(1); c.setDash([5,4])
        c.rect(ox, oy, mat['slabL']*sc, mat['slabW']*sc, fill=0, stroke=1); c.setDash([])
        # שאריות
        for rr in slab["remnants"]:
            c.setFillColor(HexColor("#DFF3E4")); c.saveState(); c.setFillAlpha(0.6)
            c.rect(ox+rr['x']*sc, oy+rr['y']*sc, rr['w']*sc, rr['h']*sc, fill=1, stroke=0); c.restoreState()
            c.setFillColor(HexColor("#2F855A")); c.setFont(FONT_NAME, 7)
            c.drawCentredString(ox+(rr['x']+rr['w']/2)*sc, oy+(rr['y']+rr['h']/2)*sc, heb(f"שארית {rr['w']:g}×{rr['h']:g}"))
        # חתיכות
        idx = 0
        for shelf_ in slab["rows"]:
            for it in shelf_["items"]:
                pc = it["pc"]; X = ox+it["x"]*sc; Y = oy+it["y"]*sc; W = pc["len"]*sc; Hh = pc["depth"]*sc
                col = PIECE_COLORS[idx % len(PIECE_COLORS)]; idx += 1
                c.setFillColor(col); c.saveState(); c.setFillAlpha(0.20); c.rect(X, Y, W, Hh, fill=1, stroke=0); c.restoreState()
                c.setStrokeColor(col); c.setLineWidth(1.5); c.rect(X, Y, W, Hh, fill=0, stroke=1)
                c.setFillColor(C_LINE); c.setFont(FONT_BOLD, 8)
                c.drawCentredString(X+W/2, Y+Hh/2-3, f"{pc['len']:g}×{pc['depth']:g}")
        c.showPage()
    c.save()
    return out_path, len(slabs)
