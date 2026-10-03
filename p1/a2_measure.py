"""Candidate A2: one param per line, description to end of line (unambiguous, comma-safe)."""
import json, tiktoken
enc = tiktoken.get_encoding("o200k_base")
T = lambda o: len(enc.encode(json.dumps(o, ensure_ascii=False, separators=(",", ":"))))
FMT = {"date-time": "datetime", "date": "date", "email": "email", "uri": "uri"}
SYS = "Today is 2026-10-02, timezone Asia/Kolkata."
CALL = "Call a tool by replying <<call NAME {JSON args}>> (one per call); otherwise answer normally."


def ty(s):
    if "enum" in s:
        return "|".join(map(str, s["enum"]))
    t = s.get("type")
    if t == "string":
        return FMT.get(s.get("format"), "str")
    if t == "array":
        return "[" + ty(s.get("items", {})) + "]"
    if t == "object":
        return "{}"
    return {"integer": "int", "number": "num", "boolean": "bool"}[t]


def lines(s, ind):
    props, req = s.get("properties", {}), set(s.get("required", []))
    out = []
    for k in sorted(props, key=lambda k: (k not in req, k)):
        p = props[k]
        d = p.get("description")
        out.append(f"{ind}{k}{'' if k in req else '?'}:{ty(p)}" + (f" # {d}" if d else ""))
        items = p.get("items", {}) if p.get("type") == "array" else {}
        inner = p if p.get("type") == "object" else items if items.get("type") == "object" else None
        if inner:
            out += lines(inner, ind + " ")
    return out


def tool(t):
    f = t["function"]
    d = f.get("description")
    return "\n".join([f["name"] + (f" # {d}" if d else "")] + lines(f.get("parameters", {}), " "))


def block(tools):
    return "Tools (? = optional):\n" + "\n".join(tool(t) for t in tools) + "\n" + CALL


def run(name, by, cases):
    nb = cb = ns = cs = 0
    for c in cases:
        tools = [by[n] for n in c["tools"]]
        msgs = [{"role": "system", "content": SYS}] + c["messages"]
        nb += T({"model": "m", "messages": msgs, "tools": tools})
        ns += T(tools)
        b = block(tools)
        cb += T({"model": "m", "messages": [{"role": "system", "content": SYS + "\n" + b}] + c["messages"]})
        cs += len(enc.encode(json.dumps(b)))
    print(f"{name}: full {nb}->{cb} ({1-cb/nb:.1%})  schema {ns}->{cs} ({1-cs/ns:.1%})")


pub = json.load(open("../reference/compact-tools-eval.json"))
ex = json.load(open("extra_tools.json"))
run("A2 public", {t["function"]["name"]: t for t in pub["tools"]}, pub["cases"])
run("A2 extra ", {t["function"]["name"]: t for t in ex},
    [{"tools": [t["function"]["name"] for t in ex], "messages": [{"role": "user", "content": "Help me."}]}])
print(block(pub["tools"]))
print(tool(ex[0]))
