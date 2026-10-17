# Stage 1 — A believable evening (done: foundation)

**Goal:** four to six model-driven guests spend one evening in the hall, and it looks believable.

Closed on 2026-10-17 as the foundation for [Stage 2](../2_story_evenings/README.md). The engine works;
the acceptance runs (E28) were not made. Stage 2 measures stories instead of believability.

## What the engine has now

- **Three speeds of thought:** the body in code (queues, routes, facing), the choice by Jev, the mind by
  Claude Haiku 5.5 (lines with speech acts, intentions, typed goals). See [MIND.md](../../MIND.md).
- **Activities as a table** (`body/activities.py`): drink, sit, WC, fire, darts, dice, give, nap, shove, fight,
  watch, cheer, help up, leave together. Invitations and accept/decline for joint activities.
- **Social layer:** thoughts and mood, relationships, names learned, conversations as scenes, news that
  drifts as it is retold, overhearing, manners at tables.
- **The barkeep** pours every mug, chats at the counter and calls closing time.
- **Fights** from drink or hatred: a formula over strength, skill, weapon and drink, five endings, a room
  that watches, cheers, steps in or joins.
- **Sleep and energy, giving, carried items, sickness and remedies.**
- **Character catalog** under `characters/<id>/` with eight-view art for every pose
  ([CHARACTER_CATALOG.md](../../CHARACTER_CATALOG.md)).
- **Headless evenings** (`make evening`), lockstep replay, `metrics.json`, cost per evening.
- Saved worlds are version 19.

## What carries over

Unticked tasks and open problems are in [TECH_DEBT.md](../TECH_DEBT.md). The task texts, decisions,
measurements and results are in [archive.md](archive.md) (history; do not extend). It names modules by
their old flat file names: find one with `git ls-files | grep <name>.py`.
