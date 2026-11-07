---
id: S3-R07
title: Metrics of actions, invitations and talk read event fields, not wording
status: todo
needs: [S3-R06, S3-R10]
touches: [social/turns.py, evening/metrics.py, evening/invitation_metrics.py, evening/choice_metrics.py, evening/fight_metrics.py, evening/dialogue_metrics.py, frontend/src/types.ts]
---

# S3-R07 — Metrics read fields, not words (actions, invitations, talk)

## Why

`metrics.json` is how every change is judged, and eleven counters in `evening/` parse event wording with
`str` methods or regexes (2026-11-07). When the player's lines and acts enter the log, worded differently,
those counts would go silently wrong. This task switches the five readers of action, invitation and talk
events; [R07b](r07b_more_metrics_read_fields.md) does the other six with the same method.

| Reader | Parses | Reads instead |
|--------|--------|---------------|
| `metrics.completed_activities` | `re.fullmatch(r".* completed ([a-z_]+)", message)` | `verb` on `action_completed` (R06) |
| `choice_metrics._repeats` | `message.rpartition(" chose ")` | `verb` on `action_started` (R06) |
| `fight_metrics` reactions | `message.endswith(f" chose {verb}")` | `verb` on `action_started` (R06) |
| `invitation_metrics.invitation_counts` | `_ANSWERED`, `_COUNTERED` over answer messages; `"(invite):" in` a `turn` message | `invitation` on answer events (R06); `act` on `turn` |
| `dialogue_metrics` | `_TURN` (`"<speaker> to <listener> (<act>): <line>"`) for who spoke to whom with which act; `startswith(f"A line for {name} failed")` | `actor_id`, `addressee`, `act` on `turn`; `speaker_id` on `turn_failed`. The words of the line it may still take from the message (`message.split("): ", 1)[1]`): measuring words is its job |

## Scope

- In: the new fields below at their source; the five readers above. Every message stays byte-identical.
- Out: R07b's readers. Deduplicating by `(time, message)` (`giving_metrics`, `manner_metrics`,
  `fight_metrics.once`, `ailment_metrics`): that uses the message as an identity, not as data; leave it.
  `repetition.py` and the dialogue judge measure the words themselves: leave them.

## Shape

| Event | New fields | Logged in (`log_event` returns the event since R05) |
|-------|-----------|------|
| `turn` | `act`, `addressee` (actor ID or None) | `social/turns.py` `_speak` |
| `turn_failed` | `speaker_id` | `social/turns.py` `deliver_turn` |

Do **not** put `line` on every `turn`: `line` on a turn is the client's signal that the line broke its scene
up and must show as a callout (`turns._speak` sets it only then; `frontend/src/bubble.ts` `callout` reads it).

`frontend/src/types.ts`: `WorldEvent` gains `act?: string; addressee?: string | null; speaker_id?: string`,
in the same commit. No new save bump if R06's bump to 23 is not yet released; otherwise ask the owner.

## Steps

1. Log the fields at their source. One commit. Golden check: R06's script with
   `NEW = {"verb", "invitation", "inviter_id", "act", "addressee", "speaker_id"}`, and `make build`.
2. One commit per reader module, in the table's order: read the field; delete what only parsing needed
   (`_ANSWERED`, `_COUNTERED`, `_WORDS`, `_BY_WORDS`, `_TURN` when nothing else uses them) and the
   `ValueError`s that guarded unparseable wording, replacing each with one for a missing field.
   — check after each: that module's tests green (`tests/test_metrics.py`, `test_choice_metrics.py`,
   `test_fight_metrics.py`, `test_invitation_metrics.py`, `test_dialogue_metrics.py`) and every golden
   `metrics.json` identical (`diff -r` on the `metrics.json` files only).

## Approval

A test that builds events by hand without the new field fails once its reader switches: the fixture is now
incomplete, not wrong. Adding the field to hand-built events is the only approved test edit; a test that
asserts the old parse error is replaced by the same test for the missing-field error. List each edit in
Results. **Approved by the owner, 2026-11-07.**

## Done when

- `make check` and `make build` pass; golden `events.jsonl` identical apart from the new fields; every
  golden `metrics.json` identical. Pasted into Results.
- The five readers contain no `["message"]`, except `dialogue_metrics` taking a line's words.

## Results

Filled in when the task is done.
