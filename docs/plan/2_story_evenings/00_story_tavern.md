---
id: S2-00
title: The Story Tavern
status: doing
needs: []
touches: [mind/turn_prompt.py, data/minds/intention_prefix.md, hall/closing.py, server/api.py, frontend/index.html, frontend/src/dashboard.ts, .agents/skills/add-npc]
---

# S2-00 — The Story Tavern

## Why

The code and prompts still describe "The Last Inn", a border inn between two kingdoms. Famous guests from
any world do not fit that world. The models need to know where they are, or a president will talk about
salt tolls and margraves.

## Scope

- In: the name in the UI, the API title, the closing call and the `add-npc` skill; the setting text in both
  shared prompt prefixes.
- In: the setting. A tavern between worlds: whoever walks in arrives from their own life and knows who
  they are. The room is still a fantasy hall with a fire, a bar, darts, dice tables and a privy.
- Out: Locals' news and backgrounds (they stay border folk; the prefix must not contradict them). New
  objects (S2-08).

## Shape

No data changes. The prefixes keep their structure and stay above 4,096 tokens.

## Steps

1. Grep for `Last Inn` and replace it with `The Story Tavern` in the UI, API, closing line and skill.
   Check: `git grep -n "Last Inn"` finds only the Stage 0–1 archives.
2. Rewrite the world notes in `turn_prompt.shared_prefix` and `intention_prefix.md`: the tavern between
   worlds, famous strangers who know of one another, the locals who find all of it odd.
   Check: the prefix-length test and `make check`.
3. One live evening of the Locals (`make evening SEED=5`): their lines still read as border folk.

## Done when

- `make check` and `make build` pass.
- Nothing visible to a player says "The Last Inn".

## Results

Steps 1–2 done: the name and the between-worlds setting are in the UI, API, closing call, skill and both
prefixes (`tests/test_story_tavern.py`); `make check` (3,580 backend tests, 194 frontend tests) and `make build` pass.
The client shell was also restyled (calmer surfaces, type from 12 px, grouped controls).
Famous guests talk about their own public lives (a new section and examples in both prefixes) and start out
knowing each other by name (`well known` ties, added by the lineup for the Guests cast).
The line writer and the mind now also carry a dated briefing of the world's wars, scandals and quarrels
(`mind/world_now.py`, copied into `intention_prefix.md`; refresh both before an evening), and scenes no longer
open on "stories from the road".
Step 3 (a live Locals evening, `make evening SEED=5`) is not run: it needs a Jev key.
