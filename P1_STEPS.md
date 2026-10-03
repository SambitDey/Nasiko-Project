# P1 compact-tools — step plan v2 (after audit). One step at a time, commit+push each.

Design: see P1_ARCHITECTURE.md.

0. Contract frozen (P1_ARCHITECTURE.md). ✅ (this commit)
   Step 1 ✅ A2 chosen. Step 2 ✅ (live test run by user; grammar A2 frozen).
   Step 3 ✅ fork SambitDey/nasiko, branch compact-tools @ upstream 796211c2; llm-router+compress tests green (473 passed).
1. Grammar candidates A/B/C: Python prototype renders public set + repo agent tools; o200k token table.
2. Tiny live adherence test of A/B/C (needs API key; else choose on tokens + priors). Freeze grammar.
3. Fork SambitDey/nasiko, branch `compact-tools`; build + tests green.
4. Crate skeleton `tool-compact/` + Schema AST + Normalizer + capability check (+ tests). ✅
5. Compiler/renderer + `decode_tools` parser + self-check; I1, I2, I3, I7 tests. ✅ (closed object = `{}!`, top-level `NAME!`, no params `NAME()`)
6. Validator (contract rules) + tests. ✅
7. Call parser: outer scanner + JSON end-offset scanner; `decode_calls`; I4, I5 + fuzz cases. ✅ (public dc-001..005 pass)
8. `StreamDecoder` (bounded holdback); I6 property test (random splits). ✅ (public dc chunked pass)
9. Eval example `compact_tools_eval.rs` (offline, deterministic, extended metrics); run twice + diff. ✅ (3/3 rt, 5/5 dc, 32.1% saved, runs identical)
10. Live mode in eval; measure adherence on 2+ model families. ✅ plumbing (mock-tested); real-model run needs user key
11. (Bonus) Router wiring, flag off by default; I9 byte-identical test; non-streaming native retry (I10). ✅
12. fmt + clippy, README (grammar + support matrix), PR `[compact-tools] …`. ✅ (fmt + clippy clean; README on both branches; PRs #302 safe, #315 aggressive 46.4%; CI pass; demo: scripts/demo.sh)
Later/not v1: BALANCED profile, type hoisting, per-tool fallback, min/max constraints.
