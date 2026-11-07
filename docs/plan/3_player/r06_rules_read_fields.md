---
id: S3-R06
title: Rules read event fields, never event wording
status: todo
needs: [S3-R05]
touches: [hall/memory.py, hall/lifecycle.py, social/invitations.py, body/projects.py, mind/briefing.py, hall/world.py, adapters/persistence.py, frontend/src/types.ts, tests]
---

# S3-R06 — Rules read fields, not words

## Why

`record_event` says it keeps an outcome "as a field so that nothing has to read it from the words". Two game
rules still read the words:

- `body/projects.py` `_no_game` (about line 212) decides that a dice game will not happen by finding an
  `invitation_declined` event whose message contains `f"from {actor['name']}"` and `"dice"`.
- `mind/briefing.py` `_memory` takes the verb of an `action_completed` memory from the message's last word
  (`message.rsplit(" ", 1)[-1]`), and `recollections` drops a finished chat by `message.endswith(" talk")`.

A player's events will be worded differently (a player may have no proper name, a line may be quoted). A rule
that parses words breaks the first time wording changes. The fix is the one `outcome` already uses.

## Scope

- In: the fields below on the events that carry them, the two rules reading them, and the save bump that
  keeps old logs from being misread.
- Out: metrics that parse words (R07). Any change to messages: every message stays byte-identical.

## Shape

`record_event(world, actor, kind, message, outcome=None, fields=None)`: `fields` (a `Mapping[str, Any]`) is
merged into the event before it is logged, remembered and heard, exactly where `outcome` is set today.

| Event type | New fields | Logged in |
|------------|-----------|-----------|
| `action_started` | `verb` | `hall/lifecycle.py` (the two `... chose {verb}` calls, about lines 140 and 182) |
| `action_completed` | `verb` | `hall/lifecycle.py` (about lines 102 and 321) |
| `invitation_accepted`, `invitation_declined`, `invitation_countered` | `invitation` (the `KINDS` key), `inviter_id` | `social/invitations.py` (about lines 260, 281, 343) |

Readers: `_no_game` matches `item["type"] == "invitation_declined" and item["inviter_id"] == actor["id"] and
item["invitation"] == "dice_together"`; `briefing._memory` uses `memory["verb"]`; `recollections` drops
`item["type"] == "action_completed" and item["verb"] == "talk"`.

**Saves:** world events and memories now carry fields older saves lack. Bump `schema_version` 22 → 23 in
`world.create_world` and `persistence.parse_world` so an older save is refused loudly instead of misread
(`runtime.restore` already opens a new evening then). `tests/test_database.py` and
`tests/test_intention_saves.py::test_new_worlds_are_version_22` pin the version.
**Approved by the owner, 2026-11-07** (AGENTS.md: ask before changing the saved-world format).

**Snapshot:** events and memories reach the client. In `frontend/src/types.ts` add the optional fields
`verb?: string; invitation?: string; inviter_id?: string` to the event type, in the same commit.

## Approval

- The schema bump above, and the edits it forces: the version number in `tests/test_database.py` and the
  test `test_new_worlds_are_version_22` (renamed `..._23`).
- No other test edits. **Approved by the owner, 2026-11-07.**

## Steps

1. Red/green, `tests/test_shared_helpers.py`: `record_event` with `fields` puts them on the logged event and on
   the memory. One commit.
2. Refactor: the lifecycle and invitations calls pass the fields; `types.ts` gains them. One commit.
   Golden check: `events.jsonl` differs only by the new keys (script below); `make build` passes.
3. Behavior-neutral switch of the readers: `_no_game` and `briefing` read the fields. One commit. — check:
   `tests/test_projects.py`, `tests/test_rematch.py`, `tests/test_briefing.py` green unchanged; golden as in 2.
4. The schema bump, one commit, with the approved test edits.

Golden check that ignores the new keys:

```bash
.venv/bin/python - <<'EOF'
import json, pathlib
NEW = {"verb", "invitation", "inviter_id"}
for before in sorted(pathlib.Path("runs/golden-base").glob("*/events.jsonl")):
    after = pathlib.Path("runs/golden-now") / before.parent.name / "events.jsonl"
    strip = lambda path: [{k: v for k, v in json.loads(line).items() if k not in NEW} for line in path.read_text().splitlines()]
    assert strip(before) == strip(after), before
print("identical apart from the new fields")
EOF
```

## Done when

- `make check` and `make build` pass; the script above prints its line. All pasted into Results.
- `grep -n '\["message"\]' backend/tavern/body/projects.py backend/tavern/mind/briefing.py` finds no rule
  reading words (wording the briefing *shows* is fine).

## Results

Filled in when the task is done.
