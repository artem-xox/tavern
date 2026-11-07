---
id: S3-R08
title: One observation, built in one place, with one list of people
status: done
needs: [S3-R04]
touches: [hall/world.py, evening/decisions.py, evening/mind_loop.py, mind/intentions.py, mind/goals.py, mind/options.py, mind/hall_view.py, mind/agents.py, mind/local_policy.py, mind/briefing.py, mind/fight_words.py, tests]
---

# S3-R08 — One observation

## Why

What a guest observes is what the player's client will show the player, so its shape must be one thing.
Today:

- `world.observe_actor` returns `visitors`: the people in sight **who sit** (`_visible_visitors`, with the
  Stage 0 comment "Only seated company is actionable in this small social demo").
- Three callers then add `people`, everyone in sight, from `observe_people`:
  `evening/decisions.py:54`, `evening/mind_loop.py:216`, `mind/intentions.py:252`, each as
  `{**observe_actor(...), "people": observe_people(...)}`.
- So `visitors` is always a subset of `people`, and the readers merge the two again:
  `[*observation.get("visitors", []), *observation.get("people", [])]` in `mind/goals.py:67`,
  `mind/options.py:55,79`, `mind/local_policy.py:205`, `mind/briefing.py:228,247,257,278`, and
  `observation.get("people") or observation.get("visitors", [])` in `mind/options.py:294`,
  `observation.get("people", observation.get("visitors", []))` in `mind/briefing.py:159`.
- The observation has no type: `Observation = Mapping[str, Any]` is declared separately in `mind/options.py`,
  `mind/briefing.py` and `mind/fight_words.py`.

## Scope

- In: `observe_actor` returns `people` (everyone in sight, as `observe_people` does) and no `visitors`; an
  `Observation` `TypedDict` in `hall/world.py` as its return type; the three callers drop their merge; every
  reader uses `people`, filtering `person["seat_id"]` where it used `visitors`.
- Out: what the observation contains otherwise; `observe_people` (tests and the world use it; it stays).

## Shape

```python
class Observation(TypedDict):
    actor: Actor; objects: list[dict[str, Any]]; people: list[dict[str, Any]]; memory: list[dict[str, Any]]
    visible_cells: list[list[int]]; time: float; invitations: list[dict[str, Any]]; promises: list[...]
    map: dict[str, int]; closed: bool; called_closing: float | None; giving: dict[str, float]; on_errands: list[str]
```

Take the exact field types from what `observe_actor` builds today; `mypy` decides. Readers that add keys
(`agents.choose_action` adds `projects`) keep doing so on a plain `dict` copy.

## Approval

Test edits, **Approved by the owner, 2026-11-07**: hand-built observations that use a `visitors` key switch it to
`people` (with `seat_id` set as before): 12 uses in `tests/hostile_view.py`, `tests/test_aims.py`,
`tests/test_families.py`, `tests/test_feelings.py`, `tests/test_evening.py`, `tests/test_seating.py`,
`tests/test_social.py`. Assertions that read `observation["visitors"]` read the seated part of
`observation["people"]` instead. Nothing else.

## Steps

1. `Observation` type and `observe_actor` returning `people` **beside** `visitors` (both, for now); the three
   callers stop adding `people`. One commit. — check: `make test`, golden empty diff.

   Expect about 4 tests to fail here (measured 2026-11-07 on `main`, before R04, on a copy with `people`
   added to `observe_actor`; after R04 the list may shift by a case or two, and the triage covers whatever fails):
   `tests/test_seating.py::test_jev_reads_a_briefing_instead_of_raw_maps`,
   `tests/test_seating.py::test_demo_newcomers_mostly_head_for_a_seat_or_the_tap`,
   `tests/test_social.py::test_social_candidates_deduplicate_visible_neighbors[empty-company]`,
   `tests/test_world.py::test_individual_observation_does_not_leak_unknown_resources_or_private_state`.
   They fed `observe_actor(...)` alone to the briefing or the candidates, an observation without `people`
   that no evening builds (the same gap as R04), or they pin the observation's exact keys. Before editing
   them, write a "Triage" section in this file (case, cause, edit) and follow R04's rules: inputs first, an
   expected value only with old → new and why, never a weaker assertion; "needs the owner" otherwise. These
   4 are approved for edit on those terms with the rest of this task.
2. Readers switch from `visitors` to `people`, one commit per module (`goals`, `options`, `hall_view`,
   `agents`, `local_policy`, `briefing`). Keep the order: the seated people in `people` order are exactly
   `visitors` in its old order. — check after each: `make test`, golden empty diff (the briefing text, and so
   every Jev request, must stay byte-identical).
3. Drop `visitors` from `observe_actor` and `_visible_visitors` from `world.py`; replace the three
   `Observation = Mapping[str, Any]` aliases with the `TypedDict`; the approved test edits. One commit.
   — check: `grep -rn '"visitors"' backend tests` finds nothing; `.venv/bin/mypy` green.

## Triage

Step 1 ran on 2026-11-07 on `claude/s3-r08-observation-2ca3c5` (tip of `claude/s3-prep` after R04): **2 failed, 4642 passed**.
Of the 4 cases listed above, the two `test_seating.py` cases pass: R04's edits already gave them `people` (or a path that
does not need it). Each failing case was run alone before any test edit.

| Case | Failing assertion and cause | Edit |
|------|-----------------------------|------|
| `test_social::test_social_candidates_deduplicate_visible_neighbors[empty-company]` | `sum(...) == 0` got 1: the test replaces `view["visitors"]` with `[]`, but `observe_actor` now carries Bea (seated, in sight) in `people`, and the candidates read both lists | inputs: the test also sets `view["people"] = visitors`, so the company it hands over is the whole company it names. Assertion and expected values unchanged. Step 3's approved `visitors` to `people` switch then leaves only the `people` line |
| `test_world::test_individual_observation_does_not_leak_unknown_resources_or_private_state` | `"bea" not in json.dumps(observation)`: Bea stands in plain sight of Ada, so her public id is now in `people`; the test meant that nothing private or unseen leaks | inputs: a wall of blocked cells across row 2 of the 20-wide room, so Ada cannot see Bea; the tap stays unseen as before. All three assertions unchanged |

## Done when

- `make check` passes; golden check prints nothing. Pasted into Results.
- One function builds an observation; no reader merges two lists of people.

## Results

Done 2026-11-07 on `claude/s3-r08-observation-2ca3c5` (step 1; step 2 one commit per module; step 3).

- `make check`: `4644 passed in 276.09s`, `mypy: Success: no issues found in 134 source files`, frontend `tsc --noEmit` clean
  and `node:test` 318 pass, 0 fail. Frontend untouched, so no `make build`.
- Golden: `make golden GOLDEN=runs/golden-now && diff -r runs/golden-base runs/golden-now` printed nothing after step 1,
  after each module of step 2 and after step 3.
- `grep -rn '"visitors"' backend tests` finds nothing. `observe_actor` is the one function that builds an observation and returns
  `Observation`; no reader merges two lists of people.

Deviations from the ticket, with reasons:

- **`Observation` lives in `hall/state.py`, not `hall/world.py`.** `world.py` imports `social.commitments`, which imports
  `mind.goals`, which would import `Observation` back: an import cycle. `state.py` already holds the `World` and `Actor`
  TypedDicts; `world.py` imports it from there.
- **The reader aliases `Observation = Mapping[str, Any]` stay** (four, not three: `hall_view.py` too). Replacing them with the
  TypedDict gave 18 mypy errors in callers that pass a `Mapping` or a plain `dict` copy that has gained keys (`social/aims.py`,
  `intentions.py`, `agents.py`, `local_policy.py`), and the tests pass hand-built dicts that lack most keys. Fixing them means
  editing files the ticket does not name. The typed observation is the return type of `observe_actor` only.
- **Order is not free in `agents._social_candidates`.** Plain iteration over `people` changed the golden log (guests-1 and
  guests-5: the first person seen for a scene or a table sets the option, so the request listed options in another order).
  The loop now takes seated people first, then the rest, each in sight order, which is exactly the old
  `[*visitors, *people]` order; golden is empty again.
- `hall_view.visible_visitor` and `_seats_taken` keep their "seated only" meaning by filtering `seat_id` on `people`.
- `briefing._people` lost its "bare observation knows only seated company" branch: `observe_actor` always has `people` and no
  test pinned that text.
- The approved test edits that a reader switch needed were made in that module's commit, with the hand-built helpers of
  `test_families.py` and `test_seating.py` carrying both keys for the commits in between and `people` alone at step 3.
- Tests were run in 8 parallel chunks between steps; the two `*_stills_ship_with_browser_build` asset tests build the frontend
  and fail only when run in parallel; they pass alone and in `make check`.
