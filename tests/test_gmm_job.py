# בדיקה מול עבודה שמורה אמיתית מהמכונה. הקבצים לא נשמרים במאגר (נתוני לקוח);
# מריצים עם GMM_SAMPLE=/path/to/job.dat (ו־job.ISO לצידו).
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gmm_job

dat = os.environ.get("GMM_SAMPLE")
if not dat:
    print("skip: GMM_SAMPLE לא מוגדר"); sys.exit(0)
root, r = gmm_job.read_job(dat)
assert r.p == len(r.d), "הקובץ לא נקרא עד הסוף"
s = gmm_job.summarize(root)
assert s["cuts"] and s["slab_thickness_mm"] > 0
iso = os.path.splitext(dat)[0] + ".ISO"
if os.path.exists(iso):
    bad = gmm_job.iso_crosscheck(s, open(iso, errors="replace").read())
    assert not bad, bad
print("ok")
