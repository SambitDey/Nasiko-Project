"""Step 1: render grammar candidates A/B/C and count o200k tokens (full request + schema only)."""
import json, sys, tiktoken
enc = tiktoken.get_encoding("o200k_base")
T = lambda o: len(enc.encode(json.dumps(o, ensure_ascii=False, separators=(",", ":"))))
FMT = {"date-time": "datetime", "date": "date", "email": "email", "uri": "uri"}
SYS = "Today is 2026-10-02, timezone Asia/Kolkata."
CALL = "To call a tool, reply with <<call NAME {JSON args}>> (one per call); otherwise answer normally."

def ty(s, style):
    t = s.get("type")
    if "enum" in s:
        lits = [str(v) for v in s["enum"]]
        return {"A": "|".join(lits), "B": "(" + "|".join(lits) + ")", "C": "|".join(f"'{v}'" for v in lits)}[style]
    if t == "string":
        f = FMT.get(s.get("format"))
        return f or ("string" if style == "C" else "str")
    if t == "integer": return "integer" if style == "C" else "int"
    if t == "number": return "number" if style == "C" else "num"
    if t == "boolean": return "boolean" if style == "C" else "bool"
    if t == "array":
        inner = ty(s.get("items", {}), style)
        return f"{inner}[]" if style == "C" else f"[{inner}]"
    if t == "object": return obj(s, style)
    raise ValueError(f"unsupported {s}")

def fields(s, style):
    props, req = s.get("properties", {}), set(s.get("required", []))
    order = sorted(props, key=lambda k: (k not in req, k))
    out = []
    for k in order:
        p, r, d = props[k], k in req, props[k].get("description")
        t = ty(p, style)
        if style == "A": f = f"{k}{'' if r else '?'}:{t}" + (f" # {d}" if d else "")
        elif style == "B": f = f"{k}:{t}{'!' if r else '?'}" + (f' @"{d}"' if d else "")
        else: f = f"{k}{'' if r else '?'}:{t}" + (f" /*{d}*/" if d else "")
        out.append(f)
    return out

def obj(s, style):
    sep = "; " if style == "C" else ", "
    return "{" + sep.join(fields(s, style)) + "}"

def tool(t, style):
    f = t["function"]; n, d, p = f["name"], f.get("description"), f.get("parameters", {"type": "object"})
    body = ", ".join(fields(p, style))
    if style == "A": return f"{n}({body})" + (f" - {d}" if d else "")
    if style == "B": return f"{n}({body})" + (f' @"{d}"' if d else "")
    return (f"// {d}\n" if d else "") + f"{n}(a:{{{'; '.join(fields(p, style))}}})"

def block(tools, style):
    head = {"A": "Tools (? = optional):", "B": "Tools (! required, ? optional):", "C": "Tools:"}[style]
    return head + "\n" + "\n".join(tool(t, style) for t in tools) + "\n" + CALL

def run(name, tools_by_name, cases):
    rows = {}
    for style in "ABC":
        nb = ns = cb = cs = 0
        for c in cases:
            tools = [tools_by_name[n] for n in c["tools"]]
            msgs = [{"role": "system", "content": SYS}] + c["messages"]
            nb += T({"model": "m", "messages": msgs, "tools": tools}); ns += T(tools)
            blk = block(tools, style)
            cb += T({"model": "m", "messages": [{"role": "system", "content": SYS + "\n" + blk}] + c["messages"]})
            cs += len(enc.encode(json.dumps(blk)))
        rows[style] = (nb, cb, ns, cs)
    print(f"\n== {name}")
    print("style full_native full_compact full_saving schema_native schema_compact schema_saving")
    for s, (nb, cb, ns, cs) in rows.items():
        print(f"{s}     {nb:11} {cb:12} {1-cb/nb:10.1%} {ns:13} {cs:14} {1-cs/ns:12.1%}")

pub = json.load(open(sys.argv[1]))
run("public set", {t["function"]["name"]: t for t in pub["tools"]}, pub["cases"])
extra = json.load(open(sys.argv[2]))
run("extra realistic tools", {t["function"]["name"]: t for t in extra}, [{"tools": [t["function"]["name"] for t in extra], "messages": [{"role": "user", "content": "Help me."}]}])
for s in "ABC": print(f"\n--- {s}\n" + block(pub["tools"], s))
