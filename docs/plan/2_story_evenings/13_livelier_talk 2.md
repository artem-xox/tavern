---
id: S2-13
title: Livelier talk, the quick fixes
status: doing
needs: [S2-03]
touches: [mind/haiku_turns.py, mind/turn_prompt.py, social/scenes.py, social/thoughts.py, social/invitations.py, evening/dialogue_judge.py]
---

# S2-13 — Livelier talk, the quick fixes

## Why

Talk between famous guests reads flat. A live Guests evening on main (seed 5, 2026-10-25) showed why, and none of
it was the model's fault:

- 96 of 125 line requests told the writer "the dice table stands free, propose a game", because every tipsy guest got
  the nudge, even mid-quarrel with no invite on offer. 67 lines said "dice"; no game was played.
- 11 of 13 invitations were never answered: one of the two left the talk first and the invitation lapsed silently, so
  the same guest asked the same person again in the next talk (Tyson asked Sobchak to dice six times).
- 25 of the line writer's 27 examples were border folk talking about mules, tolls and the road, under a tone of
  "grounded, warm"; DESIGN.md asks for satire with no brakes.
- The dialogue judge never asked whether a talk was funny, which is the stage's test.

## Scope

- In: the dice nudge only for a bored guest who may invite; an unanswered invitation counts as a no; a prompt that
  plays famous guests for satire, with comic moves and famous-guest examples; a `funny` criterion for the judge.
- Out: scene stakes and an end to insult loops (with [S2-09](09_chaos.md)); a "what just happened in the room" block;
  the barkeep as a gossip; model-written speeches on the stage (a stage task of its own).

## Shape

- Thought kind `left_hanging` (`THOUGHTS`), held by an inviter about the guest asked, 180 s; `turned_down_by` reads it
  like `turned_down`. No save format change: thoughts are already saved by kind.
- `dialogue_judge.CRITERIA` gains `funny` (1–5). No threshold in `data/evals/putin_zelensky.json` yet.
- `turn_prompt`: the tone paragraph, a new `COMIC MOVES` block before the examples, 34 examples (23 famous).

## Steps

1. Judge scores `funny` — check: `pytest tests/test_dialogue_judge.py`.
2. Baseline: `scripts/dialogue_eval.py --seeds 1 2 3` on a snapshot of step 1.
3. Dice nudge for the bored who may invite — check: `pytest tests/test_dice_invitation.py -k "haiku or drink_alone"`.
4. An unanswered invitation is not made again at once — check: `pytest tests/test_turned_down.py`.
5. Prompt: tone, comic moves, examples — check: `pytest tests/test_story_tavern.py`.
6. Eval again, and a live Guests evening (seed 5) against the morning's.

## Done when

- `make check` passes.
- The eval's `funny`, `development` and `liveliness` means rise over the baseline, and `echo` stays under its 0.35 cap.
- In the live evening, far fewer lines say "dice" than 67 of 125.

## Results
