# P1 compact-tools — final architecture (after audit, 2026-10-03)

## Audit verdict (agreed / changed)
Agreed and adopted: schema AST, canonical-equivalence invariant, formal grammar, explicit
support matrix, whole-request fallback, no description pruning in v1, two-layer scanner
(outer state machine + JSON scanner that reports the end offset), fuzzing, richer eval
output, "bounded latency" (not "zero"), "cache-friendly" (not "keeps caching"), retry only
before any client-visible output, grammar candidates benchmarked before freezing.

Where we deviate from the audit:
- **Keep `decode_tools`.** The brief explicitly recommends it ("lets us check schema
  survived"). It also powers the self-check bypass.
- **The crate keeps its own `ToolDef`/`ToolCall`** (the brief requires it); `parameters`
  stays `serde_json::Value` at the API boundary and is converted to an internal `Schema`
  AST inside the crate. One schema system, no router dependency.
- **Property order = required first, then optional, each alphabetical.** New catch: the
  router parses with `serde_json` *without* `preserve_order`, so the original order is
  already lost. Turning on `preserve_order` in our crate would enable it workspace-wide
  (Cargo feature unification) and change router serialization → breaks "byte-identical
  when off". So the order is deterministic and independent of input order.
- **Model coverage:** as many families as our API key(s) allow; at least 2.

## Contract (Step 0: frozen before code)
- **Input:** OpenAI function tools. `parameters` must be `type: object`.
- **Supported → compact:** string, integer, number, boolean, array(items), object
  (properties/required, nested), enum (string/number literals), format date | date-time |
  email | uri, descriptions (tool + param, verbatim), `additionalProperties:false` or absent.
- **Fallback (whole request native, `compacted:false`):** anyOf/oneOf/allOf/not, $ref/$defs,
  pattern, patternProperties, schema-valued or `true` additionalProperties *when it changes
  validation*, nullable/type arrays, const, default, min*/max*, uniqueItems, examples,
  if/then/else, any unknown keyword. (min/max may move to "compact" later if grammar stays clean.)
- **Ignore:** nothing (except `title`, which we preserve or fall back on; decided in Step 1).
- **Equivalence:** `canon(original) == canon(decode_tools(encode_tools(original)))`, with
  canon = sorted keys, sorted `required`, descriptions verbatim. Checked at runtime on every
  encode; any mismatch → native fallback.
- **Validation:** int rejects 1.0 and "1"; number accepts 1; `?` = optional, never nullable;
  unknown keys rejected only where the schema forbids them (absent additionalProperties = allowed
  by JSON Schema → we treat absent as allowed and validate known keys only); enums exact match.
- **Errors:** `unknown_tool`, `invalid_arguments`, `malformed` (bad syntax/JSON, unterminated).
  No malformed input may ever produce a ToolCall.
- **Library never reads env, never does IO, never tokenizes.** `never-grows` uses bytes;
  tiktoken lives only in the eval example (dev-dependency).

## Pipeline
OpenAI ToolDefs → Normalizer (JSON → Schema AST) → Capability check → [supported] Compiler
→ canonical render + self-check (decode_tools) → prompt block | [unsupported/self-check
fail/not smaller] native.
Model output → outer scanner (TEXT / MAYBE_MARKER / NAME / ARGS / END) → JSON scanner
(gives exact end offset) → require `>>` → validator → ToolCall | Error.

## Invariants (each has a test)
I1 encoder never panics · I2 unsupported never approximated · I3 round-trip canonical
equality · I4 invalid → never a ToolCall · I5 unknown tool → never a ToolCall · I6 any
chunking == whole-input decode · I7 same tools → same bytes · I8 compaction never changes
native semantics · I9 router flag off → byte-identical · I10 no fallback after visible output.

## Grammar candidates (Step 1, benchmark tokens + small live test, then freeze)
- **A (brief style):** `name(title:str, start:datetime, dur?:int # minutes, vis?:public|private) - desc`
- **B (explicit, audit):** `name(title:str!, start:datetime!, dur:int? @"minutes", vis:(public|private)?) @"desc"`
- **C (TypeScript-ish):** `name(a:{title:string; dur?:integer /*minutes*/; vis?:'public'|'private'}) // desc`
Description escaping defined per candidate (e.g. `\"`/`\\` inside `@"..."`; `#`/`*/` forbidden
→ fallback if a description contains the delimiter). Call syntax fixed: `<<call NAME {json}>>`.

## Step 1 result: token benchmark (o200k, compact-JSON body)
| cand | public full | public schema | extra full | extra schema |
|---|---|---|---|---|
| A inline `#` | 31.3% | 39.3% | 46.7% | 49.9% |
| B `!`/`@"…"` | 25.4% | 31.6% | 42.1% | 44.9% |
| C TS-ish | 27.7% | 34.6% | 40.2% | 42.9% |
| **A2 line-per-param** | **32.2%** | **40.3%** | **46.1%** | **49.2%** |
A is ambiguous (descriptions contain commas). **Provisional pick: A2** (cheapest + unambiguous):
`name # desc` / ` param[?]:type # desc` (1 space indent per nesting level, `{}` = object whose
fields follow indented, `[T]` arrays, `a|b` enums). Descriptions with newlines or enum literals
with `|`, `#`, whitespace → fallback. Final freeze after step-2 live check.
