# graphify — the fleet's structural map of `src/`

A committed structural graph of the library + orchestration code, used to scope
changes (blast radius / call sites) **before editing**. It is the concrete
backing for the "query graphify before touching code" rule in `CLAUDE.md`.

## What's committed

The graph lives under `src/graphify-out/` (graphify nests output beneath the
scanned path). Only two artifacts are tracked in git; everything else is
gitignored (large or local-path-bearing, fully regenerable):

- **`src/graphify-out/graph.json`** — the graph (917 nodes / 2259 edges at
  creation): functions, classes, methods + their relationships, each node
  tagged with `src=<file> loc=L<line>`.
- **`src/graphify-out/GRAPH_REPORT.md`** — a plain-language map of the
  communities (clusters) in the code.

Ignored (regenerate any time): `graph.html`, `cache/`, `.graphify_labels.json`,
`.graphify_root`.

## Query it (before editing — no LLM/key needed)

`query` is a pure BFS/DFS traversal of `graph.json` — deterministic, offline:

```bash
# blast radius: what is wired to a symbol (returns nodes + file:line)
graphify query "what depends on GhRunner" --graph src/graphify-out/graph.json

# trace a specific path instead of broad context
graphify query "how does a ticket become a PR" --dfs --graph src/graphify-out/graph.json

# shortest path between two concepts
graphify path "GhRunner" "Queue" --graph src/graphify-out/graph.json

# plain-language explanation of one node and its neighbours
graphify explain "pr_reply_waiting" --graph src/graphify-out/graph.json
```

Use the returned `file:line` locations to find every call site and make the
smallest surgical change (Karpathy).

## Refresh it (on demand — no LLM/key needed)

The code extractor is AST-based, so refreshing needs no API key:

```bash
graphify update src        # re-extract changed code files, recluster, rewrite outputs
```

Then commit the two tracked artifacts:

```bash
git add src/graphify-out/graph.json src/graphify-out/GRAPH_REPORT.md
git commit -m "chore(graphify): refresh structural graph"
```

Refresh when a change **adds or renames** structure (new modules, functions,
classes). Pure edits inside existing functions don't move the graph much, so a
refresh-every-commit is unnecessary — this is the deliberate "rebuild on demand"
model.

> Note: `graphify update` re-extracts **code** with no LLM. The richer
> LLM-based extraction (semantic INFERRED edges across docs/papers) needs
> `GEMINI_API_KEY`/`GOOGLE_API_KEY` and is **not** used here — the deterministic
> code graph is what we want for a versioned structural map.
