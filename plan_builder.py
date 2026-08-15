# -*- coding: utf-8 -*-
"""בונה פרמטרי לתוכנית חיתוך מטבח L — ארבע קומבינציות לפי מסמך ההעברה של הן.
משתמש בפונקציות הציור המקוריות מ-gen_lib (המחולל של הן)."""
import os
from reportlab.pdfgen import canvas
import gen_lib as G
from gen_lib import (Kitchen, PIECE_COLORS, PAGE, PAGE_W, PAGE_H, C_BG,
                     page_overview, page_combo)

def g(n):  # format number: 131.0 -> "131", 247.5 -> "247.5"
    return f"{float(n):g}"

def _op_from_left(op, L):
    if op is None: return None
    if op.get('from_left') is not None: return op['from_left']
    if op.get('from_right') is not None: return L - op['from_right']
    return None

def build_combos(k, slab_len):
    """מחזיר רשימת קומבינציות: (title, sub, pieces, fills, notes)."""
    L, A, D = k.long_cm, k.arm_cm, k.depth_cm
    left = (k.arm_side == 'left')
    PC = PIECE_COLORS
    fe_side = 'right' if left else 'left'          # צד עיבוד החזית על חתיכת הזרוע האנכית
    arm_bottom = None                               # פתח בזרוע (from_bottom)
    for op in (k.sink, k.gas):
        if op and op.get('in') == 'arm':
            arm_bottom = op.get('from_bottom')
    # פתח שנמצא בצלע הארוכה (לפיצול) — כיור עדיף
    long_op = None; long_op_name = None
    for op, nm in ((k.sink, 'sink'), (k.gas, 'gas')):
        if op and op.get('in') == 'long':
            long_op = op; long_op_name = nm; break
    split_pos = _op_from_left(long_op, L)           # מיקום הפיצול (מרכז הפתח בצלע)

    def long_ops(piece_left_off):
        """פתחים שיושבים על חתיכת הצלע, במיקום יחסי לחתיכה."""
        out = []
        for op, nm in ((k.sink, 'sink'), (k.gas, 'gas')):
            if op and op.get('in') == 'long':
                fl = _op_from_left(op, L) - piece_left_off
                d = {'kind': nm, 'from_left_cm': fl}
                if op.get('w'): d['w'] = op['w']
                if op.get('h'): d['h'] = op['h']
                out.append(d)
        return out

    # חתיכת זרוע אנכית (arm-ext = A-D, או arm-whole = A)
    def v_piece(length, sub, fe_from_top, color):
        p = {'orientation': 'vertical', 'length_cm': length, 'color': color,
             'main_label': f"{g(length)} × {g(D)}", 'sub_label': sub,
             'joint_top': True, 'front_edge_cm': A - D, 'front_edge_from_top_cm': fe_from_top,
             'front_edge_side': fe_side, 'front_edge_bottom_cm': D}
        if arm_bottom is not None:
            p['sink_from_bottom_cm'] = arm_bottom
        return p

    combos = []
    corner_fits_whole = (L <= slab_len)          # הצלע השלמה נכנסת בלוח?
    long_nocorner = L - D
    nocorner_fits = (long_nocorner <= slab_len)

    # ---- קומבינציה 1: צלע שלמה (כולל פינה) + השלמת זרוע ----
    if corner_fits_whole:
        vp = v_piece(A - D, "השלמת זרוע", 0, PC[0])
        # עיבוד חזית על הצלע: אורך L-D, מתחיל אחרי הפינה (arm-left) או מ-0 (arm-right)
        hp = {'orientation': 'horizontal', 'length_cm': L, 'color': PC[1],
              'main_label': f"{g(L)} × {g(D)}", 'sub_label': "צלע ארוכה שלמה כולל פינה",
              'openings': long_ops(0), 'front_edge_cm': L - D,
              'front_edge_from_cm': (D if left else 0)}
        hp['joint_left' if left else 'joint_right'] = True
        pieces = [vp, hp] if left else [hp, vp]
        fills = [{'type': 'arm_below_corner', 'color': PC[0]},
                 {'type': 'long_range', 'from_cm': 0, 'to_cm': L, 'color': PC[1]}]
        rem = slab_len - L
        combos.append(("קומבינציה 1   ·   צלע ארוכה שלמה + השלמת זרוע",
                       "שתי חתיכות   ·   חיבור אחד בפינה   ·   ⭐ האופציה המומלצת",
                       pieces, fills,
                       ["הפתרון החסכוני ביותר — שתי חתיכות, חיבור יחיד בפינה",
                        "הצלע הארוכה השלמה כוללת את הפינה" + (" ואת הכיור/גז" if long_op else ""),
                        f"השלמת הזרוע ({g(A-D)}) כוללת את פתח הזרוע" if arm_bottom is not None else f"השלמת הזרוע ({g(A-D)})",
                        f"{g(L)} נכנס בלוח {g(slab_len)} (שארית {g(round(rem,1))} ס\"מ)"]))

    # ---- קומבינציה 2: צלע ללא פינה + זרוע שלמה ----
    if nocorner_fits:
        vp = v_piece(A, "זרוע שלמה כולל פינה", D, PC[0])
        # הצלע ללא פינה: הפתחים זזים ב-D (arm-left, הפינה בשמאל) — arm-right הפינה בימין, ללא הזזה
        off = D if left else 0
        hp = {'orientation': 'horizontal', 'length_cm': long_nocorner, 'color': PC[1],
              'main_label': f"{g(long_nocorner)} × {g(D)}", 'sub_label': "צלע ארוכה ללא הפינה",
              'openings': long_ops(off), 'front_edge_cm': long_nocorner, 'front_edge_from_cm': 0}
        hp['joint_left' if left else 'joint_right'] = True
        pieces = [vp, hp] if left else [hp, vp]
        fills = [{'type': 'arm', 'color': PC[0]},
                 {'type': 'long_range', 'from_cm': (D if left else 0),
                  'to_cm': (L if left else long_nocorner), 'color': PC[1]}]
        combos.append(("קומבינציה 2   ·   זרוע שלמה + צלע ארוכה ללא פינה",
                       "שתי חתיכות   ·   חיבור אחד בפינה (מצד הצלע)",
                       pieces, fills,
                       ["הזרוע השלמה כוללת את הפינה — חיבור אחד בפינה",
                        "אופציה אם רוצים שהזרוע תהיה חתיכה רציפה",
                        "שתי החתיכות נכנסות בלוח " + g(slab_len)]))

    # ---- קומבינציות 3/4: פיצול במרכז הפתח שבצלע (רק אם צריך/רלוונטי) ----
    need_split = (not corner_fits_whole)
    if split_pos is not None and (need_split or True):
        # A חלק (כולל פינה) 0..split, B חלק split..L
        if left:
            aA_len = split_pos                 # כולל פינה בשמאל
            aB_len = L - split_pos
            aA_fe = split_pos - D; aA_from = D
            aB_fe = aB_len; aB_from = 0
            aA_openings = long_ops(0)          # פתחים משמאל לפיצול
            aB_openings = long_ops(split_pos)
        else:
            aA_len = split_pos
            aB_len = L - split_pos             # כולל פינה בימין
            aA_fe = aA_len; aA_from = 0
            aB_fe = aB_len - D; aB_from = 0
            aA_openings = long_ops(0)
            aB_openings = long_ops(split_pos)
        # רק פתחים שבתוך כל חלק
        aA_openings = [o for o in aA_openings if -1 <= o['from_left_cm'] <= aA_len+1]
        aB_openings = [o for o in aB_openings if -1 <= o['from_left_cm'] <= aB_len+1]
        pieceA = {'orientation': 'horizontal', 'length_cm': aA_len, 'color': PC[1],
                  'main_label': f"{g(aA_len)} × {g(D)}", 'sub_label': "עד מרכז הפתח",
                  'openings': aA_openings, 'joint_left': True, 'joint_right': True,
                  'front_edge_cm': max(aA_fe, 0), 'front_edge_from_cm': aA_from}
        pieceB = {'orientation': 'horizontal', 'length_cm': aB_len, 'color': PC[2],
                  'main_label': f"{g(aB_len)} × {g(D)}", 'sub_label': "ממרכז הפתח עד הקצה",
                  'openings': aB_openings, 'joint_left': True,
                  'front_edge_cm': max(aB_fe, 0), 'front_edge_from_cm': aB_from}
        fills_split = [{'type': 'long_range', 'from_cm': 0, 'to_cm': split_pos, 'color': PC[1]},
                       {'type': 'long_range', 'from_cm': split_pos, 'to_cm': L, 'color': PC[2]}]
        # combo 3: + arm-ext
        vp3 = v_piece(A - D, "השלמת זרוע", 0, PC[0])
        pieces3 = ([vp3, pieceA, pieceB] if left else [pieceA, pieceB, vp3])
        fills3 = [{'type': 'arm_below_corner', 'color': PC[0]}] + fills_split
        combos.append(("קומבינציה 3   ·   חיבור במרכז הפתח + השלמת זרוע",
                       "שלוש חתיכות   ·   חיבור ראשי נסתר במרכז הפתח",
                       pieces3, fills3,
                       ["החיבור הראשי במרכז הפתח — הכי נסתר שאפשר",
                        "חיבור שני בפינה",
                        "אופציה לחתיכות קטנות יותר לשינוע"]))
        # combo 4: + arm-whole
        vp4 = v_piece(A, "זרוע שלמה כולל פינה", D, PC[0])
        # בפיצול עם זרוע שלמה, חלק A מאבד את הפינה
        pieceA4 = dict(pieceA)
        if left:
            pieceA4['length_cm'] = split_pos - D
            pieceA4['main_label'] = f"{g(split_pos-D)} × {g(D)}"
            pieceA4['front_edge_cm'] = max(split_pos - D, 0); pieceA4['front_edge_from_cm'] = 0
            pieceA4['openings'] = [dict(o, from_left_cm=o['from_left_cm']-D) for o in aA_openings]
        pieces4 = ([vp4, pieceA4, pieceB] if left else [pieceA4, pieceB, vp4])
        fills4 = [{'type': 'arm', 'color': PC[0]}] + [
            {'type': 'long_range', 'from_cm': (D if left else 0), 'to_cm': split_pos, 'color': PC[1]},
            {'type': 'long_range', 'from_cm': split_pos, 'to_cm': L, 'color': PC[2]}]
        combos.append(("קומבינציה 4   ·   חיבור במרכז הפתח + זרוע שלמה",
                       "שלוש חתיכות   ·   זרוע שלמה + חיבור נסתר בפתח",
                       pieces4, fills4,
                       ["זרוע שלמה כולל הפינה",
                        "חיבור ראשי נסתר במרכז הפתח",
                        "חיבור שני בפינה (מצד הצלע)"]))
    return combos

def render_plan(k, slab_len, out_path, job_name=""):
    combos = build_combos(k, slab_len)
    total = 1 + len(combos)
    c = canvas.Canvas(out_path, pagesize=PAGE)
    def bg():
        c.setFillColor(C_BG); c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    bg()
    sub = f"צלע ארוכה {g(k.long_cm)}    ·    זרוע {g(k.arm_cm)}    ·    עומק {g(k.depth_cm)}    ·    לוח {g(slab_len)}"
    page_overview(c, k, 1, total, (job_name + "   ·   " if job_name else "") + "המטבח המקורי · צורת L", sub)
    c.showPage()
    for i, (title, csub, pieces, fills, notes) in enumerate(combos):
        bg(); page_combo(c, k, 2 + i, total, title, csub, pieces, fills, notes); c.showPage()
    c.save()
    return out_path, len(combos)

if __name__ == "__main__":
    # שחזור הדוגמה המוכחת 311.5 x 195 arm-left
    k = Kitchen(311.5, 195, 64, 'left',
                gas={'in': 'long', 'from_left': 271.5, 'from_right': 40},
                sink={'in': 'arm', 'from_bottom': 95.5})
    p, n = render_plan(k, 320, "/home/claude/outputs/param_311.pdf", "בדיקה 311.5")
    print("built", p, "combos:", n)
