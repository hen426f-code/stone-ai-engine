"""Kitchen cutting plan: 311.5 x 195 L, arm LEFT, depth 64."""
import os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def heb(s):
    def is_heb(ch): return '\u0590' <= ch <= '\u05FF'
    runs, ck, cur = [], None, []
    for ch in s:
        k = 'heb' if is_heb(ch) else 'ltr'
        if k != ck:
            if cur: runs.append((ck, ''.join(cur)))
            cur, ck = [ch], k
        else: cur.append(ch)
    if cur: runs.append((ck, ''.join(cur)))
    out = []
    for i, (k, t) in enumerate(runs):
        if k == 'heb': out.append(t[::-1])
        else:
            ntr = (i > 0 and runs[i-1][0] == 'heb' and not t.endswith(' '))
            nld = (i < len(runs)-1 and runs[i+1][0] == 'heb' and not t.startswith(' '))
            t = (' '+t) if nld else t
            t = (t+' ') if ntr else t
            out.append(t)
    return ''.join(reversed(out))


FONT_NAME, FONT_BOLD = "Helvetica", "Helvetica-Bold"
import os as _os
_here=_os.path.dirname(_os.path.abspath(__file__))
for cand in [_os.path.join(_here,"DejaVuSans.ttf"),
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]:
    if os.path.exists(cand):
        pdfmetrics.registerFont(TTFont("HebFont", cand))
        b = cand.replace("Sans.ttf", "Sans-Bold.ttf").replace("Regular", "Bold")
        if os.path.exists(b):
            pdfmetrics.registerFont(TTFont("HebFontBold", b)); FONT_BOLD = "HebFontBold"
        else: FONT_BOLD = "HebFont"
        FONT_NAME = "HebFont"; break

C_BG = HexColor("#FAFAF7"); C_LINE = HexColor("#1F1F1F"); C_MUTED = HexColor("#666666")
C_ACCENT = HexColor("#D97757"); C_JOINT = HexColor("#C53030"); C_FRONT = HexColor("#8B5A2B")
C_NEUTRAL = HexColor("#F5F1E8")
C_GAS_F = HexColor("#FFF7E0"); C_GAS_S = HexColor("#B8860B")
C_SINK_F = HexColor("#E8F0FA"); C_SINK_S = HexColor("#2B6CB0")
PIECE_COLORS = [HexColor("#4A90A4"), HexColor("#D97757"), HexColor("#7CA982"), HexColor("#9B7BB8")]
PAGE = landscape(A4); PAGE_W, PAGE_H = PAGE


def hdim(c, x1, y, x2, text, fs=10):
    c.setStrokeColor(C_LINE); c.setLineWidth(0.7); c.line(x1, y, x2, y)
    for x in (x1, x2):
        s = 1 if x == x1 else -1
        c.line(x, y, x+s*4, y+2); c.line(x, y, x+s*4, y-2)
    c.setFillColor(C_LINE); c.setFont(FONT_BOLD, fs)
    c.drawCentredString((x1+x2)/2, y+4, text)


def vdim(c, x, y1, y2, text, fs=10):
    c.setStrokeColor(C_LINE); c.setLineWidth(0.7); c.line(x, y1, x, y2)
    for y in (y1, y2):
        s = 1 if y == y1 else -1
        c.line(x, y, x-2, y+s*4); c.line(x, y, x+2, y+s*4)
    c.setFillColor(C_LINE); c.setFont(FONT_BOLD, fs)
    c.saveState(); c.translate(x-7, (y1+y2)/2); c.rotate(90)
    c.drawCentredString(0, 0, text); c.restoreState()


def fe_h(c, x1, x2, y, lbl=None, below=False):
    c.setStrokeColor(C_FRONT); c.setLineWidth(3); c.line(x1, y, x2, y)
    mx = (x1+x2)/2; c.setLineWidth(1.5)
    for dx in (-3, 3): c.line(mx+dx, y-6, mx+dx, y+6)
    if lbl is not None:
        c.setFillColor(C_FRONT); c.setFont(FONT_BOLD, 9)
        c.drawCentredString(mx, y-14 if below else y+9, heb(f"עיבוד חזית {lbl}"))


def fe_v(c, x, y1, y2, lbl=None, right=True):
    c.setStrokeColor(C_FRONT); c.setLineWidth(3); c.line(x, y1, x, y2)
    my = (y1+y2)/2; c.setLineWidth(1.5)
    for dy in (-3, 3): c.line(x-6, my+dy, x+6, my+dy)
    if lbl is not None:
        c.setFillColor(C_FRONT); c.setFont(FONT_BOLD, 9)
        c.saveState()
        lx = x+14 if right else x-14
        c.translate(lx, my); c.rotate(-90 if right else 90)
        c.drawCentredString(0, 0, heb(f"עיבוד חזית {lbl}")); c.restoreState()


def joint_h(c, x1, x2, y):
    c.setStrokeColor(C_JOINT); c.setLineWidth(2.5); c.setDash([4, 3])
    c.line(x1, y, x2, y); c.setDash([])


def joint_v(c, x, y1, y2):
    c.setStrokeColor(C_JOINT); c.setLineWidth(2.5); c.setDash([4, 3])
    c.line(x, y1, x, y2); c.setDash([])


def draw_opening(c, cx, cy, w, h, label, fill, stroke, fs=8):
    c.setFillColor(fill); c.setStrokeColor(stroke); c.setLineWidth(0.8)
    c.rect(cx-w/2, cy-h/2, w, h, fill=1, stroke=1)
    if label:
        c.setFillColor(stroke); c.setFont(FONT_BOLD, fs)
        c.drawCentredString(cx, cy-3, heb(label))


def draw_header(c, title, sub, p, total):
    c.setFillColor(C_LINE); c.rect(0, PAGE_H-55, PAGE_W, 55, fill=1, stroke=0)
    c.setFillColor(C_ACCENT); c.rect(0, PAGE_H-60, PAGE_W, 5, fill=1, stroke=0)
    c.setFillColor(white); c.setFont(FONT_BOLD, 17)
    c.drawRightString(PAGE_W-30, PAGE_H-30, heb(title))
    if sub:
        c.setFillColor(HexColor("#CCCCCC")); c.setFont(FONT_NAME, 10)
        c.drawRightString(PAGE_W-30, PAGE_H-46, heb(sub))
    c.setFillColor(white); c.setFont(FONT_NAME, 10)
    c.drawString(30, PAGE_H-35, f"{p} / {total}")
    c.setFillColor(C_MUTED); c.setFont(FONT_NAME, 8)
    c.drawString(30, 20, heb("תוכנית חיתוך שיש   |   כל המידות בסנטימטרים"))
    c.drawRightString(PAGE_W-30, 20, heb("הופק באמצעות Claude"))


def draw_notes(c, notes, x=40, y=45, w=None, h=80):
    if w is None: w = PAGE_W-80
    c.setFillColor(C_NEUTRAL); c.setStrokeColor(C_ACCENT); c.setLineWidth(1.5)
    c.roundRect(x, y, w, h, 8, fill=1, stroke=1)
    c.setFillColor(C_ACCENT); c.setFont(FONT_BOLD, 11)
    c.drawRightString(x+w-15, y+h-20, heb("הערות"))
    c.setFillColor(C_LINE); c.setFont(FONT_NAME, 10)
    cy = y+h-38
    for ln in notes:
        c.drawRightString(x+w-15, cy, heb("• "+ln)); cy -= 14


class Kitchen:
    def __init__(self, long_cm, arm_cm, depth_cm, arm_side='right', sink=None, gas=None):
        self.long_cm = long_cm; self.arm_cm = arm_cm; self.depth_cm = depth_cm
        self.arm_side = arm_side; self.sink = sink; self.gas = gas


def draw_kitchen(c, k, ox, oy, scale, fills=None, dims=True, openings=True, labels=True):
    L = k.long_cm*scale; A = k.arm_cm*scale; D = k.depth_cm*scale
    ll_top = oy+A; ll_bot = oy+A-D
    if k.arm_side == 'right':
        alx = ox+L-D; arx = ox+L
    else:
        alx = ox; arx = ox+D

    if fills:
        for r in fills:
            c.setFillColor(r['color']); c.setStrokeColor(r['color']); c.setLineWidth(0)
            if r['type'] == 'long_range':
                x1 = ox+r['from_cm']*scale; x2 = ox+r['to_cm']*scale
                c.rect(x1, ll_bot, x2-x1, D, fill=1, stroke=0)
            elif r['type'] == 'arm':
                c.rect(alx, oy, D, A, fill=1, stroke=0)
            elif r['type'] == 'arm_below_corner':
                c.rect(alx, oy, D, A-D, fill=1, stroke=0)

    p = c.beginPath()
    if k.arm_side == 'right':
        p.moveTo(ox, ll_top); p.lineTo(ox+L, ll_top); p.lineTo(ox+L, oy)
        p.lineTo(alx, oy); p.lineTo(alx, ll_bot); p.lineTo(ox, ll_bot); p.close()
    else:
        p.moveTo(ox, ll_top); p.lineTo(ox+L, ll_top); p.lineTo(ox+L, ll_bot)
        p.lineTo(arx, ll_bot); p.lineTo(arx, oy); p.lineTo(ox, oy); p.close()
    c.setStrokeColor(C_LINE); c.setLineWidth(1.5)
    if fills: c.drawPath(p, fill=0, stroke=1)
    else: c.setFillColor(C_NEUTRAL); c.drawPath(p, fill=1, stroke=1)

    if openings:
        if k.gas:
            if k.gas['in'] == 'long':
                gx = ox+k.gas['from_left']*scale; gy = (ll_top+ll_bot)/2
                gw, gh = min(60*scale, D*0.7), D*0.6
                draw_opening(c, gx, gy, gw, gh, "גז" if labels else "",
                             C_GAS_F, C_GAS_S, max(6, int(scale*7)))
            else:
                gy = oy+k.gas['from_bottom']*scale; gx = (alx+arx)/2
                gw, gh = D*0.55, min(50*scale, D*0.7)
                draw_opening(c, gx, gy, gw, gh, "גז" if labels else "",
                             C_GAS_F, C_GAS_S, max(6, int(scale*7)))
        # Sink (either in long or in arm)
        if k.sink:
            if k.sink['in'] == 'long':
                sx = ox+k.sink['from_left']*scale; sy = (ll_top+ll_bot)/2
                sw, sh = min(80*scale, D*0.8), D*0.55
                draw_opening(c, sx, sy, sw, sh, "כיור" if labels else "",
                             C_SINK_F, C_SINK_S, max(6, int(scale*7)))
            else:  # in arm
                sy = oy+k.sink['from_bottom']*scale; sx = (alx+arx)/2
                sw, sh = D*0.55, min(60*scale, D*0.8)
                draw_opening(c, sx, sy, sw, sh, "כיור" if labels else "",
                             C_SINK_F, C_SINK_S, max(6, int(scale*7)))

    if dims:
        hdim(c, ox, ll_top+32, ox+L, str(k.long_cm), 11)
        if k.arm_side == 'right':
            vdim(c, ox-22, ll_bot, ll_top, str(k.depth_cm), 10)
            vdim(c, ox+L+22, oy, oy+A, str(k.arm_cm), 10)
            hdim(c, alx, oy-20, ox+L, str(k.depth_cm), 9)
        else:
            vdim(c, ox+L+22, ll_bot, ll_top, str(k.depth_cm), 10)
            vdim(c, ox-22, oy, oy+A, str(k.arm_cm), 10)
            hdim(c, ox, oy-20, ox+D, str(k.depth_cm), 9)

        # Draw dimension label for an opening (works for either sink or gas)
        def draw_opening_label(op):
            if op['in'] == 'long':
                sx = ox+op['from_left']*scale
                c.setStrokeColor(C_LINE); c.setLineWidth(1)
                c.line(sx, ll_top, sx, ll_top+12)
                c.setFillColor(C_LINE); c.setFont(FONT_BOLD, 9)
                if 'from_right' in op:
                    ay = ll_top+16
                    c.setStrokeColor(C_LINE); c.setLineWidth(0.7)
                    c.line(sx+4, ay, sx+22, ay)
                    c.line(sx+22, ay, sx+19, ay+2); c.line(sx+22, ay, sx+19, ay-2)
                    c.setFillColor(C_LINE); c.drawString(sx+4, ll_top+22, str(op['from_right']))
                else:
                    c.drawRightString(sx-3, ll_top+15, str(op['from_left']))
            else:  # in arm
                gy = oy+op['from_bottom']*scale
                if k.arm_side == 'left':
                    tx = alx
                    c.setStrokeColor(C_LINE); c.setLineWidth(1)
                    c.line(tx, gy, tx-10, gy)
                    ax = tx-18
                    c.line(ax, gy+6, ax, gy-16)
                    c.line(ax, gy-16, ax-2, gy-13); c.line(ax, gy-16, ax+2, gy-13)
                    c.setFillColor(C_LINE); c.setFont(FONT_BOLD, 9)
                    c.drawRightString(tx-22, gy+4, str(op['from_bottom']))
                else:
                    tx = arx
                    c.setStrokeColor(C_LINE); c.setLineWidth(1)
                    c.line(tx, gy, tx+10, gy)
                    ax = tx+18
                    c.line(ax, gy+6, ax, gy-16)
                    c.line(ax, gy-16, ax-2, gy-13); c.line(ax, gy-16, ax+2, gy-13)
                    c.setFillColor(C_LINE); c.setFont(FONT_BOLD, 9)
                    c.drawString(tx+22, gy+4, str(op['from_bottom']))

        if k.sink: draw_opening_label(k.sink)
        if k.gas: draw_opening_label(k.gas)

        # Front-edge marks on outline
        if k.arm_side == 'right':
            fe_h(c, ox, alx, ll_bot)
            fe_v(c, alx, oy, ll_bot, right=False)
            fe_h(c, alx, arx, oy)  # bottom edge of arm
        else:
            fe_h(c, arx, ox+L, ll_bot)
            fe_v(c, arx, oy, ll_bot, right=False)
            fe_h(c, alx, arx, oy)  # bottom edge of arm


def draw_h_piece(c, x, y, L_cm, D_cm, scale, color, main, sub=None, num=None,
                 openings=None, joint_left=False, joint_right=False,
                 fe_cm=None, fe_from=0):
    w = L_cm*scale; h = D_cm*scale
    c.setFillColor(color); c.setStrokeColor(C_LINE); c.setLineWidth(1.4)
    c.rect(x, y, w, h, fill=1, stroke=1)
    if openings:
        for op in openings:
            cx = x+op['from_left_cm']*scale; cy = y+h/2
            if op['kind'] == 'gas':
                gw, gh = min(60*scale, w*0.18), h*0.6
                draw_opening(c, cx, cy, gw, gh, "גז", C_GAS_F, C_GAS_S)
            else:
                sw, sh = min(80*scale, w*0.22), h*0.55
                draw_opening(c, cx, cy, sw, sh, "כיור", C_SINK_F, C_SINK_S)
    if joint_left: joint_v(c, x, y, y+h)
    if joint_right: joint_v(c, x+w, y, y+h)
    if fe_cm and fe_cm > 0:
        fx1 = x+fe_from*scale; fx2 = fx1+fe_cm*scale
        fe_h(c, fx1, fx2, y, lbl=fe_cm, below=True)
    hdim(c, x, y+h+14, x+w, str(L_cm), 10)
    vdim(c, x-18, y, y+h, str(D_cm), 9)
    if num is not None:
        c.setFillColor(white); c.circle(x+12, y+h-12, 10, fill=1, stroke=0)
        c.setFillColor(color); c.setFont(FONT_BOLD, 12)
        c.drawCentredString(x+12, y+h-16, str(num))
    ly = y - (32 if fe_cm and fe_cm > 0 else 22)
    c.setFillColor(C_LINE); c.setFont(FONT_BOLD, 13)
    c.drawCentredString(x+w/2, ly, main)
    if sub:
        c.setFillColor(C_MUTED); c.setFont(FONT_NAME, 9)
        c.drawCentredString(x+w/2, ly-14, heb(sub))


def draw_v_piece(c, x, y, L_cm, D_cm, scale, color, main, sub=None, num=None,
                 gas_from_bottom=None, sink_from_bottom=None, joint_top=False,
                 fe_cm=None, fe_from_top=0, fe_side='left',
                 fe_bottom_cm=None):
    w = D_cm*scale; h = L_cm*scale
    c.setFillColor(color); c.setStrokeColor(C_LINE); c.setLineWidth(1.4)
    c.rect(x, y, w, h, fill=1, stroke=1)
    if gas_from_bottom is not None:
        gy = y+gas_from_bottom*scale; gx = x+w/2
        gw, gh = w*0.55, min(50*scale, h*0.18)
        draw_opening(c, gx, gy, gw, gh, "גז", C_GAS_F, C_GAS_S)
    if sink_from_bottom is not None:
        sy = y+sink_from_bottom*scale; sx = x+w/2
        sw, sh = w*0.55, min(60*scale, h*0.2)
        draw_opening(c, sx, sy, sw, sh, "כיור", C_SINK_F, C_SINK_S)
    if joint_top: joint_h(c, x, x+w, y+h)
    if fe_cm and fe_cm > 0:
        fyt = y+h-fe_from_top*scale; fyb = fyt-fe_cm*scale
        fx = (x+w) if fe_side == 'right' else x
        fe_v(c, fx, fyb, fyt, lbl=fe_cm, right=(fe_side == 'right'))
    # Front-edge on the BOTTOM edge of the vertical piece (the short 64cm edge at the bottom)
    if fe_bottom_cm and fe_bottom_cm > 0:
        fe_h(c, x, x+w, y, lbl=fe_bottom_cm, below=True)
    vdim(c, x-18, y, y+h, str(L_cm), 10)
    hdim(c, x, y+h+14, x+w, str(D_cm), 9)
    if num is not None:
        c.setFillColor(white); c.circle(x+12, y+h-12, 10, fill=1, stroke=0)
        c.setFillColor(color); c.setFont(FONT_BOLD, 12)
        c.drawCentredString(x+12, y+h-16, str(num))
    c.setFillColor(C_LINE); c.setFont(FONT_BOLD, 13)
    c.drawCentredString(x+w/2, y-22, main)
    if sub:
        c.setFillColor(C_MUTED); c.setFont(FONT_NAME, 9)
        c.drawCentredString(x+w/2, y-36, heb(sub))


def page_overview(c, k, p, total, title, sub):
    draw_header(c, title, sub, p, total)
    aw = PAGE_W-160; ah = PAGE_H-320
    scale = min(1.7, aw/k.long_cm, ah/k.arm_cm)
    Lw = k.long_cm*scale; Lh = k.arm_cm*scale
    ox = (PAGE_W-Lw)/2; oy = max(220, 480-Lh)
    draw_kitchen(c, k, ox, oy, scale)
    lx, ly = 60, 70
    c.setFillColor(C_NEUTRAL); c.setStrokeColor(C_MUTED); c.setLineWidth(0.7)
    c.roundRect(lx, ly, 220, 90, 6, fill=1, stroke=1)
    c.setFillColor(C_LINE); c.setFont(FONT_BOLD, 11)
    c.drawRightString(lx+210, ly+70, heb("מקרא"))
    c.setFillColor(C_GAS_F); c.setStrokeColor(C_GAS_S)
    c.rect(lx+190, ly+48, 18, 12, fill=1, stroke=1)
    c.setFillColor(C_LINE); c.setFont(FONT_NAME, 10)
    c.drawRightString(lx+180, ly+50, heb("פתח גז"))
    c.setFillColor(C_SINK_F); c.setStrokeColor(C_SINK_S)
    c.rect(lx+190, ly+30, 18, 12, fill=1, stroke=1)
    c.setFillColor(C_LINE); c.drawRightString(lx+180, ly+32, heb("פתח כיור"))
    c.setStrokeColor(C_FRONT); c.setLineWidth(3); c.line(lx+188, ly+16, lx+208, ly+16)
    c.setLineWidth(1.5)
    for dx in (-3, 3): c.line(lx+198+dx, ly+10, lx+198+dx, ly+22)
    c.setFillColor(C_LINE); c.setFont(FONT_NAME, 10)
    c.drawRightString(lx+180, ly+14, heb("עיבוד חזית"))


def page_combo(c, k, p, total, title, sub, pieces, fills, notes):
    draw_header(c, title, sub, p, total)
    mw, mh = 200, 100
    ms = min(0.45, mw/k.long_cm, mh/k.arm_cm)
    mL = k.long_cm*ms; mA = k.arm_cm*ms
    mox = PAGE_W-50-mL; moy = PAGE_H-80-mA-10
    draw_kitchen(c, k, mox, moy, ms, fills=fills, dims=False, openings=True, labels=False)
    c.setFillColor(C_LINE); c.setFont(FONT_BOLD, 10)
    c.drawRightString(PAGE_W-50, moy+mA+14, heb("מיקום החתיכות במטבח"))
    arm_lx_cm = (k.long_cm-k.depth_cm) if k.arm_side == 'right' else 0
    arm_cx = mox+(arm_lx_cm+k.depth_cm/2)*ms
    ll_bot_my = moy+(k.arm_cm-k.depth_cm)*ms
    for i, r in enumerate(fills):
        if r['type'] == 'long_range':
            cx = mox+((r['from_cm']+r['to_cm'])/2)*ms
            cy = ll_bot_my+(k.depth_cm*ms)/2
        elif r['type'] == 'arm':
            cx = arm_cx; cy = moy+(k.arm_cm*ms)/2
        elif r['type'] == 'arm_below_corner':
            cx = arm_cx; cy = moy+((k.arm_cm-k.depth_cm)*ms)/2
        else: continue
        c.setFillColor(white); c.circle(cx, cy, 9, fill=1, stroke=0)
        c.setFillColor(r['color']); c.setFont(FONT_BOLD, 12)
        c.drawCentredString(cx, cy-4, str(i+1))

    has_v = any(p.get('orientation') == 'vertical' for p in pieces)
    n = len(pieces); gap = 35
    aw = PAGE_W-130; av = 200
    th_cm = sum((p['length_cm'] if p.get('orientation') != 'vertical' else k.depth_cm) for p in pieces)
    mv = max((p['length_cm'] for p in pieces if p.get('orientation') == 'vertical'), default=k.depth_cm)
    sw = (aw-gap*(n-1))/th_cm
    sh = av/mv if has_v else 1.0
    scale = min(1.1, sw, sh)
    base_y = 200
    x_cur = 65
    for i, p in enumerate(pieces):
        is_v = p.get('orientation') == 'vertical'
        if i+1 < len(pieces):
            nv = pieces[i+1].get('orientation') == 'vertical'
            corner = (is_v != nv)
        else: corner = False
        tg = 0 if corner else gap
        if is_v:
            ph_v = p['length_cm']*scale; pw_v = k.depth_cm*scale
            vy = base_y
            default_side = 'right' if k.arm_side == 'left' else 'left'
            fes = p.get('front_edge_side', default_side)
            draw_v_piece(c, x_cur, vy, p['length_cm'], k.depth_cm, scale,
                         p['color'], p['main_label'], sub=p.get('sub_label'), num=i+1,
                         gas_from_bottom=p.get('sink_from_bottom_cm'),
                         sink_from_bottom=p.get('sink_from_bottom_cm'),
                         joint_top=p.get('joint_top', False),
                         fe_cm=p.get('front_edge_cm'),
                         fe_from_top=p.get('front_edge_from_top_cm', 0),
                         fe_side=fes,
                         fe_bottom_cm=p.get('front_edge_bottom_cm'))
            x_cur += pw_v+tg
        else:
            pw = p['length_cm']*scale
            top_y = base_y+mv*scale if has_v else base_y+k.depth_cm*scale
            hy = top_y-k.depth_cm*scale
            draw_h_piece(c, x_cur, hy, p['length_cm'], k.depth_cm, scale,
                         p['color'], p['main_label'], sub=p.get('sub_label'), num=i+1,
                         openings=p.get('openings'),
                         joint_left=p.get('joint_left', False),
                         joint_right=p.get('joint_right', False),
                         fe_cm=p.get('front_edge_cm'),
                         fe_from=p.get('front_edge_from_cm', 0))
            x_cur += pw+tg

    c.setFillColor(C_LINE); c.setFont(FONT_BOLD, 11)
    c.drawString(60, base_y+(mv if has_v else k.depth_cm)*scale+35, heb("החתיכות לחיתוך"))

    c.setStrokeColor(C_JOINT); c.setLineWidth(2); c.setDash([4, 3])
    c.line(60, 145, 80, 145); c.setDash([])
    c.setFillColor(C_LINE); c.setFont(FONT_NAME, 9)
    c.drawString(85, 142, heb("= מיקום חיבור"))
    c.setStrokeColor(C_FRONT); c.setLineWidth(3); c.line(220, 145, 240, 145)
    c.setLineWidth(1.5)
    for dx in (-3, 3): c.line(230+dx, 139, 230+dx, 151)
    c.setFillColor(C_LINE); c.setFont(FONT_NAME, 9)
    c.drawString(245, 142, heb("= עיבוד חזית"))
    draw_notes(c, notes)


