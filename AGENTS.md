## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- When graphify-out/graph.json exists, run a focused `graphify query "<question>" --budget 1000` before your first grep, search or source-file read for a codebase question. Ask about one symbol, module or flow at a time; use `--seed <symbol> --depth 1` or `--context <edge>` when useful. If the answer is broad or truncated, narrow it before increasing the budget. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. When the answer is under a Markdown heading, `graphify section "<heading>"` prints that section's text, so the .md need not be opened. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- Use `graphify update .` for routine code refreshes. Run semantic extraction or `graphify label` only when changed documents or missing community labels matter to the task; these steps can use model tokens.
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.

## Matt Pocock engineering skills

Matt Pocock's skills are installed globally for Codex and Antigravity. Select a skill only when the user's request matches its description, and read that skill's `SKILL.md` rather than loading the whole collection. Prefer `implement` for requested code changes, `diagnosing-bugs` for reported failures, `code-review` for review requests, and `writing-for-agents` when editing agent instructions. Use the host's native skill invocation syntax. Do not invoke setup workflows that ask the user to choose external trackers or project conventions unless that setup is requested.
