---
id: S2-12
title: The stage
status: done
needs: [S2-06, S2-07]
touches: [hall/room.py, data/tavern.json, body/activities.py, body/hearing.py, social/speeches.py, social/thoughts.py, mind/goals.py, mind/agents.py, mind/local_policy.py, mind/options.py, evening/story_score.py, evening/speech_metrics.py]
---

# S2-12 — The stage

## Why

Trump will want to get up and tell everybody something. Today a guest can only talk to the few at their table;
nothing lets one guest address the whole room, and nothing makes the room answer. A small stage gives the loud
guests a verb that turns heads, splits the room into cheers and groans, and is a moment worth retelling.

## Scope

- In: object kind `stage` (one speaker spot, art-free); verb `give_speech`; the room hears it; listeners think
  `speech_admired` or `speech_tiresome` and may cheer; goal kind `address_room` (no person); local utility; a
  `speech` story moment and its metrics.
- Decision: speech lines are written by a pure function from the speaker's card (`social/speeches.py`), as the
  barkeep's call-outs are fixed text. Model-written speeches need a new request in `mind_loop`; that is a
  follow-up, not this task.
- Decision: heckling and toasts are not in this task: heckling needs an `insult` aim at a listener out of
  reach, which `aims` does not offer, and a toast needs a new joinable scene. Both are follow-ups.
- Out: stage art (S2-04 art pipeline); model-written speeches; signature acts (S2-08); escalation (S2-09).

## Shape

- `OBJECT_KINDS` gains `stage`. The hall has one, `stage`, at (17, 9) with its spot at (16, 9).
- `Activity(verb="give_speech", target_kinds=("stage",), family="company", fun=0.8, duration=6.0)`; its effect
  is `speeches.give_speech`.
- Event `gave_speech` (the speaker's, with `line`); sound `EVENT_SOUNDS["gave_speech"]`, loudness 0.6, reach 30:
  between `dice_won` (0.3) and a brawl (1.0).
- Everyone awake who hears it at `HEARD_FROM` or louder keeps the lines in `heard` (scene id `speech-<time>`,
  act `boast`) and thinks `speech_admired` / `speech_tiresome` about the speaker.
- Goal kind `address_room` (`GoalKind.person=False`, target None), reached by a `gave_speech` in the guest's
  memory after the goal was set. No save format change.

## Steps

1. Stage object and `give_speech` verb: it runs at the stage and logs `gave_speech` — check:
   `pytest tests/test_speeches.py -k stage`.
2. The room hears it: sound, `heard` lines, thoughts — check: `pytest tests/test_speeches.py -k hear`.
3. Listeners cheer — check: `pytest tests/test_speeches.py -k cheer`.
4. Goal `address_room` — check: `pytest tests/test_goals.py -k address`.
5. Candidate, local utility and option sentence — check: `pytest tests/test_speeches.py -k utility`.
6. Story moment and metrics — check: `pytest tests/test_story_score.py tests/test_speech_metrics.py`.
7. Client: the speech shows as a bubble over the speaker; the stage is drawn as a plain plank.
8. Live evening, Guests, seed 5.

## Done when

- `make check` and `make build` pass.
- A live Guests evening (Trump, seed 5) has at least one speech with listeners reacting.

## Results

Built: stage object, `give_speech`, `speeches.py` (lines from the card, hearing, thoughts, applause, cooldown),
goal `address_room`, `speech` moment (weight 1.5), `speech_metrics`, plank art and speech bubbles in the client.
Only guests with a public persona on their card speak (ordinary locals never do: it kept the Locals news-spread
test intact). Weight 1.5 sits between a gift (1.0) and a quarrel (2.0).
Live Guests evening, seed 5 (Haiku lines): 9 speeches by Musk, Trump, Greta and Tyson; 23 listeners admired, 8 groaned.
Offline seed 5: 5 speeches. Not done: heckling, toasts and model-written speeches (follow-ups).
`tests/test_lineup.py::test_the_api_lists_both_casts_and_starts_either` fails here also on the merged S2-06/07 branch
without this task's changes; it is not caused by it.
