---
id: S2-14
title: Stage numbers
status: doing
needs: [S2-12, S2-13]
touches: [social/speeches.py, social/numbers.py, social/heckles.py, social/stage_lines.py, social/thoughts.py, mind/agents.py, mind/stage_prompt.py, mind/haiku_stage.py, evening/mind_loop.py, evening/lockstep.py, evening/speech_metrics.py, evening/story_score.py, server/runtime.py, server/sessions.py, server/api.py, app.py, scripts/evening.py, frontend/src/bubble.ts]
---

# S2-14 — Stage numbers

## Why

What guests say from the stage is nonsense. `speeches.speech_lines` glues one of three openers to the first sentence of
the speaker's inner thought and a catchphrase, so the room hears a plan meant for nobody: "Friends, patrons, whoever is
still sober! A word! Thirst first, then an audience, and this room has a barkeep and five empty tables to pitch from.
First principles." (Musk, live seed 5, 2026-10-25). Six of that evening's eight speeches opened the same way, five
retold "Trump and Musk are at it over dice", and the room's only answer was a count of who groaned. After this task a
guest climbs up for a reason, performs a number aimed at someone in the room, written by Haiku in their voice, and the
person it stung shouts back from the floor and gets a comeback.

## Scope

- In: four numbers (toast, roast, pitch, confession) chosen by the game; a reason to climb for each; a quiet spell
  for the whole room between numbers; the number's words written by Haiku (a new `stage` request), with a scripted
  fallback that never reads an inner thought aloud; what a number does to its target; a heckle from the floor and the
  performer's comeback, both written by Haiku; bubbles for both in the client; counts in `metrics.json`.
- Out: the stage's new look ([S2-15](15_stage_look.md)); a challenge number (a public invitation); a song.

## Shape

- No save format change. What waits for words is derived each tick from saved state: a performer is on the stage
  with `give_speech` and no `gave_speech` in their memory since they arrived (`_remaining` tells when); a heckle is
  due after a `gave_speech` event that names a `heckler_id`, a comeback after a `heckled` event. Which claims were
  asked lives in the mind loop (`MindLoop.staged`), as turn tickets do. Constants live in the modules, not in rules.
- `numbers.NUMBERS`: `Number(brief, aimed)` per kind. `choose_number(speaker, present, now) -> (kind, target_id)`,
  first that fits: `confession` (drunk or worse, the card has a secret, none confessed tonight), `roast` (someone
  present the speaker thinks `DISLIKED` of or worse; the most disliked), `toast` (tipsy or worse, someone present
  liked at +30 or more; the best liked), `pitch` (otherwise). Ties go to the lower actor ID.
- `speeches.performs` (the reason to climb): a persona and any number other than `pitch`, or a `pitch` with today's
  reasons (an intention serving an obsession, or the goal `address_room`); and no number heard in the last
  `ROOM_QUIET = 90` s by the guest (`heard_speech` or `gave_speech` in their memory).
- Event `gave_speech` gains `number`, `target_id` (or None) and `heckler_id` (or None); `line` is the beats joined.
  Events `heckled` (heckler's, with `line`, `performer_id`) and `heckle_answered` (performer's, with `line`,
  `heckler_id`). Sounds: `heckled` as loud as an insult across the hall; `heckle_answered` the same.
- Thoughts: `toasted` (target of a toast: mood +4, opinion +15), `roasted` (target of a roast: mood -6, opinion -25;
  their friends take offence as at an insult), `heckled` (the performer about the heckler: mood -4, opinion -15).
- Heckler: the roast's target if awake and in earshot, else the listener in earshot who thinks least of the
  performer, at `DISLIKED` or below; none otherwise.
- `give_speech` lasts 14 s (was 9): the number, the heckle and the comeback fit while the performer is up. The
  scripted number is spoken `PERFORM_WAIT = 4` s after arrival when no written one came.
- Writer port `stage_lines.StageWriter(view, config) -> list[str]`; `write_scripted_stage` by default in `MindLoop`,
  `lockstep.run_evening`, the runtime, sessions and the API; `haiku_stage.claude_stage_writer(ask)` with a key.
  The view: `kind` (`number`, `heckle`, `comeback`), the speaker (`card`, `portrait`, `feelings`, drink), the number
  (`kind`, `brief`, target's name), the room (who is present, and how the speaker regards them), tonight's salient
  moments, and for a heckle or comeback the words being answered.
- Question: system `[stage_prompt.shared_prefix(), haiku_turns.card_block(speaker)]` (the prefix shares the turn
  writer's world, news and comic moves, and stays above 16,500 characters to be cached); answer `{"lines": [...]}`:
  2–3 lines for a number, 1 for a heckle or comeback, each at most 120 characters, no stage directions. Recorded as
  call kind `stage` in `calls.jsonl`; a replay answers from it.
- `speech_metrics.stage_counts(events)`: numbers by kind, heckles, comebacks; in `metrics.json` beside `speeches`.
- Story: `heckled` is a `heckle` moment (weight 1.0).
- Client: `bubble.callout` shows `heckled` and `heckle_answered` too, and keeps a long line up for its reading time
  rather than 8 s. No snapshot change: events already carry `line`.

## Tests that change, because the behaviour they pin is what this task replaces

- `test_speeches.py::test_the_speech_voices_the_speakers_thought` and `::test_the_speech_ends_with_the_speakers_catchphrase`:
  the inner thought and the closing catchphrase are the nonsense; the scripted fallback writes the number instead.
- `test_speeches.py::test_the_listeners_remember_the_speech_the_moment_it_is_given` and
  `::test_the_listeners_turn_to_look_at_the_speaker`: a number is spoken when written, not on arrival; they wait
  for it.

## Steps

1. Numbers: choice, reasons to climb, room quiet — check: `pytest tests/test_numbers.py tests/test_speeches.py`.
2. Performing: the event's new fields, target thoughts, scripted fallback after the wait — check: `pytest tests/test_numbers.py -k perform`.
3. Claims and delivery for numbers, heckles, comebacks; the mind loop asks — check: `pytest tests/test_stage_lines.py`.
4. Heckler choice, heckle and comeback events — check: `pytest tests/test_heckles.py`.
5. Haiku: prefix, question, boundary check, writer — check: `pytest tests/test_haiku_stage.py`.
6. Wiring (lockstep, runtime, script, recording) — check: offline evening seed 5 has numbers and heckles.
7. Metrics, story moment, client bubbles — check: `pytest tests/test_speech_metrics.py`, `npm --prefix frontend test`.
8. Live Guests evenings, seeds 1 and 5.

## Done when

- `make check` and `make build` pass.
- In two live Guests evenings, every number is aimed (no inner thought read aloud), at least one is heckled and
  answered, and an observer can retell one from the log.

## Results
