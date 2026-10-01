# -*- coding: utf-8 -*-
"""קורא לקובץ העבודה השמור של מכונת GMM (סיומת dat).

הקובץ הוא סריאליזציה בינארית של ‎.NET (BinaryFormatter, פורמט MS-NRBF).
הקורא מפרק את כל הרשומות לעץ פייתון: אובייקט = dict עם "__class__",
מערך = list, הפניות בין אובייקטים נפתרות בסוף. אין כאן ניחוש של שדות:
השמות והטיפוסים כתובים בקובץ עצמו.

שימוש: python3 gmm_job.py job.dat > job.json
"""
import json, struct, sys, datetime

# טיפוסים פרימיטיביים לפי MS-NRBF 2.1.2.3
P_BOOL, P_BYTE, P_CHAR, P_DECIMAL, P_DOUBLE, P_INT16, P_INT32, P_INT64, P_SBYTE, \
    P_SINGLE, P_TIMESPAN, P_DATETIME, P_UINT16, P_UINT32, P_UINT64, P_NULL, P_STRING = \
    1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18

# BinaryType לפי 2.1.2.2
BT_PRIMITIVE, BT_STRING, BT_OBJECT, BT_SYSCLASS, BT_CLASS, BT_OBJARRAY, BT_STRARRAY, BT_PRIMARRAY = range(8)


class Ref:
    """הפניה לאובייקט שעוד לא נקרא (נפתרת בסוף)"""
    __slots__ = ("id",)

    def __init__(self, i):
        self.id = i


class _Null:
    """ריצה של ערכי null בתוך מערך (ObjectNullMultiple)"""
    __slots__ = ("n",)

    def __init__(self, n):
        self.n = n


class NrbfReader:
    def __init__(self, data):
        self.d = data
        self.p = 0
        self.objects = {}      # objectId -> ערך
        self.classes = {}      # objectId -> מטא־דאטה של מחלקה (לשימוש ב-ClassWithId)
        self.libraries = {}
        self.root_id = None

    # ---- קריאה בסיסית ----
    def _u(self, fmt):
        v = struct.unpack_from("<" + fmt, self.d, self.p)
        self.p += struct.calcsize("<" + fmt)
        return v[0]

    def byte(self):
        b = self.d[self.p]
        self.p += 1
        return b

    def string(self):
        n = 0
        shift = 0
        while True:
            b = self.byte()
            n |= (b & 0x7F) << shift
            if not b & 0x80:
                break
            shift += 7
        s = self.d[self.p:self.p + n].decode("utf-8", errors="replace")
        self.p += n
        return s

    def primitive(self, t):
        if t == P_BOOL:
            return self.byte() != 0
        if t == P_BYTE:
            return self.byte()
        if t == P_SBYTE:
            return self._u("b")
        if t == P_CHAR:
            # תו UTF-8 יחיד
            b = self.d[self.p]
            n = 1 if b < 0x80 else 2 if b < 0xE0 else 3 if b < 0xF0 else 4
            s = self.d[self.p:self.p + n].decode("utf-8", errors="replace")
            self.p += n
            return s
        if t == P_DECIMAL:
            return self.string()
        if t == P_DOUBLE:
            return self._u("d")
        if t == P_SINGLE:
            return self._u("f")
        if t == P_INT16:
            return self._u("h")
        if t == P_UINT16:
            return self._u("H")
        if t == P_INT32:
            return self._u("i")
        if t == P_UINT32:
            return self._u("I")
        if t == P_INT64:
            return self._u("q")
        if t == P_UINT64:
            return self._u("Q")
        if t == P_TIMESPAN:
            return {"__timespan_ticks__": self._u("q")}
        if t == P_DATETIME:
            raw = self._u("Q")
            ticks = raw & 0x3FFFFFFFFFFFFFFF
            try:
                dt = datetime.datetime(1, 1, 1) + datetime.timedelta(microseconds=ticks // 10)
                return {"__datetime__": dt.isoformat(), "kind": raw >> 62}
            except OverflowError:
                return {"__datetime_ticks__": ticks}
        if t == P_STRING:
            return self.string()
        if t == P_NULL:
            return None
        raise ValueError(f"טיפוס פרימיטיבי לא מוכר {t} במיקום {self.p}")

    # ---- מטא־דאטה של מחלקה ----
    def class_info(self):
        oid = self._u("i")
        name = self.string()
        n = self._u("i")
        members = [self.string() for _ in range(n)]
        return oid, name, members

    def member_types(self, n):
        bts = [self.byte() for _ in range(n)]
        extra = []
        for bt in bts:
            if bt in (BT_PRIMITIVE, BT_PRIMARRAY):
                extra.append(self.byte())
            elif bt == BT_SYSCLASS:
                extra.append(self.string())
            elif bt == BT_CLASS:
                extra.append((self.string(), self._u("i")))
            else:
                extra.append(None)
        return bts, extra

    def _values(self, meta):
        vals = {}
        for name, bt, ex in zip(meta["members"], meta["bts"], meta["extra"]):
            if bt == BT_PRIMITIVE:
                vals[name] = self.primitive(ex)
            else:
                v = self.record()
                if isinstance(v, _Null):
                    v = None
                vals[name] = v
        return vals

    def _make_obj(self, oid, meta):
        obj = {"__class__": meta["name"]}
        self.objects[oid] = obj
        obj.update(self._values(meta))
        return obj

    # ---- רשומות ----
    def record(self):
        rt = self.byte()
        if rt == 0:      # SerializedStreamHeader
            self.root_id = self._u("i")
            self._u("i"); self._u("i"); self._u("i")
            return self.record()
        if rt == 12:     # BinaryLibrary
            lid = self._u("i")
            self.libraries[lid] = self.string()
            return self.record()
        if rt in (5, 4):  # ClassWithMembersAndTypes / SystemClassWithMembersAndTypes
            oid, name, members = self.class_info()
            bts, extra = self.member_types(len(members))
            if rt == 5:
                self._u("i")  # libraryId
            meta = {"name": name, "members": members, "bts": bts, "extra": extra}
            self.classes[oid] = meta
            return self._make_obj(oid, meta)
        if rt in (3, 2):  # ClassWithMembers / SystemClassWithMembers (בלי טיפוסים — לא נפוץ)
            oid, name, members = self.class_info()
            if rt == 3:
                self._u("i")
            meta = {"name": name, "members": members,
                    "bts": [BT_OBJECT] * len(members), "extra": [None] * len(members)}
            self.classes[oid] = meta
            return self._make_obj(oid, meta)
        if rt == 1:      # ClassWithId — מחלקה שכבר הוגדרה
            oid = self._u("i")
            meta = self.classes[self._u("i")]
            self.classes[oid] = meta
            return self._make_obj(oid, meta)
        if rt == 6:      # BinaryObjectString
            oid = self._u("i")
            s = self.string()
            self.objects[oid] = s
            return s
        if rt == 8:      # MemberPrimitiveTyped
            return self.primitive(self.byte())
        if rt == 9:      # MemberReference
            return Ref(self._u("i"))
        if rt == 10:     # ObjectNull
            return None
        if rt == 13:     # ObjectNullMultiple256
            return _Null(self.byte())
        if rt == 14:     # ObjectNullMultiple
            return _Null(self._u("i"))
        if rt == 15:     # ArraySinglePrimitive
            oid = self._u("i"); n = self._u("i"); t = self.byte()
            if t == P_BYTE:
                arr = list(self.d[self.p:self.p + n]); self.p += n
            else:
                arr = [self.primitive(t) for _ in range(n)]
            self.objects[oid] = arr
            return arr
        if rt in (16, 17):  # ArraySingleObject / ArraySingleString
            oid = self._u("i"); n = self._u("i")
            arr = []
            self.objects[oid] = arr
            self._fill(arr, n, lambda: self.record())
            return arr
        if rt == 7:      # BinaryArray
            oid = self._u("i")
            atype = self.byte()
            rank = self._u("i")
            lengths = [self._u("i") for _ in range(rank)]
            if atype in (3, 4, 5):
                [self._u("i") for _ in range(rank)]  # lower bounds
            bt = self.byte()
            ex = None
            if bt in (BT_PRIMITIVE, BT_PRIMARRAY):
                ex = self.byte()
            elif bt == BT_SYSCLASS:
                ex = self.string()
            elif bt == BT_CLASS:
                ex = (self.string(), self._u("i"))
            total = 1
            for L in lengths:
                total *= L
            arr = []
            self.objects[oid] = arr
            if bt == BT_PRIMITIVE:
                arr.extend(self.primitive(ex) for _ in range(total))
            else:
                self._fill(arr, total, lambda: self.record())
            return arr
        if rt == 11:     # MessageEnd
            return StopIteration
        raise ValueError(f"סוג רשומה לא מוכר {rt} במיקום {self.p - 1}")

    def _fill(self, arr, n, read):
        while len(arr) < n:
            v = read()
            if isinstance(v, _Null):
                arr.extend([None] * v.n)
            else:
                arr.append(v)

    def parse(self):
        while self.p < len(self.d):
            if self.record() is StopIteration:
                break
        return self._resolve(self.objects.get(self.root_id), set())

    def _resolve(self, v, seen):
        if isinstance(v, Ref):
            v = self.objects.get(v.id)
        if isinstance(v, dict):
            if id(v) in seen:
                return v
            seen.add(id(v))
            for k in list(v):
                v[k] = self._resolve(v[k], seen)
        elif isinstance(v, list):
            if id(v) in seen:
                return v
            seen.add(id(v))
            for i in range(len(v)):
                v[i] = self._resolve(v[i], seen)
        return v


def to_plain(v, path=None):
    """עותק שאפשר להמיר ל-JSON: הפניה מעגלית (למשל לאובייקט האב) נכתבת כשם המחלקה בלבד"""
    path = path or set()
    if isinstance(v, (dict, list)):
        if id(v) in path:
            return "<חזרה אל %s>" % (v.get("__class__", "dict") if isinstance(v, dict) else "list")
        path = path | {id(v)}
        if isinstance(v, dict):
            return {k: to_plain(x, path) for k, x in v.items()}
        return [to_plain(x, path) for x in v]
    return v


def read_job(path):
    with open(path, "rb") as f:
        r = NrbfReader(f.read())
    root = r.parse()
    return root, r


def _items(lst):
    """List<T> של ‎.NET: רק _size הפריטים הראשונים במערך הפנימי תקפים"""
    if isinstance(lst, dict) and "_items" in lst:
        return lst["_items"][:lst.get("_size", len(lst["_items"]))]
    return lst or []


def _pt(p):
    return (round(p["x0"], 2), round(p["y0"], 2)) if p else None


def _enum(v):
    return v.get("value__") if isinstance(v, dict) else v


# סוגי פעולה ב-ordLav שזוהו מול קוד המכונה (ISO) של העבודה לדוגמה
LAV_CUT, LAV_SPOST = 1, 2


def summarize(root):
    """תמצית העבודה: הגדרות לוח ומסור, חיתוכים עם הארכות, תנועות ואקום, וסדר הביצוע"""
    t = root["tgl1"]
    cuts = []
    for c in _items(t["tgl"]):
        tr, tu = c["tratto"], c["trattoUt"]
        p1, p2 = _pt(tr["p1_"]), _pt(tr["p2_"])
        cuts.append({
            "id": c["ID"], "piece": c["gruppoID"], "priority": c["priorita"],
            "p1": p1, "p2": p2,
            "length_mm": round(((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2) ** 0.5, 1),
            "head_angle_C": c["posC"], "tilt": c["inclTgl"],
            "depth_mm": c["profTgl"], "overcut_mm": c["debordo"],
            # הארכות [התחלה, סוף] במ"מ
            "ext_manual": [round(x, 1) for x in c["prol"]],
            "ext_to_adjacent": [round(x, 1) for x in c["prolTglAdiac"]],
            "ext_for_vacuum": [round(x, 1) for x in c["prolVentose"]],
            "tool_p1": _pt(tu["p1_"]) if tu else None, "tool_p2": _pt(tu["p2_"]) if tu else None,
        })
    moves = []
    for g in _items(t["grpiSpost"]):
        moves.append({
            "id": g["ID"], "priority": g["priorita"],
            "pick": _pt(g["ptoSpost"]), "drop": _pt(g["ptoSpostDef"]),
            "dx": round(g["deltaSpostX"], 2), "dy": round(g["deltaSpostY"], 2),
            "default_mm": round(g["spostDefault"], 2), "cups_mask": g["maskUsoVent"],
            "angle": g["angVentose"],
            "cuts_before": [c["ID"] for c in _items(g["lstTgl"]) if isinstance(c, dict)],
        })
    order = []
    for o in _items(t["ordLav"]):
        k = _enum(o["tipoLav"])
        order.append(("חיתוך" if k == LAV_CUT else "ואקום" if k == LAV_SPOST else f"סוג {k}", o["indLav"]))
    return {
        "slab_thickness_mm": t["spessLastra"], "overcut_mm": t["debZ"],
        "disc_diameter_mm": round(t["diamDisco"], 2), "disc_thickness_mm": t["spesDisco"],
        "max_extension_mm": t["maxProlTgl"], "vacuum_enabled": t["abilVentosa"],
        "auto_extension_threshold_mm": t["sogliaProlAuto"], "vacuum_safety_margin_mm": t["margSicDeltaSpost"],
        "table_mm": (t["dimxTavola"], t["dimyTavola"]),
        "slab_outline": [(_pt(s["p1_"]), _pt(s["p2_"])) for s in _items(t["perimLastra"]["tratti"])],
        "cuts": cuts, "moves": moves, "order": order,
    }


def iso_crosscheck(summary, iso_text):
    """משווה את החיתוכים ותנועות הוואקום שבקובץ העבודה מול ההערות בקוד המכונה (ISO).
    מחזיר רשימת אי־התאמות (ריקה = הכל תואם)"""
    import re
    def blocks(tag):
        out = {}
        for m in re.finditer(r";\s*\*+\s*ID %s = (\d+)\s*\*+(.*?)(?=; \*{8}  ID|\Z)" % tag, iso_text, re.S):
            vals = dict(re.findall(r";(p[12]\.[xy]0)=([-\d.]+)", m.group(2)))
            if vals:
                out[int(m.group(1))] = {k: float(v) for k, v in vals.items()}
        return out
    # חיתוך שאין לו מסלול כלי לא מבוצע (הצלע מכוסה בהארכת החיתוך הסמוך).
    # אחרי תנועת ואקום, הפס שהורם זז, וחיתוכים שבוצעו עליו אחר כך מופיעים בקוד המכונה במיקום המוזז.
    cuts = {c["id"]: c for c in summary["cuts"]}
    moves = {m["id"]: m for m in summary["moves"]}
    shifted = []  # (ציר, ערך קו החיתוך, צד, dx, dy)
    tag, spost = blocks("TAGLIO"), blocks("SPOST")
    bad = []

    def side_of(axis, val, pt):
        return (pt[1] if axis == "y" else pt[0]) > val

    for kind, idx in summary["order"]:
        if kind == "ואקום":
            mv = moves.get(idx)
            ref = [cuts[i] for i in mv["cuts_before"] if cuts.get(i) and cuts[i]["tool_p1"]] if mv else []
            if not ref:
                bad.append(f"תנועת ואקום {idx}: אין חיתוך מוגדר שלפניה"); continue
            a, b2 = ref[-1]["tool_p1"], ref[-1]["tool_p2"]
            axis = "y" if abs(a[1] - b2[1]) < abs(a[0] - b2[0]) else "x"
            val = a[1] if axis == "y" else a[0]
            shifted.append((axis, val, side_of(axis, val, mv["pick"]), mv["dx"], mv["dy"]))
            continue
        if kind != "חיתוך":
            continue
        c = cuts.get(idx)
        if not c or c["tool_p1"] is None:
            continue
        mid = ((c["tool_p1"][0] + c["tool_p2"][0]) / 2, (c["tool_p1"][1] + c["tool_p2"][1]) / 2)
        dx = sum(s[3] for s in shifted if side_of(s[0], s[1], mid) == s[2])
        dy = sum(s[4] for s in shifted if side_of(s[0], s[1], mid) == s[2])
        b = tag.get(idx)
        if not b:
            bad.append(f"חיתוך {idx} לא נמצא בקוד המכונה"); continue
        for key, pt in (("p1", c["tool_p1"]), ("p2", c["tool_p2"])):
            if abs(b[key + ".x0"] - pt[0] - dx) > 0.05 or abs(b[key + ".y0"] - pt[1] - dy) > 0.05:
                bad.append(f"חיתוך {idx}: {key} שונה")
    executed = {i for k, i in summary["order"] if k == "חיתוך" and cuts.get(i) and cuts[i]["tool_p1"]}
    for i in set(tag) - executed:
        bad.append(f"חיתוך {i} מופיע בקוד המכונה אבל לא מסומן לביצוע")
    for mv in summary["moves"]:
        b = spost.get(mv["id"])
        if not b:
            bad.append(f"תנועת ואקום {mv['id']} לא נמצאה בקוד המכונה"); continue
        for key, pt in (("p1", mv["pick"]), ("p2", mv["drop"])):
            if abs(b[key + ".x0"] - pt[0]) > 0.05 or abs(b[key + ".y0"] - pt[1]) > 0.05:
                bad.append(f"תנועת ואקום {mv['id']}: {key} שונה")
    return bad


if __name__ == "__main__":
    # python gmm_job.py job.dat          -> תקציר העבודה, ובדיקה מול קובץ ISO שלצידו אם קיים
    # python gmm_job.py job.dat --raw    -> כל העץ כפי שנשמר
    import os
    root, r = read_job(sys.argv[1])
    if "--raw" in sys.argv:
        print(json.dumps(to_plain(root), ensure_ascii=False, indent=1, default=str))
    else:
        s = summarize(root)
        iso = os.path.splitext(sys.argv[1])[0] + ".ISO"
        if os.path.exists(iso):
            s["iso_mismatches"] = iso_crosscheck(s, open(iso, errors="replace").read())
        print(json.dumps(s, ensure_ascii=False, indent=1, default=str))
    sys.stderr.write(f"נקראו {len(r.objects)} אובייקטים, עד בית {r.p} מתוך {len(r.d)}\n")
