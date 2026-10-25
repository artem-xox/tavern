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

- 80 of 125 line requests told the writer "the dice table stands free, propose a game", 64 of them only because the
  guest was tipsy, some mid-quarrel with no invite on offer. 67 lines said "dice"; no game was played.
- 11 of 13 invitations were never answered: one of the two left the talk first and the invitation lapsed silently, so
  the same guest asked the same person again in the next talk (Tyson asked Sobchak to dice six times).
- 25 of the line writer's 27 examples were border folk talking about mules, tolls and the road, under a tone of
  "grounded, warm"; DESIGN.md asks for satire with no brakes.
- The dialogue judge never asked whether a talk was funny, which is the stage's test.

## Scope

- In: the dice nudges only while the speaker may invite and has asked nobody yet in the talk; an unanswered invitation counts as a no; a prompt that
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
3. Dice nudges only while an invite is on offer and the speaker has asked nobody yet in the talk — check:
   `pytest tests/test_dice_invitation.py -k haiku`.
4. An unanswered invitation is not made again at once — check: `pytest tests/test_turned_down.py`.
5. Prompt: tone, comic moves, examples — check: `pytest tests/test_story_tavern.py`.
6. Eval again, and a live Guests evening (seed 5) against the morning's.

## Done when

- `make check` passes.
- The eval's `funny`, `development` and `liveliness` means rise over the baseline, and `echo` stays under its 0.35 cap.
- In the live evening, far fewer lines say "dice" than 67 of 125.

## Results

Built: the dice nudges (bored, or tipsy) only while an invite is on offer and the speaker has asked nobody yet in the
talk; a `left_hanging` thought that makes an unanswered invitation count as a no; a line-writer prompt with a satire
tone, a COMIC MOVES block and 23 of 34 examples voicing famous guests; a `funny` criterion for the judge.
`make check`: 4317 passed, frontend typecheck and 247 node tests pass.

Dialogue eval, Putin and Zelensky, 3 scenarios × seeds 1–3, means before → after (`runs/evals/baseline`,
`runs/evals/after`):

| | funny | development | liveliness | coherence | in_character | variety | echo | on_brief |
|---|---|---|---|---|---|---|---|---|
| before | 1.88 | 2.12 | 2.25 | 3.00 | 3.75 | 0.22 | 0.18 | 0.56 |
| after | 1.78 | 2.00 | 2.22 | 2.89 | 3.67 | 0.33 | 0.25 | 0.74 |

No change the judge can see. That pair's talk is one quarrel about the war, and the judge's notes blame the same
thing every time: both circle one charge and nothing changes (D28). A prompt does not fix that. Once, Putin copied
Zelensky's previous line word for word: the repeat check only compares a speaker with their own lines.

Live Guests evenings: before; with no drink nudge at all; with it back, once per talk (the final code):

| | seed 5 | seed 1 |
|---|---|---|
| line requests with a dice nudge | 80 of 125 → 7 of 159 → 19 of 103 | 24 of 97 → 0 of 109 → 14 of 127 |
| lines saying "dice" | 44 of 84 → 12 of 105 → 32 of 87 | 20 of 77 → 0 of 90 → 22 of 90 |
| invitations accepted | 0 → 0 → 3 | 2 → 0 → 0 |
| dice games played | 0 → 0 → 1 | 2 → 0 → 0 |
| longest run of insults between one pair | 27 → 5 → 2 | 4 → 7 → 5 |
| fights | 0 → 2 → 2 | 4 → 6 → 2 |

With the nudge once per talk, most of seed 5's dice lines come from talks where dice are already the subject: an
invitation being answered, or a game played earlier. Seed 1 played no game because its invitations died unanswered:
of 8, five ended with the inviter or the one asked walking out of the talk 6 to 10 s later (D29).

The talk moved to the guests' public lives: Vucic, asked about his two chairs, "One for the people, one for the people
who pay"; Musk to Tyson, "your chair's the only thing you've ever held longer than a grudge". Left as they were: the
barkeep greets the same newcomer four times in 15 s, Musk and Hob circle the beer pipe for the last ten lines, and the
speeches from the stage are still a guest's inner thought read aloud.

Follow-up, D29: why invitations died unanswered. Of 48 in six live evenings, 19 died when a quarrel nearby broke one
of the two off (`attention._alert` took every alerted guest out of their talk), and the invitee rarely answered: 3 of
33 first lines were accept or decline, 8 said goodbye, the rest said yes in words under another act ("Dice, sure" as
agree). The answer stage of C7 is off unless `AI_ANSWERS` is set, so the line writer had every act. Now two guests
between an invitation and its answer stay in their talk when a sound turns their heads (`scenes.awaits_answer`), and
an undecided invitee may only accept or decline, with no goodbye nudged at them.

| | seed 1 | seed 5 |
|---|---|---|
| invitations answered | 0 → 10 | 3 → 10 |
| games played (dice + darts) | 0 → 7 | 1 → 5 |
| invitee's answer, seconds after the invitation | – | 6 to 9 |

(Once-per-talk nudge → with the hold; one live evening each.) Answers lean heavily to yes: 19 accepts to 2 declines.
Insults and quarrels rose on seed 5 (3 → 21 insults), as they swing from run to run (36, 25, 3, 21 on that seed).
