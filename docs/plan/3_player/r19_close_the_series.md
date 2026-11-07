---
id: S3-R19
title: Close the R series: AGENTS.md, tech debt, plan index, names and stale docs
status: todo
needs: [S3-R01, S3-R02, S3-R03, S3-R04, S3-R05, S3-R06, S3-R07, S3-R07b, S3-R08, S3-R09, S3-R10, S3-R11, S3-R12, S3-R13, S3-R14, S3-R15, S3-R16, S3-R17, S3-R18]
touches: [AGENTS.md, README.md, docs/plan/README.md, docs/plan/TECH_DEBT.md, docs/plan/3_player/README.md, pyproject.toml, frontend/package.json, frontend/package-lock.json]
---

# S3-R19 — Close the series

## Why

The first player task will be written from AGENTS.md, the plan index and TECH_DEBT.md. After the R series
they describe a codebase that no longer exists. This task makes the documents true, and finishes the
renames the project's setting change (S2-00) left behind. A task dropped by the owner is skipped here: write
only what landed.

## Steps

1. **AGENTS.md.**
   - "Commands": add `make golden   # four offline evenings, to diff before and after a refactor (S3-R00)`.
   - "Architecture": add the modules the series created, each with its few words: `hall/whereabouts`
     (at which table or bar, whom one can reach), `mind/candidates` (the options open now),
     `mind/turn_view` (what a line writer sees), `mind/haiku_intentions` (Haiku's intention question),
     `evening/report` (the report of `make evening`). Remove names that no longer exist
     (`grep -o '`[a-z_]*`' AGENTS.md` against `git ls-files backend`).
   - "Testing": the rubric added by R16, if it landed.
   One commit.
2. **TECH_DEBT.md.** D09 is gone (R13). D16 names only `state.py` (R10). D05's evidence: recount
   `grep -ro "dict\[str, Any\]" backend | wc -l` (139 on 2026-11-07, the row still says 80). Add a row for
   what the series left on purpose: `social/scenes.py` about 410 lines, `body/activities.py` 687 (the verb
   table; split when a player verb is added), `mind/turn_prompt.py` 505 (prompt text), and any "needs the
   owner" case left by R04 or R08. One commit.
3. **Plan index** (`docs/plan/README.md`). Every R row → its final status. Stage 2 rows that disagree with
   their task file's `status:` (on 2026-11-07: S2-09 and S2-12 say `done` in the file, `doing` in the index)
   take the file's status. List, in Results, the Stage 2 tasks still `doing` (S2-00, 03, 04, 07, 10, 13) for the
   owner to close or keep; do not change them yourself. One commit.
4. **Names.** `pyproject.toml`: `name = "story-tavern"`, `description = "The Story Tavern: famous guests,
   model-driven, in one evening"`. `frontend/package.json` and `package-lock.json` (both `name` fields):
   `story-tavern-client`. Then `make install` (the editable install's egg-info is named after the
   project) and `make check`. One commit.
5. **Stale docs.** `docs/PIXEL_ART_REDESIGN.md` (2026-10-02) plans art for the "medieval border inn", the
   setting before S2-00; README links it as the current plan, and `docs/CHARACTER_ART_PIPELINE.md` (about line
   279) calls it "the room" plan. **The owner decided 2026-11-07: history.** Delete it (git keeps it) and
   drop both links. One commit.

## Done when

- `make check` and `make build` pass. Pasted into Results.
- `grep -rn "last.inn" --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=.git --exclude-dir=.claude -i .`
  finds only `docs/plan/*/archive.md` and the test that guards the name (if R16 kept it).
- The Stage 3 README says "R series: done" and points at the first player task to write.

## Results

Filled in when the task is done.
