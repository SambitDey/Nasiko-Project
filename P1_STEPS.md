# P1 compact-tools — step plan (one step at a time, commit+push after each)

1. Fork + branch: fork Nasiko-Labs/nasiko → SambitDey/nasiko, branch `compact-tools`; build + existing tests green.
2. Crate skeleton `tool-compact/`: Cargo.toml, workspace member, own `ToolDef`/`ToolCall`/`Error` types. Compiles.
3. Encoder: JSON Schema → compact ASCII lines + call instructions; detect unsupported features → bypass. Unit tests.
4. `decode_tools`: compact → schema; round-trip test (encode→decode == original).
5. Validator: required/types/enums/nested/arrays, unknown keys rejected. Unit tests.
6. `decode_calls`: parse `<<call name {json}>>` (string-aware, `>>` in strings), text before/after, multiple calls; errors `unknown_tool` / `invalid_arguments`.
7. `StreamDecoder`: chunk-by-chunk, holds back partial markers; property test (random splits == whole decode).
8. Eval example `llm-router/examples/compact_tools_eval.rs` (offline): reads EVAL_SET, writes OUT JSONL; run twice, diff; tiktoken-rs savings report.
9. Tune format for tokens (measure, keep ≥30%, ASCII only).
10. Live mode (PROVIDER_BASE_URL + MODEL): needs API key; test 2 models, tune instructions.
11. (Bonus) Router wiring behind `TOOL_COMPACT_ENABLED` (off by default), byte-identical test, native fallback on decode failure.
12. fmt + clippy zero warnings, README/grammar doc, PR `[compact-tools] …` with template.
