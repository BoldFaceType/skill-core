# Why Filesystem-As-State

The design rationale behind Skill Core's structure. Relocated from a standalone canvas so the reasoning lives beside the thing it justifies.

## The claim

An agent ecosystem should run on ordinary files and folders, not on a framework. The filesystem is the source of truth; everything else is transport.

## Why

**Folders are routing.** Rather than making an agent choose among many tools, the directory it works in narrows what it can see and do. Context shrinks because location already answers "what am I working on."

**Files are the knowledge base.** Skills are Markdown with YAML frontmatter — readable without a database, a network, or a runtime. Any agent, any editor, any `grep`.

**Chat is not state.** A session is a conversation that ends. A run directory persists, resumes, and can be handed to a different agent or a different person. Each stage reads the prior stage's file, not the entire prior conversation — which is what bounds context and makes retry possible.

**Nothing to keep running.** No server, no database, no scheduler that can be down. The failure mode of a missing service is silent data loss; the failure mode of a missing file is an error you can see.

## Design consequences

Each of Skill Core's structural choices follows from the above:

| Choice | Rationale |
|---|---|
| Skill Core is immutable, never locally edited | Upstream identity must stay verifiable; local edits make provenance meaningless |
| Workflows are `.toml` data, not Python | A recipe should not require programming to add |
| Every stage declares a durable output | Enables resume/retry and bounds the next stage's input |
| `runs/<id>/` is the execution record | Chat is transport, not state |
| The installer owns only declared paths | Never destroy what it did not create |
| Skill Core is not a runtime | Execution belongs to hosts; owning it means rebuilding it every time hosts change |

That last row is the load-bearing one. SkillStore v1.x built its own execution, storage, search, and cost model, and every one of those was absorbed by the platform within a year. Skill Core owns only what nobody else does: **which skills you have, pinned to which versions, in which combinations.**

## The Activation Gap

The failure this design avoids: an agent given a tool that it never invokes. Turning active tools into passive, location-bound context removes the decision entirely — the agent doesn't choose to load context, the folder it's in already supplies it.

## Vocabulary from the original canvas

*FSAR* (Folder Structure as Routing) · *ICM* (Interpretable Context Methodology) · *OKF* (Open Knowledge Format — Markdown + YAML + relative links) · *Locality of Reference* (everything for one task inside one folder boundary) · *JSONL* (append-only line-delimited log) · *Resolver agent* (reads activity logs, distills skills) · *SkillOpt* (validates candidate skills under a bounded edit budget) · *CLI-Anything* (drive applications through command lines, not screen-scraping).

Two of these have since been superseded by upstream work rather than local implementation: the Resolver and SkillOpt roles are covered by the `skillopt-sleep` skill (microsoft/SkillOpt). See `decisions/0003-skillstore-v1x-archived.md`.

## Source lineage

- *CLI-Anything: Towards Agent-Native Computer Use* — Yang, Fan, Huang (2026)
- *Interpretable Context Methodology: Folder Structure as Agentic Architecture* — Van Clief & McDermott (2026)
- *Structured Context Engineering* — McMillan (2026)
- *SkillCompiler: unified compilation for cross-platform LLM agent skills* — Ouyang (2026)
- Open Knowledge Format v0.1 (Google Cloud); Model Context Protocol; Vercel/Eve "Activation Gap"

These are recorded as lineage. Claims attributed to them have not been re-verified here.
