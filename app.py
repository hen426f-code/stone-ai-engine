# -*- coding: utf-8 -*-
"""שרת המנוע — מריץ את המחולל המוכח של הן: תוכנית חיתוך יפה (PDF) + DXF למכונה.
Endpoints: /api/plan (מטבח L מסקיצה/ידני), /api/prodim (קובץ מודד)."""
import base64, io, tempfile, os
from flask import Flask, request, jsonify
from flask_cors import CORS
import gen_lib as G
from gen_lib import Kitchen
import plan_builder as PB
import dxf_engine as DE
import prodim_reader as PR

app = Flask(__name__)
CORS(app)

def _f(v, default=None):
    """המרה בטוחה למספר: None/ריק/טקסט לא-מספרי -> default"""
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def _remnants(slabs):
    """רשימת שאריות פנויות מכל הלוחות: [{slab, len, depth}]"""
    out = []
    for i, sl in enumerate(slabs):
        for r in sl.get("remnants", []):
            w, h = round(float(r["w"]), 1), round(float(r["h"]), 1)
            if w >= 5 and h >= 5:
                out.append({"slab": i + 1, "len": w, "depth": h})
    return out

def norm_piece(p, is_clad=False):
    ops = []
    for o in (p.get("openings") or []):
        ow, oh = _f(o.get("w")), _f(o.get("h"))
        if not ow or not oh:
            continue
        ops.append({"kind": o.get("kind") or "פתח",
                    "from_left_cm": _f(o.get("from_left_cm"), 0) or 0,
                    "from_front_cm": _f(o.get("from_front_cm"), 0) or 0,
                    "w": ow, "h": oh})
    plen, pdep = _f(p.get("len")), _f(p.get("depth"))
    if not plen or not pdep or plen <= 0 or pdep <= 0:
        return None
    d = {"len": plen, "depth": pdep,
         "label": p.get("label") or ("ציפוי קיר" if is_clad else "חתיכה"),
         "openings": ops}
    fe = _f(p.get("fe_cm"))
    if fe and fe > 0:
        d["fe_cm"] = fe; d["fe_from_cm"] = _f(p.get("fe_from_cm"), 0) or 0
    return d

def _b64_file(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

@app.get("/")
def health():
    return jsonify({"ok": True, "service": "stone-ai-engine",
                    "endpoints": ["/api/plan", "/api/prodim", "/api/pieces", "/api/combos"]})

@app.post("/api/plan")
def plan():
    """מטבח L. body: {long,arm,depth,arm_side,sink,gas,material}"""
    try:
        b = request.get_json(force=True)
        mat = DE.MATERIALS.get(b.get("material", "porcelan"), DE.MATERIALS["porcelan"])
        k = Kitchen(float(b["long"]), float(b["arm"]), float(b["depth"]),
                    b.get("arm_side", "left"), sink=b.get("sink"), gas=b.get("gas"))
        job = b.get("job_name", "")
        with tempfile.TemporaryDirectory() as td:
            pdf_path = os.path.join(td, "plan.pdf")
            PB.render_plan(k, mat["slabL"], pdf_path, job)
            # DXF for the RECOMMENDED combo (combo 1: whole long + arm-ext) if it fits, else split
            combos = PB.build_combos(k, mat["slabL"])
            pieces = _combo_to_pieces(combos[0], k) if combos else []
            dxf_text, slabs = DE.gen_dxf(pieces, mat) if pieces else ("", [])
            return jsonify({"ok": True, "pdf": _b64_file(pdf_path),
                            "dxf": dxf_text, "combos": len(combos),
                            "slabs": len(slabs), "remnants": _remnants(slabs)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

def _combo_to_pieces(combo, k):
    """ממיר חתיכות הקומבינציה לרשימת {len,depth,openings} למנוע ה-DXF."""
    _, _, pieces, _, _ = combo
    out = []
    for p in pieces:
        is_v = p.get("orientation") == "vertical"
        ln = p["length_cm"] if not is_v else p["length_cm"]
        dp = k.depth_cm
        ops = []
        for op in p.get("openings", []) or []:
            if op.get("w") and op.get("h"):
                ops.append({"from_left_cm": op["from_left_cm"], "w": op["w"], "h": op["h"],
                            "fromFront": op.get("from_front_cm")})
        out.append({"len": ln, "depth": dp, "openings": ops})
    return out

@app.post("/api/prodim")
def prodim():
    """קובץ מודד. multipart 'file' או body {dxf_text}. + material."""
    try:
        material = request.form.get("material") or (request.get_json(silent=True) or {}).get("material", "porcelan")
        mat = DE.MATERIALS.get(material, DE.MATERIALS["porcelan"])
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "in.dxf")
            if "file" in request.files:
                request.files["file"].save(src)
            else:
                txt = (request.get_json(silent=True) or {}).get("dxf_text", "")
                open(src, "w", encoding="utf-8", errors="ignore").write(txt)
            pieces, mitre = PR.read_prodim(src)
            if not pieces:
                return jsonify({"ok": False, "error": "לא זוהו חתיכות (ירוק=עיבוד) בקובץ"}), 400
            pdf_path = os.path.join(td, "prodim.pdf")
            PR.render_prodim_plan(pieces, mat, pdf_path, mitre)
            dxf_text, slabs = DE.gen_dxf([dict(p) for p in pieces], mat)
            plist = [{"label": p.get("label") or ("חתיכה %d" % (i + 1)),
                      "len": p["len"], "depth": p["depth"],
                      "openings": p.get("openings", [])} for i, p in enumerate(pieces)]
            return jsonify({"ok": True, "pdf": _b64_file(pdf_path), "dxf": dxf_text,
                            "pieces": len(pieces), "pieces_list": plist,
                            "slabs": len(slabs), "mitre": mitre, "remnants": _remnants(slabs)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.post("/api/pieces")
def pieces_endpoint():
    """חתיכות כלליות (מסקיצה/ידני): {pieces:[{len,depth,label?,openings:[{kind,from_left_cm,from_front_cm,w,h}]}],
       cladding:[{len,depth,label?}], material, job_name} -> PDF יפה + DXF."""
    try:
        b = request.get_json(force=True)
        mat = DE.MATERIALS.get(b.get("material", "porcelan"), DE.MATERIALS["porcelan"])
        raw = b.get("pieces") or []
        clad = b.get("cladding") or []
        def norm(p, is_clad=False):
            ops = []
            for o in (p.get("openings") or []):
                if o.get("w") and o.get("h"):
                    ow, oh = _f(o.get("w")), _f(o.get("h"))
                    if not ow or not oh:
                        continue
                    ops.append({"kind": o.get("kind") or "פתח",
                                "from_left_cm": _f(o.get("from_left_cm"), 0) or 0,
                                "from_front_cm": _f(o.get("from_front_cm"), 0) or 0,
                                "w": ow, "h": oh})
            plen, pdep = _f(p.get("len")), _f(p.get("depth"))
            if not plen or not pdep or plen <= 0 or pdep <= 0:
                return None
            d = {"len": plen, "depth": pdep,
                 "label": p.get("label") or ("ציפוי קיר" if is_clad else "חתיכה"),
                 "openings": ops}
            if p.get("fe_cm"):
                fe = _f(p.get("fe_cm"))
                if fe and fe > 0:
                    d["fe_cm"] = fe; d["fe_from_cm"] = _f(p.get("fe_from_cm"), 0) or 0
            return d
        allp = [x for x in (norm(p) for p in raw) if x]
        allp += [x for x in (norm(p, True) for p in clad) if x]
        if not allp:
            return jsonify({"ok": False, "error": "לא התקבלו חתיכות"}), 400
        with tempfile.TemporaryDirectory() as td:
            pdf_path = os.path.join(td, "plan.pdf")
            PR.render_prodim_plan(allp, mat, pdf_path, False, b.get("job_name", ""), title="חתיכות לחיתוך")
            dxf_text, slabs = DE.gen_dxf([dict(p) for p in allp], mat)
            return jsonify({"ok": True, "pdf": _b64_file(pdf_path), "dxf": dxf_text,
                            "pieces": len(allp), "slabs": len(slabs), "remnants": _remnants(slabs)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.post("/api/combos")
def combos_endpoint():
    """כל הקומבינציות במסמך אחד + DXF לכל אחת.
    body: {combos:[{title, note, pieces:[{len,depth,label,fe_cm,openings}]}],
           cladding:[...], material, job_name}"""
    try:
        b = request.get_json(force=True)
        mat = DE.MATERIALS.get(b.get("material", "porcelan"), DE.MATERIALS["porcelan"])
        clad = [x for x in (norm_piece(p, True) for p in (b.get("cladding") or [])) if x]
        combos = b.get("combos") or []
        if not combos:
            return jsonify({"ok": False, "error": "לא התקבלו קומבינציות"}), 400
        job = b.get("job_name", "")
        out = []
        from pypdf import PdfWriter, PdfReader
        import io as _io
        writer = PdfWriter()
        with tempfile.TemporaryDirectory() as td:
            for i, c in enumerate(combos):
                pcs = [x for x in (norm_piece(p) for p in (c.get("pieces") or [])) if x]
                allp = pcs + clad
                if not allp:
                    continue
                title = "קומבינציה %d · %s" % (i + 1, c.get("title", ""))
                pth = os.path.join(td, "c%d.pdf" % i)
                PR.render_prodim_plan(allp, mat, pth, False, job, title=title)
                for pg in PdfReader(pth).pages:
                    writer.add_page(pg)
                dxf_text, slabs = DE.gen_dxf([dict(p) for p in allp], mat)
                out.append({"title": c.get("title", ""), "note": c.get("note", ""),
                            "dxf": dxf_text, "slabs": len(slabs),
                            "pieces": len(allp), "remnants": _remnants(slabs)})
            buf = _io.BytesIO(); writer.write(buf)
            pdf_b64 = base64.b64encode(buf.getvalue()).decode()
        return jsonify({"ok": True, "pdf": pdf_b64, "combos": out})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
