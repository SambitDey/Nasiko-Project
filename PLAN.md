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

---

## 6. Second pass (2026-10-03, from the full zip) — innovative directions

The zip (`Nasiko-Labs-nasiko-v1.0.0-1815-g70b4e74.zip`) is byte-identical to the GitHub clone at
`70b4e74` (only diff: `Cargo.lock`, which upstream has let go stale — `cargo build` rewrites it; keep
unrelated lockfile churn out of the PR). No hidden code; the new ideas come from reading the
token-optimisation stack end-to-end (`savings.rs`, `nasiko-savings`, `compress/`, `brevity.rs`,
`inbound/responses.rs`, `mcp-gateway`).

### Measured format variants (o200k, public set; scorer's JSON style unknown → both shown)

| format | compact-JSON body | pretty body |
|---|---|---|
| brief's arrow style, all descriptions | −36.6% | −48.1% |
| TypeScript-style signature, all descriptions | −35.3% | −47.1% |
| lean (redundant descriptions pruned) | −56.6% | −63.6% |

→ TS-style costs ~the same tokens as the brief's style but is the shape models have seen most
(adherence upside for free). Description pruning is where the next 20 points are.

### P1 ideas, ranked by (score impact × uniqueness) / effort

1. **Lossless-by-construction encoder with a self-checking bypass.** `encode_tools` immediately runs
   `decode_tools` on its own output and bypasses compaction (`compacted:false`) for any tool whose
   schema doesn't round-trip exactly. "Schema kept" becomes a runtime invariant, not a hope —
   unsupported features are detected by construction rather than by an allow-list that can drift.
2. **Information-preserving description pruning (deterministic).** Drop a description only when it adds
   nothing: every content word already appears in the tool/param name or is implied by the type
   (`"Start time, ISO 8601"` on a `datetime` → dropped; `"Duration in minutes"` → keeps `minutes`
   because the unit disambiguates). Two levels: `Lossless` (default) and `Pruned`; report both.
3. **Shared type hoisting for real catalogs.** MCP/Composio tool sets repeat sub-schemas (address,
   pagination, attendee lists). Hoist identical nested objects into named types once
   (`type Attendee = {...}`) and reference them. Little effect on the 2-tool public set, large on
   real 20–50-tool catalogs and likely on the private set; a genuinely different idea.
4. **Fall back to native on decode failure, invisible to the client** (router wiring). If the compact
   reply fails validation, re-issue the same request with native tools once. Fail-closed for
   correctness *and* client never sees a compaction-induced error; costs tokens only on failure.
   Recorded as `compact_tools.fallback` in `token_usage.metadata`. Most "production-minded" story.
5. **Cache-prefix stability.** Following `compress.rs`'s own reasoning: the compact block is a pure
   function of the tool list, placed as the first system message, byte-identical every turn, so it
   keeps provider prompt caching working. Test: same tools → identical bytes across turns.
6. **Never-grows + idempotent invariants**, mirroring `nasiko-compress`: if compact form isn't
   smaller for a request (tiny tool, huge instruction) → bypass. Property-tested.
7. **Telemetry in the house style.** `to_metadata()` block like `brevity.rs` (`applied`, `skipped`
   reason, bytes before/after, decode outcome) so the existing dashboard pipeline can pick it up.
   Stay inside `llm-router/` — the `savings` crate's `Layer` enum is CHECK-constrained by a
   migration and outside the allowed scope; propose it as a follow-up in the PR.
8. **Zero-latency streaming.** `StreamDecoder` holds back only the longest suffix that could begin
   `<<call` (≤6 bytes), so plain answers stream with no added latency; calls are emitted as standard
   `ToolCallDelta`s the moment `>>` closes.
9. **Differential property tests.** Random schemas + random valid args: encode→decode_tools ≡
   original; render→random chunk split→StreamDecoder ≡ whole-string decode; random mutations
   (drop required key, wrong enum, wrong type) → always an error, never a call.
10. **Adherence tuning loop in live mode.** Small matrix (format × instruction wording × 2 providers),
    pick the variant with best decode-success at acceptable token cost; report the matrix honestly
    in the PR (judges reward negative results too).

### P2 ideas (if switching tracks)

1. **Confidence cascade:** regex (µs) → embedded hashed-n-gram multinomial LR reusing the salience
   feature engine (µs, no network) → optional hosted LLM only when confidence < τ. Below a floor →
   safe default (`General` + current tier), counted as fallback, not error.
2. **Temperature-scaled calibration** fitted on our validation split → low ECE, which the scorer penalises.
3. **Instruction-focus features** for the near-miss cases (pub-08 "do not redesign… just change TODO"):
   weight the clause after `just/only/simply` and down-weight negated spans.
4. **Structural complexity estimator:** count constraints (`do not`, enumerations, "and"-joined
   deliverables), context length, code presence, entities → ordinal 1–5; feed complexity into the
   tier prior without changing the bandit key (keeps learned cells valid).
5. **Data pipeline:** LLM-generated paraphrases + adversarial near-misses per label, MinHash dedup
   across splits, documented rubric.

### Updated recommendation
Still **P1**. Core: ideas 1, 2, 5, 6, 8, 9 (all in-crate, deterministic). Differentiators if time:
4 (native fallback wiring) and 3 (type hoisting). Ask organizers how the body is serialized for
token counting and whether descriptions must survive verbatim for the "schema kept" check — that
decides whether `Pruned` can be the eval default.

---

## 7. Full-repo pass (all 1,761 tracked files) + "quick setup"

**Quick setup.** There is no quicksetup file in the repo, the zip, the brief or ~/Downloads. The
closest thing is README §"Quick Start: Docker only" (`cp .env.example .env` → set
`SECRETS_ENCRYPTION_KEY`, `JWT_SECRET`, `AGENT_JWT_SECRET`, admin creds, `OPENAI_API_KEY` →
`docker compose up -d` → http://localhost:8080). **We don't need it for either track:** the
graders run `cargo run --release -p nasiko-llm-router --example …`, which needs no Postgres,
Redis, Docker or UI. Only worth doing for a live demo of router wiring (bonus).

**How the pass was done.** `scripts/build_repo_digest.py` extracts, for every tracked file, its
size, module docs (`//!`), public items, headings, exports, or first lines; the digest
(`notes/repo_digest.txt`, ~16k lines) was read end to end. Every file relevant to the tracks was
then read in full: the whole `llm-router` request path, providers, config, brevity/compress/savings
layers, routing (classifier, patterns, salience gate + model, boundary, cache, cells, registry),
`nasiko-compress`, `nasiko-savings`, plus the migrations touching token savings.

**Map of the repo (what each area is):**
- `server/` control plane (Axum): auth, agents CRUD/upload/build worker, A2A dispatch, HITL, MCP
  routes, observability/FinOps/savings APIs; mounts `llm-router` in-process.
- `llm-router/` egress proxy (our scope): inbound parsers (OpenAI/Anthropic/Gemini/Responses) →
  IR → resolver → 5-level routing → compress → brevity → providers (+fallback/param-fix retry).
- `orchestrator/`, `react-agent/` agent selection, MAF workflows, PACMS context selection.
- `mcp-gateway/` tool catalog aggregation, permissions, BM25/semantic tool search.
- `compress/`, `savings/`, `pricing/` token-optimization and cost engines.
- `agents/` ~30 example agents (Rust/Go/Python) with **real OpenAI tool definitions**
  (`agents/*/src/tools.rs`, `tools.go`) → ready-made realistic corpus for P1 extra eval cases.
- `ui/` React dashboard (TokenOps, router, chat, MCP pages); `migrations/` 53 SQL files.

**New facts that change the plan:**
1. `providers/fallback.rs` already does patch-and-retry on provider rejection (`try_fix_param`)
   → P1's native-fallback-on-decode-failure has a direct in-house precedent.
2. Every token layer follows one pattern: per-agent switch (`compress_enabled`) + fleet kill
   switch + `Skipped` reasons → `to_metadata()` in `token_usage.metadata`. P1 wiring should copy it.
3. The salience model is the ML template for P2: LLM-labelled data (provenance carries a
   `gate_prompt_sha256`), Python-trained hashed n-gram LR with **Platt calibration**, weights
   embedded as JSON, feature-engine parity checked. Training scripts aren't in the public repo.
4. **Regex baseline on the P2 public set: 3/10** (`scripts/p2_regex_baseline.py`). Failures are
   exactly the brief's near-misses: "Explain what … API returns" → code_understanding (gold:
   technical_design); "Fix typo…", "Implement a parser…", "Summarize…" → general.
5. `classifier_eval.rs` is still absent upstream (P2 would create it from scratch).
6. Committed `Cargo.lock` is stale; any build rewrites it — keep unrelated churn out of the PR.

**Track call, revisited.** P1 stays the lower-risk pick (deterministic scoring, isolated crate).
P2 is now a credible alternative: a 30% baseline is easy to beat visibly, and the repo already
has the exact pattern (embedded calibrated LR) to copy, but it needs an LLM API key for labelling
and more surface area (trait, config, timeout fallback, sticky tests, ECE). Decide by: do we have
an API key now (P2 needs one more than P1) and does the team prefer ML or systems work?
