# Nasiko Buildathon — Analysis & Plan (2026-10-03)

Problem statement: `~/Downloads/5_6199233723485922027.md` (two tracks, pick one).
Upstream: https://github.com/Nasiko-Labs/nasiko (Rust workspace, edition 2024).
Reference clone + public eval sets: `reference/` (git-ignored).

## 1. What the repo is (the parts that matter)

`llm-router/` (`nasiko-llm-router`) is an OpenAI-compatible egress proxy for user agents:
JWT → resolve provider/model/key → **5-level model routing** → provider translation → usage row.

Request pipeline (`src/handlers/chat.rs::chat_core`):
1. `inbound.parse_chat` → canonical IR `ChatRequest` (`src/ir/chat.rs`, OpenAI shape, permissive `extra` maps)
2. `resolve_routed_request` → `routing::route_model` (Pinned → CacheHit → SalienceGate → **Classify** → Config → Default)
3. **compression seam** `compress::apply` (tool *results* only; `nasiko-compress` crate, fail-closed/deterministic)
4. **brevity seam** `brevity::apply` (appends a trailing system message; carve-outs; holdout control arm)
5. `fallback::execute_chat[_stream]` → providers (openai / anthropic / gemini / bedrock / openrouter)
6. `inbound.render_chat_response`

Routing classifier (`src/routing/classifier.rs`): regex vote count (`patterns.rs`) → `RequestType`
(7 labels) → Thompson-sampled `Tier` over learned `CellMap`. Classification only at fireable
boundaries (`cold_start`/`switch`, `boundary.rs`), sticky via `DecisionCache` on `continue`.

Existing precedent worth reusing:
- `routing/salience_classifier.rs` + `salience.rs`: hashed n-gram + logistic regression, weights
  trained **offline** and embedded as JSON, trait `SalienceGate` behind `Arc<dyn …>`, config in
  `config.rs` (`SALIENCE_GATE_ENABLED`), fail-safe direction documented. → the template for P2.
- `compress/` crate: pure library, never reads env, `Policy` built by caller, `#![deny(unwrap/expect/panic)]`.
  → the template for P1's `tool-compact/` crate.
- `brevity.rs`: how to inject a system message at the IR seam without disturbing author text. → P1 wiring.

Conventions (CONTRIBUTING.md): zero warnings on `cargo check`/`clippy`, `cargo fmt`, deps declared
once in root `Cargo.toml` (`dep.workspace = true`), hermetic unit tests, focused PRs.

Gaps / things to confirm with organizers:
- `llm-router/examples/classifier_eval.rs` is **not in the repo** (brief says it ships). Only `mint_token.rs`.
- P1: does the native baseline request include the same reference-date system message we add? Is
  the body tokenized pretty-printed or compact JSON? (Changes savings ~5–10 pts; we can't control it.)
- No competing `[compact-tools]` / `[classifier]` PRs exist yet upstream.

## 2. Track comparison

| | P1 compact-tools | P2 classifier |
|---|---|---|
| Scoring | deterministic screening + token % (automatic) + live adherence | accuracy vs regex on adversarial private set, ECE, latency |
| Risk | live models not following the format | private set is deliberately hard; small model may not beat regex convincingly; labelling data eats hours |
| Isolation | new crate, router untouched unless bonus wiring | trait refactor inside router hot path + config + timeout/fallback + sticky tests |
| Measurable today | yes — I measured it (below) | only on 10 public cases + our own labels |

**Measured on public set (o200k_base, full request body):** native tools 952 tokens; prototype compact
format 471 (**−50.5%**) keeping all descriptions, 402 (**−57.8%**) dropping redundant ones; floor with
no tools at all is 185 (max possible −80.6%). Pitfall found: non-ASCII separators (e.g. `—`)
get `\uXXXX`-escaped in JSON and halve the savings → grammar must be ASCII-only and avoid `"`.

## 3. Recommendation: **P1 — compact tool schemas**

Reasons: objectively scorable and deterministic; target (≥30%) already demonstrably beaten with
headroom to trade back for adherence; self-contained new crate = cleaner "merge-ready" story
(40% of score); no training data to build; the hard parts (streaming decoder, escaping, fail-closed
validation) are well-defined engineering we can test exhaustively.

Choose P2 instead only if you have a live LLM API key handy for a hosted classifier *and* want an
ML-flavoured demo; the plan would be: `RequestClassifier` trait + regex impl + embedded
hashed-n-gram multinomial LR (salience pattern, trained offline in Python) + optional hosted backend.

## 4. P1 design

**Grammar** — keep the brief's `<<call NAME {json}>>` verbatim (no conversion of decoder cases needed;
models write JSON args reliably):
```
output   := (text | call)*
call     := "<<call" WS+ NAME WS* JSON_OBJECT WS* ">>"
NAME     := [A-Za-z0-9_.-]+   (must be in the tool list)
```
JSON_OBJECT is consumed with a real JSON scanner (string/escape aware), so `>>` inside strings is safe.

**Compact definitions** (ASCII, one line per tool, descriptions kept where they disambiguate):
```
create_calendar_event(title:str # Event title, start:datetime, duration_min?:int # minutes,
  attendees?:[str] # emails, visibility?:public|private): Create an event in the user's calendar.
```
Type map: `str int num bool datetime(date-time) date [T] {k:T,...}(nested object) a|b|c (enum)`,
`?` = optional. Unsupported (→ bypass, `compacted:false`): `$ref`, `oneOf/anyOf/allOf`,
`patternProperties`, `additionalProperties` schemas, `const`, numeric/string constraints we can't
render, nullable unions. `decode_tools` reconstructs the schema from the compact form.

**Crate `tool-compact/` (`nasiko-tool-compact`)** — pure, no IO/env, no router dep:
- `ToolDef`/`ToolCall` own types; `encode_tools`, `decode_tools`, `decode_calls`, `StreamDecoder`
- `validate(args, schema)`: required, types (int vs number strict), enums, nested objects/arrays,
  unknown keys rejected (fail closed) → `Error::{UnknownTool, InvalidArguments, Malformed}`
- `StreamDecoder::push(chunk) -> Vec<Event{Text|Call|Error}>`, holds back any suffix that could be a
  prefix of `<<call`; `finish()` flushes / errors on unterminated call
- unit tests + proptest (random split points ≡ whole-string decode; roundtrip encode→render→decode)

**Example `llm-router/examples/compact_tools_eval.rs`**: reads `EVAL_SET`, writes `OUT` JSONL
(`compact_request`, `compacted`, `rendered_calls`, `roundtrip_calls`; `decoded` for decoder cases);
live mode when `PROVIDER_BASE_URL`+`MODEL` set (temperature 0, adds `raw_output`, `live_calls`).
`tiktoken-rs` pinned as dev-dependency only, prints local savings to stderr.

**Bonus wiring**: `TOOL_COMPACT_ENABLED` (default off) in `config.rs`; seam after brevity in
`chat_core`; OpenAI non-streaming first, bypass when `tool_choice` forces a tool or history has
prior tool calls we can't re-render; byte-identical-when-off test.

## 5. Day schedule (approx.)

1. Fork `Nasiko-Labs/nasiko` → `SambitDey/nasiko`, branch `compact-tools`; confirm build/tests green.
2. Crate skeleton + types + encoder + `decode_tools` + tests.
3. Decoder + validator + `StreamDecoder` + escaping/split/property tests.
4. Eval example (offline), run on public set twice, diff for determinism.
5. Live mode; test against 2 models (needs an OpenAI-compatible key, e.g. OpenRouter); tune
   instruction wording for adherence vs tokens.
6. Optional router wiring + byte-identical test.
7. `cargo fmt`, clippy zero-warn, docs (`tool-compact/README.md` with grammar), PR `[compact-tools] …`
   with template sections; demo script.

Commit/push cadence: notes & eval outputs to this repo; code to the fork branch.
