# Normalize name tables of instantiated static fonts so PowerPoint sees one
# family ("Source Serif 4" / "Inter") with proper subfamilies.
import sys
from fontTools.ttLib import TTFont

JOBS = [
    ("SourceSerif4-Regular.ttf", "Source Serif 4", "Regular"),
    ("SourceSerif4-SemiBold.ttf", "Source Serif 4", "SemiBold"),
    ("SourceSerif4-Bold.ttf", "Source Serif 4", "Bold"),
    ("Inter-Regular.ttf", "Inter", "Regular"),
    ("Inter-Medium.ttf", "Inter", "Medium"),
    ("Inter-SemiBold.ttf", "Inter", "SemiBold"),
    ("Inter-Bold.ttf", "Inter", "Bold"),
]

for fname, fam, sub in JOBS:
    t = TTFont(fname)
    name = t["name"]
    # drop any existing records that carry the instancer's instance suffix or
    # are the IDs we rewrite.
    for rec in list(name.names):
        try:
            s = rec.toUnicode()
        except Exception:
            continue
        if "24pt" in s or "14pt" in s or rec.nameID in (1, 2, 4, 6, 16, 17):
            name.removeNames(nameID=rec.nameID, platformID=rec.platformID,
                             platEncID=rec.platEncID, langID=rec.langID)
    full = f"{fam} {sub}" if sub != "Regular" else fam
    ps = f"{fam.replace(' ', '')}-{sub}"
    for plat in ((3, 1, 0x409), (1, 0, 0)):
        pid, eid, lid = plat
        name.setName(fam, 1, pid, eid, lid)
        name.setName(sub, 2, pid, eid, lid)
        name.setName(full, 4, pid, eid, lid)
        name.setName(ps, 6, pid, eid, lid)
        name.setName(fam, 16, pid, eid, lid)
        name.setName(sub, 17, pid, eid, lid)
    t.save(fname)
    n = TTFont(fname)["name"]
    print(f"{fname}: fam={n.getDebugName(16)} sub={n.getDebugName(17)} ps={n.getDebugName(6)}")
