import subprocess, re, sys, os
files = subprocess.check_output(["git","ls-files"], text=True).split("\n")
out = []
skip = re.compile(r'\.(lock|zip|png|sum)$|package-lock|\.sync-manifest|salience_weights|schema\.gen\.ts|\.openapi\.json')
for f in filter(None, files):
    if skip.search(f):
        out.append(f"### {f}  [binary/generated, skipped]"); continue
    try: src = open(f, encoding="utf-8").read()
    except Exception: out.append(f"### {f}  [unreadable]"); continue
    lines = src.split("\n"); n = len(lines)
    ext = f.rsplit(".",1)[-1]
    keep = []
    if ext == "rs":
        keep = [l for l in lines if l.lstrip().startswith("//!")][:25]
        keep += [l.strip() for l in lines if re.match(r'\s*pub(\(crate\))? (async )?(fn|struct|enum|trait|type|const|mod) ', l)][:25]
    elif ext == "md":
        keep = [l for l in lines if l.startswith("#")][:30]
    elif ext in ("ts","tsx","js"):
        keep = [l for l in lines[:6] if l.strip().startswith(("//","/*","*"))] + [l.strip() for l in lines if l.startswith("export ")][:12]
    elif ext == "py":
        keep = [l for l in lines if re.match(r'(class |def |async def )', l)][:15]
    elif ext in ("toml","yml","yaml","sql","example","txt","html","mod","gitignore") or "/" not in f:
        keep = lines[:15]
    elif ext == "json":
        keep = lines[:5]
    else:
        keep = lines[:8]
    out.append(f"### {f}  ({n} lines)\n" + "\n".join(keep))
open(sys.argv[1],"w").write("\n".join(out))
