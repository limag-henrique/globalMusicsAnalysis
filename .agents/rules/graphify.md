---
trigger: always_on
description: Consult the graphify knowledge graph at graphify-out/ for codebase and architecture questions.
---

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- For codebase or architecture questions, when `graphify-out/graph.json` exists, first run a focused `graphify query "<question>" --budget 1000` (CLI) or `query_graph` (MCP). Ask about one symbol, module or flow at a time; use `--seed <symbol> --depth 1` or `--context <edge>` when useful. If the answer is broad or truncated, narrow it before increasing the budget. Use `graphify path "<A>" "<B>"` / `shortest_path` for relationships and `graphify explain "<concept>"` / `get_node` for focused concepts. When the answer is under a Markdown heading, `graphify section "<heading>"` / `get_section` returns that section's text, so the .md need not be opened. These return a scoped subgraph, usually much smaller than `GRAPH_REPORT.md` or raw grep output.
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
- Use `graphify update .` for routine code refreshes. Run semantic extraction or `graphify label` only when changed documents or missing community labels matter to the task; these steps can use model tokens.
