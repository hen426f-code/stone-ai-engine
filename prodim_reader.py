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

# ACI צבע -> משמעות (מקרא Prodim של הן). הצבע מתאר את סוג הצלע, לא אם היא שייכת לחתיכה:
# מתאר חתיכה בנוי מצלעות בכמה צבעים (ירוק=עיבוד, שחור=קיר וכו').
CUT = 3           # ירוק = עיבוד
EDGE_KIND = {3: "עיבוד", 7: "קיר", 1: "ארון", 5: "כיור", 6: "כיריים", 4: "שקע", 30: "גרונג"}
SEM = {5: ("כיור", C_SINK_F, C_SINK_S), 6: ("כיריים", HexColor("#FCE7F3"), HexColor("#DB2777")),
       4: ("שקע", HexColor("#CFFAFE"), HexColor("#0891B2"))}
MITRE = 30        # כתום = גרונג
SNAP_MM = 2.0     # מרחק חיבור בין קצוות קווים
ARC_STEP = math.radians(5)

def _eff_color(e, layer_color):
    c = e.dxf.color
    if c in (0, 256):
        c = layer_color.get(e.dxf.layer, 7)
    return abs(c)

def _arc_edge(cx, cy, r, a0, a1, color):
    """קשת נגד כיוון השעון מ-a0 ל-a1 (מעלות) -> צלע עם נקודות צפופות ו-bulge"""
    s = math.radians(a0); sweep = math.radians((a1 - a0) % 360 or 360)
    n = max(2, int(math.ceil(sweep / ARC_STEP)) + 1)
    pts = [(cx + r*math.cos(s + sweep*i/(n-1)), cy + r*math.sin(s + sweep*i/(n-1))) for i in range(n)]
    return {"pts": pts, "bulge": math.tan(sweep/4), "color": color}

def _edges(msp, layer_color):
    """כל הישויות הגיאומטריות -> צלעות פתוחות + לולאות סגורות מוכנות (עיגולים)"""
    edges, circles = [], []
    def add(e, color):
        t = e.dxftype()
        if t == "LINE":
            a = (e.dxf.start.x, e.dxf.start.y); b = (e.dxf.end.x, e.dxf.end.y)
            if math.dist(a, b) > 1e-6:
                edges.append({"pts": [a, b], "bulge": 0.0, "color": color})
        elif t == "ARC":
            edges.append(_arc_edge(e.dxf.center.x, e.dxf.center.y, e.dxf.radius,
                                   e.dxf.start_angle, e.dxf.end_angle, color))
        elif t == "CIRCLE":
            circles.append({"center": (e.dxf.center.x, e.dxf.center.y), "r": e.dxf.radius, "color": color})
        elif t in ("LWPOLYLINE", "POLYLINE"):
            for v in e.virtual_entities():
                add(v, color)
        elif t in ("SPLINE", "ELLIPSE"):
            pts = [(p.x, p.y) for p in e.flattening(0.5)]
            if len(pts) >= 2:
                edges.append({"pts": pts, "bulge": None, "color": color})
    for e in msp:
        add(e, _eff_color(e, layer_color))
    return edges, circles

def _snap(edges):
    nodes = []
    def nid(p):
        for i, q in enumerate(nodes):
            if abs(p[0]-q[0]) <= SNAP_MM and abs(p[1]-q[1]) <= SNAP_MM:
                return i
        nodes.append(p); return len(nodes) - 1
    for ed in edges:
        ed["a"] = nid(ed["pts"][0]); ed["b"] = nid(ed["pts"][-1])
    return nodes

def _walk(comp_edges, edges):
    """לולאה סגורה -> רשימת קודקודים (x, y, bulge) ונקודות צפופות, לפי סדר ההליכה"""
    first = edges[comp_edges[0]]
    used = {comp_edges[0]}; verts = []; dense = []
    cur_edge, node = first, first["b"]
    def push(ed, forward):
        # כל קודקוד: (x, y, bulge, צבע הקטע שמתחיל בו), כדי לדעת איזו צלע היא גרונג
        pts = ed["pts"] if forward else ed["pts"][::-1]
        b, c = ed["bulge"], ed["color"]
        if b is None:      # עקומה כללית: נכנסת כרצף קטעים ישרים
            for p in pts[:-1]:
                verts.append((p[0], p[1], 0.0, c))
        else:
            verts.append((pts[0][0], pts[0][1], b if forward else -b, c))
        dense.extend(pts[:-1])
    push(first, True)
    while True:
        nxt = [i for i in comp_edges if i not in used and node in (edges[i]["a"], edges[i]["b"])]
        if not nxt:
            break
        i = nxt[0]; used.add(i); ed = edges[i]
        fwd = ed["a"] == node
        push(ed, fwd)
        node = ed["b"] if fwd else ed["a"]
    return verts, dense

def _drop_collinear(verts, tol_mm=0.5):
    """מסיר קודקודים שיושבים על קו ישר בין שכניהם (קו שהמודד פיצל לשניים)"""
    out = list(verts); changed = True
    while changed and len(out) > 3:
        changed = False
        for k in range(len(out)):
            a, b, c = out[k-1], out[k], out[(k+1) % len(out)]
            # לא מאחדים צלע גרונג עם צלע רגילה, כדי לא לאבד איזה קטע נחתך בזווית
            if a[2] or b[2] or (a[3] != b[3] and (a[3] in (MITRE, 8) or b[3] in (MITRE, 8))):
                continue
            L = math.dist(a[:2], c[:2])
            if L and abs((c[0]-a[0])*(a[1]-b[1]) - (a[0]-b[0])*(c[1]-a[1])) / L < tol_mm:
                out.pop(k); changed = True; break
    return out

def _close_u(comp, edges, deg):
    """פתח של שלוש צלעות (המודד לא מדד את הצלע הרביעית כי היא זהה למקבילה שלה):
    מחזיר את ארבע הפינות אם הצלע החסרה מקבילה לבסיס ובאותו אורך, אחרת None"""
    if len(comp) < 3 or any(edges[j]["bulge"] != 0 or len(edges[j]["pts"]) != 2 for j in comp):
        return None
    ends = [n for n, v in deg.items() if v == 1]
    if len(ends) != 2 or any(v > 2 for v in deg.values()):
        return None
    node, left, chain = ends[0], set(comp), []
    while left:
        j = next((j for j in left if node in (edges[j]["a"], edges[j]["b"])), None)
        if j is None:
            return None
        left.discard(j); ed = edges[j]
        fwd = ed["a"] == node
        chain.append(ed["pts"][0] if fwd else ed["pts"][1])
        node = ed["b"] if fwd else ed["a"]
        if not left:
            chain.append(ed["pts"][1] if fwd else ed["pts"][0])
    k = 1                                   # צלע שהמודד פיצל לשני קטעים ישרים = צלע אחת
    while k < len(chain) - 1:
        a, b, c = chain[k-1], chain[k], chain[k+1]
        L = math.dist(a, c)
        if L and abs((c[0]-a[0])*(a[1]-b[1]) - (a[0]-b[0])*(c[1]-a[1])) / L < 2.0:
            chain.pop(k)
        else:
            k += 1
    if len(chain) != 4:
        return None
    p0, p1, p2, p3 = chain
    bx, by = p2[0]-p1[0], p2[1]-p1[1]; cx, cy = p0[0]-p3[0], p0[1]-p3[1]
    lb, lc = math.hypot(bx, by), math.hypot(cx, cy)
    if lb < 1 or lc < 1:
        return None
    cos = (bx*cx + by*cy) / (lb*lc)          # צלע הסגירה הולכת בכיוון ההפוך לבסיס
    if cos > -math.cos(math.radians(2)) or abs(lb - lc) > max(5.0, 0.02*lb):
        return None
    return [p0, p1, p2, p3]

def _area(pts):
    return 0.5 * sum(pts[i][0]*pts[i-1][1] - pts[i-1][0]*pts[i][1] for i in range(len(pts)))

def _inside(p, poly):
    x, y = p; ins = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i-1], poly[i]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            ins = not ins
    return ins

def _contains(outer, inner):
    pts = inner["dense"]
    return sum(_inside(p, outer["dense"]) for p in pts) >= 0.9 * len(pts)

def _bbox(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)

def _majority_color(lengths):
    return max(lengths.items(), key=lambda kv: kv[1])[0] if lengths else 7

def read_prodim(path_or_stream, min_cm=12, with_warnings=False):
    """חתיכה = לולאה סגורה (בכל צבע) שאינה בתוך לולאה אחרת. לולאה בתוך חתיכה = פתח.
    צורות לא סגורות לא נחתכות ומדווחות כאזהרה, כי אסור לנחש."""
    d = ezdxf.readfile(path_or_stream)
    msp = list(d.modelspace())
    layer_color = {l.dxf.name: l.dxf.color for l in d.layers}
    edges, circles = _edges(msp, layer_color)
    _snap(edges)
    warnings = []

    # רכיבים קשירים
    adj = {}
    for i, ed in enumerate(edges):
        adj.setdefault(ed["a"], []).append(i); adj.setdefault(ed["b"], []).append(i)
    seen = set(); loops = []; open_parts = []
    for i in range(len(edges)):
        if i in seen:
            continue
        stack = [i]; comp = []
        while stack:
            j = stack.pop()
            if j in seen:
                continue
            seen.add(j); comp.append(j)
            for n in (edges[j]["a"], edges[j]["b"]):
                stack.extend(adj[n])
        lengths = {}
        for j in comp:
            p = edges[j]["pts"]
            L = sum(math.dist(p[k], p[k+1]) for k in range(len(p)-1))
            lengths[edges[j]["color"]] = lengths.get(edges[j]["color"], 0) + L
        deg = {}
        for j in comp:
            for n in (edges[j]["a"], edges[j]["b"]):
                deg[n] = deg.get(n, 0) + 1
        closed = all(v == 2 for v in deg.values()) and (len(comp) >= 3 or
                 (len(comp) == 2 and any(edges[j]["bulge"] for j in comp)))
        if closed:
            verts, dense = _walk(comp, edges)
            if len(dense) >= 3 and abs(_area(dense)) > 1:
                loops.append({"verts": verts, "dense": dense, "lengths": lengths,
                              "color": _majority_color(lengths), "kind": "loop"})
                continue
        u = _close_u(comp, edges, deg)
        if u:
            loops.append({"verts": [(x, y, 0.0, _majority_color(lengths)) for x, y in u], "dense": u, "lengths": lengths,
                          "color": _majority_color(lengths), "kind": "loop", "completed": True})
            continue
        pts = [pt for j in comp for pt in edges[j]["pts"]]
        open_parts.append({"bbox": _bbox(pts), "color": _majority_color(lengths), "mid": pts[len(pts)//2]})
    for c in circles:
        cx, cy = c["center"]; r = c["r"]
        dense = [(cx + r*math.cos(2*math.pi*k/72), cy + r*math.sin(2*math.pi*k/72)) for k in range(72)]
        loops.append({"verts": None, "dense": dense, "lengths": {c["color"]: 2*math.pi*r},
                      "color": c["color"], "kind": "circle", "r": r})

    # היררכיה: מכל לולאה, ההורה הוא הלולאה הקטנה ביותר שמכילה אותה
    for lp in loops:
        lp["absarea"] = abs(_area(lp["dense"]))
    loops.sort(key=lambda l: -l["absarea"])
    for i, lp in enumerate(loops):
        lp["parent"] = None
        for j in range(i-1, -1, -1):
            if _contains(loops[j], lp):
                lp["parent"] = j; break
        lp["depth"] = 0 if lp["parent"] is None else loops[lp["parent"]]["depth"] + 1

    pieces = []; piece_of_loop = {}
    for i, lp in enumerate(loops):
        if lp["depth"] % 2:
            continue
        x0, y0, x1, y1 = _bbox(lp["dense"])
        w = (x1-x0)/10; h = (y1-y0)/10
        if lp.get("completed"):   # השלמת צלע רביעית רק לפתח שבתוך חתיכה
            warnings.append(f"קו לא סגור ({EDGE_KIND.get(lp['color'], 'צבע %d' % lp['color'])}, "
                            f"{w:.1f}×{h:.1f}) מחוץ לחתיכות — לא נחתך. לבדוק.")
            continue
        if lp["depth"]:
            warnings.append(f"צורה סגורה בתוך פתח ({w:.1f}×{h:.1f}) — לא ברור אם זו חתיכה. לבדוק.")
            continue
        if lp["kind"] == "circle" or w < min_cm or h < min_cm:
            warnings.append(f"צורה סגורה קטנה {w:.1f}×{h:.1f} לא נכללה כחתיכה (מינימום {min_cm}). לבדוק.")
            continue
        verts = lp["verts"]
        if _area([(v[0], v[1]) for v in verts]) < 0:     # כיוון אחיד נגד השעון
            rev = verts[::-1]
            # הקשת של הקטע rev[k] -> rev[k+1] נשמרה בקודקוד rev[k+1] (תחילת הקטע בכיוון המקורי)
            verts = [(rev[k][0], rev[k][1], -rev[(k+1) % len(rev)][2], rev[(k+1) % len(rev)][3])
                     for k in range(len(rev))]
        verts = _drop_collinear(verts)
        outline = [(round(vx-x0, 2), round(vy-y0, 2), round(b, 6)) for vx, vy, b, _ in verts]
        mitre_segs = [k for k, v in enumerate(verts) if v[3] in (MITRE, 8)]
        skew_mm = max(min(abs(vx), abs(vx-(x1-x0))) + min(abs(vy), abs(vy-(y1-y0))) for vx, vy, _ in outline)
        is_rect = len(outline) == 4 and not any(b for _, _, b in outline) and skew_mm < 1
        edge_m = {EDGE_KIND.get(c, f"צבע {c}"): round(L/1000, 2) for c, L in lp["lengths"].items()}
        pc = {"len": round(w, 1), "depth": round(h, 1), "bbox": (x0, y0, x1, y1), "openings": [],
              "outline": outline, "outline_pts": [(round(p[0]-x0, 1), round(p[1]-y0, 1)) for p in lp["dense"]],
              "is_rect": is_rect, "edges_m": edge_m}
        if mitre_segs:
            pc["mitre_segs"] = mitre_segs   # אינדקס קטע במתאר (מקודקוד k לקודקוד k+1) שנחתך בזווית
        piece_of_loop[i] = len(pieces); pieces.append(pc)
        n = len(pieces)
        if any(b for _, _, b in outline):
            warnings.append(f"חתיכה {n}: יש בה קשת — המסור לא חותך קשתות, נדרש כרסום. לבדוק.")
        elif len(outline) == 4 and not is_rect:
            warnings.append(f"חתיכה {n}: מלבן לא ישר, סטייה של עד {skew_mm:.0f} מ״מ — נחתכת לפי המדידה.")
        elif not is_rect:
            warnings.append(f"חתיכה {n}: צורה לא מלבנית ({len(outline)} צלעות) — נחתכת לפי המתאר המדויק.")

    for i, lp in enumerate(loops):
        if lp["depth"] % 2 == 0 or loops[lp["parent"]]["depth"] != 0 or lp["parent"] not in piece_of_loop:
            continue
        pi = piece_of_loop[lp["parent"]]; pc = pieces[pi]
        bx0, by0 = pc["bbox"][0], pc["bbox"][1]
        ox0, oy0, ox1, oy1 = _bbox(lp["dense"])
        ow = round((ox1-ox0)/10, 1); oh = round((oy1-oy0)/10, 1)
        ocx, ocy = (ox0+ox1)/2, (oy0+oy1)/2
        if lp["kind"] == "circle":
            warnings.append(f"חתיכה {pi+1}: קידוח בקוטר {2*lp['r']/10:.1f} ס״מ — לא נכלל בקובץ המכונה, לסמן ידנית.")
            continue
        kind = SEM.get(lp["color"], ("פתח",))[0]
        # כלל גודל שגובר על הצבע: פתח קטן = פתח חשמל
        if max(ow, oh) <= 25 and min(ow, oh) <= 15:
            kind = "חשמל"
        if lp.get("completed"):
            warnings.append(f"חתיכה {pi+1}: {kind} {ow:g}×{oh:g} נמדד בשלוש צלעות — הושלמה הצלע הרביעית כמו המקבילה לה.")
        if kind == "פתח":
            warnings.append(f"חתיכה {pi+1}: פתח {ow:g}×{oh:g} בלי צבע של כיור/כיריים/שקע — "
                            f"לוודא שזה פתח ולא חתיכה נפרדת.")
        fl = round((ocx-bx0)/10, 1); ff = round((ocy-by0)/10, 1)
        pc["openings"].append({"kind": kind, "from_left_cm": fl, "from_front_cm": ff,
                               "fromFront": round(ff - oh/2, 1), "w": ow, "h": oh})

    for op_ in open_parts:
        x0, y0, x1, y1 = op_["bbox"]
        host = next((k+1 for k, pc in enumerate(pieces) if _inside(op_["mid"], [
            (pc["bbox"][0]+p[0], pc["bbox"][1]+p[1]) for p in pc["outline_pts"]])), None)
        where = f"בתוך חתיכה {host}" if host else "מחוץ לחתיכות"
        warnings.append(f"קו לא סגור ({EDGE_KIND.get(op_['color'], 'צבע %d' % op_['color'])}, "
                        f"{(x1-x0)/10:.1f}×{(y1-y0)/10:.1f}) {where} — לא נחתך. לבדוק.")

    has_mitre = any(_eff_color(e, layer_color) in (MITRE, 8) for e in msp)
    if with_warnings:
        return pieces, has_mitre, warnings
    return pieces, has_mitre

# ------- תוכנית חיתוך יפה ל-Prodim -------
def _shape(c, x, y, W, Hh, piece, mm_scale, fill, alpha=0.20, rot=False):
    """מלבן, או המתאר המדויק כשיש (קובץ מודד). rot = סיבוב 90° כמו בסידור על הלוח"""
    pts = piece.get("outline_pts")
    if not pts:
        c.saveState(); c.setFillColor(fill); c.setFillAlpha(alpha); c.rect(x, y, W, Hh, fill=1, stroke=0); c.restoreState()
        c.rect(x, y, W, Hh, fill=0, stroke=1)
        return
    H0 = (W if rot else Hh) / mm_scale
    p = c.beginPath()
    for k, (px, py) in enumerate(pts):
        X, Y = ((H0 - py), px) if rot else (px, py)
        (p.moveTo if k == 0 else p.lineTo)(x + X*mm_scale, y + Y*mm_scale)
    p.close()
    c.saveState(); c.setFillColor(fill); c.setFillAlpha(alpha); c.drawPath(p, fill=1, stroke=0); c.restoreState()
    c.drawPath(p, fill=0, stroke=1)

def _draw_piece(c, x, y, w_cm, h_cm, scale, color, num, piece):
    W = w_cm*scale; Hh = h_cm*scale
    c.setFillColor(color); c.setStrokeColor(C_LINE); c.setLineWidth(1.2)
    _shape(c, x, y, W, Hh, piece, scale/10, color, alpha=0.20)
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
        elif name in ("שקע", "חשמל"): fF, sF = HexColor("#CFFAFE"), HexColor("#0891B2")
        ocx = x + op["from_left_cm"]*scale
        ocy = y + op["from_front_cm"]*scale
        ow = op["w"]*scale; oh = op["h"]*scale
        c.setFillColor(fF); c.setStrokeColor(sF); c.setLineWidth(0.8)
        c.rect(ocx-ow/2, ocy-oh/2, ow, oh, fill=1, stroke=1)
        c.setFillColor(sF); c.setFont(FONT_BOLD, 7)
        c.drawCentredString(ocx, ocy-3, heb(f"{name} {op['w']:g}×{op['h']:g}"))

def render_prodim_plan(pieces, mat, out_path, has_mitre=False, job_name="", title=None, warnings=None):
    from dxf_engine import nest_pieces
    slabs = nest_pieces([dict(p) for p in pieces], mat["slabL"], mat["slabW"])
    c = canvas.Canvas(out_path, pagesize=PAGE)
    def bg(): c.setFillColor(C_BG); c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    warnings = warnings or []
    total = len(slabs) + 1 + (1 if warnings else 0)
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
                c.setStrokeColor(col); c.setLineWidth(1.5)
                _shape(c, X, Y, W, Hh, pc, sc/10, col, rot=pc.get("rot"))
                c.setFillColor(C_LINE); c.setFont(FONT_BOLD, 8)
                c.drawCentredString(X+W/2, Y+Hh/2-3, f"{pc['len']:g}×{pc['depth']:g}")
        c.showPage()
    if warnings:
        bg()
        draw_header(c, "לבדיקה לפני חיתוך", f"{len(warnings)} הערות מקריאת קובץ המודד", total, total)
        c.setFillColor(C_LINE); c.setFont(FONT_NAME, 11)
        y = PAGE_H - 130
        for wtxt in warnings:
            if y < 50:
                c.drawRightString(PAGE_W-50, y, heb("• ועוד הערות — ראה ברשימה באפליקציה")); break
            c.drawRightString(PAGE_W-50, y, heb("• " + wtxt)); y -= 18
        c.showPage()
    c.save()
    return out_path, len(slabs)
