#!/usr/bin/env bash
# Screen-recording demo for nasiko-tool-compact (about 90 s). Press Enter to go to the next scene.
#
#   bash demo.sh --prep   build once before recording (offline, no network)
#   bash demo.sh          run the demo; scene 3 sends 3 requests to the live model
#
# The live scene reads ~/.config/nasiko/live.env and never prints it.
# DEMO_MODEL picks the live model (default anthropic/claude-sonnet-5.5).
set -uo pipefail

FORK="${FORK:-$HOME/work-2026-10-03/fork}"
EVAL_SET="${EVAL_SET:-$HOME/work-2026-10-03/reference/compact-tools-eval.json}"
LIVE_ENV="${LIVE_ENV:-$HOME/.config/nasiko/live.env}"
DEMO_MODEL="${DEMO_MODEL:-anthropic/claude-sonnet-5.5}"
PR_URL="https://github.com/Nasiko-Labs/nasiko/pull/315"

C=$'\e[1;36m' G=$'\e[1;32m' R=$'\e[1;31m' Y=$'\e[1;33m' B=$'\e[1m' D=$'\e[2m' N=$'\e[0m'

scene() { clear; printf '%s\n\n' "${C}$*${N}"; }
pause() { printf '\n%s' "${D}[Enter]${N}"; read -r _; }

# Offline: unset the live variables so an exported key can never turn this into a paid run.
eval_offline() {
    (cd "$FORK" && env -u PROVIDER_BASE_URL -u MODEL -u PROVIDER_API_KEY \
        EVAL_SET="$EVAL_SET" OUT="$1" \
        cargo run -q --release -p nasiko-llm-router --example compact_tools_eval)
}

# Live: load the key file in a subshell only; its contents are never echoed.
eval_live() {
    (set -a; . "$LIVE_ENV"; set +a
     export MODEL="$DEMO_MODEL"
     cd "$FORK" && EVAL_SET="$EVAL_SET" OUT="$1" \
        cargo run -q --release -p nasiko-llm-router --example compact_tools_eval) 2>/dev/null
}

# Native schemas (part "native") or the compact block (part "compact") for one case.
show_compare() {
    python3 - "$1" "$2" "$3" "$4" <<'PY'
import json, re, sys
out, eval_set, err, part = sys.argv[1:]
case = "ct-002"
data = json.load(open(eval_set))
tools = {t["function"]["name"]: t for t in data["tools"]}
names = next(c["tools"] for c in data["cases"] if c["id"] == case)
m = re.search(rf"{case}: baseline (\d+) compact (\d+)", open(err).read())
base, comp = m.groups() if m else ("?", "?")
line = next(json.loads(l) for l in open(out) if f'"{case}"' in l)
block = line["compact_request"]["messages"][0]["content"].split("\n\n", 1)[1]
if part == "native":
    print(f"\x1b[1;31mNative tool schemas sent today\x1b[0m  ({case} request: {base} tokens)\n")
    print(json.dumps([tools[n] for n in names], indent=1))
else:
    print(f"\x1b[1;32mSame two tools, compacted by nasiko-tool-compact\x1b[0m  ({case} request: {comp} tokens)\n")
    print(block)
PY
}

# What the live model wrote, and what the decoder made of it.
show_live() {
    python3 - "$1" "$2" <<'PY'
import json, sys
out, eval_set = sys.argv[1:]
asks = {c["id"]: c["messages"][-1]["content"] for c in json.load(open(eval_set))["cases"]}
for l in open(out):
    d = json.loads(l)
    if "raw_output" not in d:
        continue
    print(f"\x1b[1m{d['id']}\x1b[0m  user: \x1b[2m{asks[d['id']]}\x1b[0m")
    live = d["live_calls"]
    if "error" in live:
        print(f"  \x1b[1;31m✗ {live['error']}\x1b[0m {str(live.get('detail', ''))[:160]}\n")
        continue
    raw = d["raw_output"] or ""
    print("  model: " + raw.replace("\n", "\n         ")[:600])
    calls = live["calls"]
    if calls:
        names = ", ".join(c["name"] for c in calls)
        print(f"  \x1b[1;32m✓ {len(calls)} valid call(s): {names}\x1b[0m\n")
    else:
        print("  \x1b[1;32m✓ plain text, no call\x1b[0m\n")
PY
}

# Decoder cases: what was streamed in, and what came out.
show_decoder() {
    python3 - "$1" "$2" <<'PY'
import json, sys
out, eval_set = sys.argv[1:]
cases = {c["id"]: c for c in json.load(open(eval_set))["decoder_cases"]}
for l in open(out):
    d = json.loads(l)
    if d["id"] not in cases:
        continue
    c = cases[d["id"]]
    print(f"\x1b[1m{d['id']}\x1b[0m  {c['note']}")
    print(f"  chunks: \x1b[2m{json.dumps(c['chunks'])[:110]}\x1b[0m")
    r = d["decoded"]
    if "error" in r:
        print(f"  \x1b[1;31m✗ rejected: {r['error']}\x1b[0m\n")
    else:
        print(f"  \x1b[1;32m✓ {len(r['calls'])} valid call(s)\x1b[0m\n")
PY
}

main() {
    if [[ "${1:-}" == "--prep" ]]; then
        (cd "$FORK" && cargo build -q --release -p nasiko-llm-router --example compact_tools_eval) \
            && echo "Built. Start recording, then run: bash $0"
        return
    fi
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    if ! eval_offline "$tmp/offline.jsonl" 2>"$tmp/offline.err"; then
        echo "Offline eval failed:"; cat "$tmp/offline.err"; return 1
    fi

    scene "1 / 5  The problem: every request resends every tool's full JSON schema"
    show_compare "$tmp/offline.jsonl" "$EVAL_SET" "$tmp/offline.err" native
    pause
    scene "1 / 5  The fix: the same tools in a compact form"
    show_compare "$tmp/offline.jsonl" "$EVAL_SET" "$tmp/offline.err" compact
    pause

    scene "2 / 5  Token savings: offline eval, deterministic (o200k_base)"
    echo "\$ cargo run --release -p nasiko-llm-router --example compact_tools_eval"
    eval_offline "$tmp/run.jsonl"
    printf '\n%s\n' "${G}On the 47 real tool definitions of Nasiko's own agents: 32.2% saved, all 9 tool sets compacted.${N}"
    pause

    scene "3 / 5  Live model follows the format: $DEMO_MODEL"
    if [[ -f "$LIVE_ENV" ]]; then
        eval_live "$tmp/live.jsonl"
        show_live "$tmp/live.jsonl" "$EVAL_SET"
    else
        echo "${Y}No $LIVE_ENV, skipping the live scene.${N}"
    fi
    pause

    scene "4 / 5  Strict decoder: split chunks and '>>' inside strings work; bad calls are rejected"
    show_decoder "$tmp/offline.jsonl" "$EVAL_SET"
    pause

    scene "5 / 5  In Nasiko's LLM router"
    cat <<EOF
  ${B}TOKEN_COMPACT_TOOLS=1${N}   opt-in; off by default, requests byte-identical when off
  ${B}Invalid reply${N}           router re-sends the request natively before the client sees anything
  ${B}Unsupported schema${N}      sent natively; never approximated
  ${B}Tests${N}                   411 passing (crate, router, end-to-end); fmt + clippy clean

  ${C}${PR_URL}${N}
EOF
    pause
}

# Allow `source demo.sh` (for testing the helpers) without running the demo.
[[ "${BASH_SOURCE[0]}" == "$0" ]] && main "$@"
