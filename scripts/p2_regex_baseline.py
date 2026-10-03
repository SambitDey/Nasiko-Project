import json, re
P = [
("code_generation",[r"(?i)\b(write|implement|create|build|generate)\b.{0,40}\b(function|script|code|class|program|api|endpoint|method|module)\b",r"(?i)\bwrite (a|an|the|me)\b.*\b(python|javascript|typescript|rust|golang|go|java|c\+\+|sql)\b",r"(?i)\bfix (this|the) bug\b",r"(?i)\brefactor\b",r"(?i)\badd error handling\b"]),
("code_understanding",[r"(?i)\bexplain (what|how|why)\b",r"(?i)\bwhat does (this|that|the) (function|code|script|class) do\b",r"(?i)\bhow does (this|that|the) (function|code|script|class) work\b",r"(?i)\bwalk me through (this|that) code\b",r"(?i)\bwhat is this code doing\b"]),
("technical_design",[r"(?i)\bhow should i design\b",r"(?i)\b(api|system|database|schema) design\b",r"(?i)\barchitecture\b",r"(?i)\bdesign (a|an|the) (system|api|service|schema|database)\b",r"(?i)\btrade-?offs?\b"]),
("analytical_reasoning",[r"(?i)\bcalculate\b",r"(?i)\bprobability\b",r"(?i)\bsolve\b",r"(?i)\bprove\b",r"(?i)\bproof\b",r"(?i)\bhow many\b",r"(?i)\bwhat'?s the (sum|product|average|result)\b",r"[0-9]+\s*[+\-*/]\s*[0-9]+"]),
("writing",[r"(?i)\bdraft\b",r"(?i)\bwrite (an?|the)\b.*\b(email|blog|article|essay|post|letter|story|poem)\b",r"(?i)\bcompose\b",r"(?i)\brewrite (this|that|the)\b",r"(?i)\bmake this sound\b"]),
("factual_lookup",[r"(?i)\bwhat is (the )?capital of\b",r"(?i)^\s*(who|what|when|where) (is|was|are|were)\b",r"(?i)\bdefine\b",r"(?i)\bhow many\b.*\b(are there|exist)\b"]),
]
P=[(rt,[re.compile(p) for p in ps]) for rt,ps in P]
def cls(t):
    best,bs="general",0
    for rt,ps in P:
        s=sum(1 for p in ps if p.search(t))
        if s>bs: best,bs=rt,s
    return best
d=json.load(open("/home/sdey/work-2026-10-03/reference/classifier-eval.json"))
ok=0
for e in d["examples"]:
    p=cls(e["query"]); ok+=p==e["request_type"]
    print(f'{e["id"]} {"OK " if p==e["request_type"] else "BAD"} pred={p:22} gold={e["request_type"]}')
print(f"regex accuracy (query only): {ok}/{len(d['examples'])}")
