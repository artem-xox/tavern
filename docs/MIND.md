# The Last Inn — Mind

How a guest thinks, where the current fast/slow split falls short among guests who meet all
evening, what others have learned building such agents, and the steps toward a mind that works
for any character in any place. [DESIGN.md](DESIGN.md#how-a-guest-thinks) describes the layers
as built; this document is the plan for changing them.

## Where we are

- **Body** (code, every tick): queues, routes, turning to a sound. It decides how, never what.
- **Choice** (Jev, on events): scores the legal options from the guest's briefing, first one
  option per activity family, then the action within it, and draws from the near-best.
- **Mind** (Claude Haiku 4.5, asynchronous): conversation lines with speech acts, and a
  `thought` plus an `intention` in free prose. An intention is asked on arrival, after a salient
  event (an interrupt, a quarrel, a taken seat, a scene's end, closing) and every 180 s.

The intention reaches the choice only as a sentence in Jev's briefing. The line writer does not
see it ([haiku_turns.py](../backend/tavern/mind/haiku_turns.py) reads the card's `goal`), and
the local policy does not read it either.

Cost and latency are not the problem. A live evening (seed 7, 2026-10-04) cost $0.21: Jev
$0.046 for 229 decision stages, intentions $0.086 for 46 calls, lines $0.074 for 39 calls.

## What the logs show

From `runs/g5-live-7` (seed 7, six guests, 433 s), checked against the other live evenings
recorded on 2026-10-04:

- **The mind plans what the world cannot do.** From 161 s to 224 s Brida intends five times
  over to "pour an ale at the tap and bring it back to Edda". No activity gives a drink to
  someone else. Across seven live evenings, 17 intentions in five of them ask for that, while
  DESIGN.md lists "buy someone a drink" as a planned action. An intention the world cannot
  carry out shows a missing verb.
- **Speech and action disagree.** At 159 s Brida says "let me get you an ale". Her later lines
  invite Edda to darts three times, the same line word for word at 207 s and 216 s.
- **Goals do not survive the evening.** Edda means to learn about the fever from 1 s, and at
  closing thinks "I have not got a straight answer from Brida". From 69 s Toren means to ask the
  sage-woman (Edda) which roads are watched. He reaches her only at 329 s, then tells her news and
  invites her to darts, and at closing thinks "I never got a straight answer about which roads
  are watched". Jev picks one step at a time and nothing holds the plan between steps.
- **Guests think alike and collide.** At 1 s three arrivals each intend an ale, then a seat by
  the fire. The evening has seven `seat_taken` events.
- **The slow layer does the fast layer's work.** 40 of the 46 intentions open with an errand the
  choice makes anyway (pour an ale, sit at a table, play darts, go home); a social aim, when
  there is one, comes after it.

## Why a fast/slow split breaks among many agents

1. **Plans go stale against other plans.** A plan is made on a snapshot, and other guests act
   on their own plans in the meantime. Dropping an answer after a salient event
   (`stale_intentions`) helps, but a prose plan cannot say when it is done, failed or
   impossible. Only code can, if the plan names things the code knows.
2. **No shared bottleneck.** Three channels decide in parallel: Jev, the line writer and the
   intention. Each reads a different picture of the guest, so what a guest says and what they
   do drift apart.
3. **Errors spread.** The mind reflects on lines another model call wrote. One invented fact
   travels through the group, as D17's misused `share_news` shows. Reflection should read the
   event log, not only other models' words.
4. **Aligned models are too nice.** They play kind people well and spiteful ones badly.
   Conflict must come from the numbers (temper, drink, grudges), with the model giving it
   words.
5. **The slow mind is not slow.** Asked after every scene's end, it ran six to eight times per
   guest in each evening of seven to eight minutes. That is chasing events, not reflecting on them.
6. **Inside one evening there is little past to reflect on.** Reflection over memories in the
   style of Generative Agents pays off across evenings (Stage 4). Within an evening the mind's
   job is to appraise what happened and to keep or drop goals.

## What research says

| Work | Idea | What we take |
|---|---|---|
| [Lyfe Agents](https://arxiv.org/abs/2310.02172) (2023) | A model picks an *option* with a subgoal; it runs until a cheap exit (a timer, repetition detection). An asynchronous self-summary feeds every prompt. About $0.50 per agent-hour, 10–100× cheaper than Generative Agents; without the summary, success in a nine-agent mystery fell from about 60% to 20–30% | Goals with exit conditions; repetition ends a conversation |
| [Project Sid / PIANO](https://arxiv.org/abs/2411.00114) (2024) | Concurrent modules at several speeds, and a cognitive controller as a bottleneck whose decision conditions both talk and action. Hallucinations cascade through groups; without social awareness, roles blur | One stance read by every layer |
| [Talker-Reasoner](https://arxiv.org/abs/2410.08328) (DeepMind, 2024) | The reasoner writes a structured belief state; the talker answers at once from the latest one | The slow layer writes data, not commands |
| [DPT-Agent](https://arxiv.org/abs/2502.11882) (ACL 2025) | System 1 is a state machine and code-as-policy; System 2 adds theory of mind and asynchronous reflection that adjusts System 1 | The slow layer tunes the fast one |
| [AgileThinker](https://arxiv.org/abs/2511.04898) (ICLR 2026) | Reactive and planning reasoning run at once and beat either alone under time pressure | Keep the asynchronous mind loop |
| [Humanoid Agents](https://arxiv.org/abs/2310.05418) (2023) | Basic needs, emotion and closeness as System 1 numbers that bend plans and talk | Needs and thoughts, as built |
| [Affordable Generative Agents](https://arxiv.org/abs/2402.02053) (2024) | Repeated model decisions become a learned policy; social memory compresses repeated talk | Do not ask the model what it answered last time |
| [Concordia](https://arxiv.org/abs/2507.08892) (DeepMind) | Agents are entities built from components; a game master turns intents into events | Characters as data and components |
| [Versu](https://www.cs.uky.edu/~sgware/reading/papers/evans2014versu.pdf) (Evans, Short) | A social practice offers roles and affordances; each agent still chooses by utility | The evening as a practice; the barkeep as a role |
| [Winnow](https://ojs.aaai.org/index.php/AIIDE/article/view/18903), [Felt](https://github.com/mkremins/felt) (Kreminski) | Story sifting: patterns over the event log find storyful sequences | Measure retellable stories |
| [Persona drift](https://arxiv.org/abs/2402.10962), [Too Good to be Bad](https://arxiv.org/abs/2511.04962) | Instructed personas drift within about eight rounds; models play villains worst | Keep character in numbers, not only text |

## Target design

The slow layer stops writing "what next" in prose. It writes a typed **stance** that the choice,
the local policy and the line writer all read: one bottleneck, as in PIANO.

```
world tick (code): body ───────────────────────────────────────── as now
   │ events
   ▼
stance (in the world, checked by code)
   thought      one sentence, for the inspector and the voice
   goal         a template from a table, e.g. talk_to(edda, topic=fever), avoid(toren)
   topics       facts and people to raise in talk
   commitments  promises made in talk: to whom, what, by when
   │                 │                    │
   ▼                 ▼                    ▼
choice (Jev)     local policy         speech (Haiku)
options that     the same bonus,      sees goal, topics
serve the goal   from the table       and promises
are marked
   ▲
   │ rare triggers: goal done, failed or expired; a strong thought; a new fact on a topic;
   │ arrival; closing; a budget per guest
reflection (Haiku): view + event log → next stance
```

- **Goal templates** are data, like `activities.py`. Each declares the options that serve it,
  the events that complete it, and when it fails or expires. A goal names only templates,
  people and facts that exist, so an intention the world cannot carry out cannot be written.
  Jev sees a mark on the options that serve the goal instead of matching prose.
- **Commitments** extend the invitation protocol, which DESIGN.md already means to carry
  agreements. A promise left unkept by its deadline gives the other guest a thought, which is
  story material.
- **Appraisals** come from a table (`suspects`, `warmed_to`, …) with bounded mood effects, as
  speech acts do. The model names one; the rules apply it. Text alone still changes nothing.
- **Inertia.** A bonus for continuing the current goal, as in utility AI, keeps guests from
  hopping between tables.
- **What stays:** only validated actions change the world, the body buys time for thought, the
  mind runs asynchronously, stale answers are dropped, the near-best draw, and the event log as
  the source of truth.

## Any character in any place

Separate who from where:

- **A character** is a card (text), params and drives (needs, plus motives from traits, as in
  The Sims), and the goal templates open to them. Components (drink, grudge, curiosity) each add
  a line to the briefing and a bonus to the options they favour. A new character is new data, not
  new code.
- **A place** is a social practice, as in Versu: roles (guest, barkeep, bouncer), each role's
  duties and affordances, norms (queue, pay), and the goals that fit. Staff now keep no
  intentions ([intentions.py](../backend/tavern/mind/intentions.py)). As a role, the barkeep
  gets a stance bound by his duties, which also answers D19 (he forgets he is at work).
- **A mind** is the same four ports for everyone: perceive, choose, speak and reflect.

## Measures

| Measure | What it shows | From |
|---|---|---|
| `repetition.restated` | Intentions that repeat the guest's previous one almost word for word: a wasted call or a stuck plan | Step 0 (done) |
| `repetition.repeated` | Lines a speaker has already said tonight | Step 0 (done) |
| Intentions per guest | How often the slow layer runs: `intentions.written` / `guests` | Already logged |
| Goals achieved | Goals completed before they failed or expired | `goals` in `metrics.json` (step 2, done) |
| Unrealizable goals | Goals the world cannot carry out | Zero by construction (step 2, done); the prose can still say anything |
| Say and do | Promises followed by the matching action in time | Step 4 |
| Sameness | Guests holding the same goal template and target at once | Step 2 |
| Stories | Matches of story patterns (a promise broken, a grudge acted on, news passed through three guests) | With E28 |

## Steps

Each step is small, test-first, and checked against the baseline of step 0. None is scheduled
against M4 yet; [PLAN.md](PLAN.md) decides the order.

- [x] **0. Measure.** `evening/repetition.py` counts restated intentions and repeated lines;
  `scripts/evening.py` writes them as `repetition` in `metrics.json`. A text counts as the same
  when at least 0.7 of the two texts' words are shared (words of three letters or more). In the
  live evenings recorded by 2026-10-04, every intention at 0.7 or more kept the previous plan
  almost word for word. The same plan in other words scored 0.57–0.63 or less, so the counts
  are a lower bound. Results (2026-10-05), seven recorded live evenings:

  | Evening | Intentions | Restated | Lines | Repeated | `seat_taken` | Intentions per guest |
  |---|---|---|---|---|---|---|
  | e19-live | 37 | 2 | 23 | 0 | 5 | 6.2 |
  | e19-live-1 | 39 | 2 | 22 | 0 | 4 | 6.5 |
  | g5-live | 36 | 1 | 24 | 0 | 4 | 6.0 |
  | g5-live-1 | 40 | 2 | 26 | 0 | 1 | 6.7 |
  | g5-live-2 | 41 | 4 | 26 | 0 | 0 | 6.8 |
  | g5-live-3 | 38 | 0 | 22 | 0 | 7 | 6.3 |
  | g5-live-7 | 46 | 5 | 27 | 1 | 7 | 7.7 |

  Read by hand in seed 7: of three goals pursued over several intentions (Edda's question,
  Toren's talk, Brida's ale), none was achieved by closing, and one could not be. The offline
  evening (seed 5, scripted lines) repeats 5 of 38 lines.
- [x] **1. The intention reaches speech.** The line writer sees the current intention next to
  the card's goal (`turn_view` gets `speaker.intention`; the moment says "What you mean to do";
  rule 13 of the shared prefix says to raise it and never to offer what it does not say). Check: no
  more restated or repeated, and by hand, a goal raised in talk. Result (2026-10-05, live seed 7,
  replay byte-identical): restated 2, repeated 0 (baseline 5 and 1), 44 intentions, 41 lines, no
  fallbacks. The evening took another course than the baseline's (a barkeep now pours), so only
  the repeats are comparable; goals raised in talk are a by-hand check for step 2's measures.
- [x] **2. Stance and goal templates.** The mind answers with a thought, an intention in words and a
  typed goal (`mind/goals.py`: `GOALS` holds `talk_to` and `sit_with`, each with the options that serve
  it, how it is reached and how long it lasts). The goal's kind and guest are checked at the boundary
  (`intentions.parse_stance`), so an unrealizable goal is refused. Options that serve the goal are
  marked for Jev (briefing) and score `GOAL_BONUS` higher in the local policy; `settle_goals` ends each
  goal once as `done` (`talk_to`: a line heard from them since; `sit_with`: one table), `failed` (they
  left) or `expired`, and logs it; a goal's end is a trigger to take stock. Saved worlds are version 11
  (approved bump), and the inspector shows the goal. New `goals` in `metrics.json`: set, done, failed,
  expired. Tests named for the change: `test_database.py` (version), `test_intention_saves.py`,
  `test_dice_intentions.py` and `test_intentions.py` (the intention carries a `goal`, the answer has
  four fields). Result (2026-10-05, live seed 7, replay byte-identical; offline seed 5 sets no goals):
  30 goals set, 7 done, 0 failed, 1 expired, 56 intentions (44 in step 1), restated 2, repeated 0. Most
  goals ended replaced by a newer intention: Brida set out to sit with Edda seven times between 41 s
  and 151 s, once for each scene's end, which is what step 3 changes. Not done here: `avoid` and other
  kinds (the table takes them as entries), the unrealizable-intention count for the prose itself, and
  sameness at arrival.
- [ ] **3. Take stock on surprise.** Triggers are a goal's end, a strong thought, a new fact on
  a topic, arrival and closing, under a budget per guest; a scene's end alone no longer counts.
  Check: fewer intentions per guest, and goals achieved no lower.
- [ ] **4. Commitments.** A promise in talk becomes a commitment; an unkept one gives a
  thought. Check: say and do.
- [ ] **5. Practices and roles.** The evening as a practice; the barkeep gets a stance bound by
  his duties. Check: D19 lines gone.
- [ ] **6. Between evenings (Stage 4).** Each guest's evening is summarized into memories and
  opinions that carry over, dropping what repeats, as Lyfe's summarize-and-forget does.

Missing verbs found on the way go to their own tasks. The first is "buy someone a drink"
(DESIGN.md, Actions), which 17 intentions in five of the seven evenings asked for. It became
[Giving (H0–H5)](stages/1_EVENING.md#giving--from-hand-to-hand-h0h5): anything a guest carries
can be handed to another, and fetching a drink for someone is one chosen errand.

## Sources

- Park et al., [Generative Agents](https://arxiv.org/abs/2304.03442) (2023)
- Kaiya et al., [Lyfe Agents](https://arxiv.org/abs/2310.02172) (2023)
- Altera, [Project Sid](https://arxiv.org/abs/2411.00114) (2024)
- Christakopoulou et al., [Agents Thinking Fast and Slow: A Talker-Reasoner Architecture](https://arxiv.org/abs/2410.08328) (2024)
- Zhang et al., [DPT-Agent](https://arxiv.org/abs/2502.11882) (ACL 2025)
- Wen et al., [Real-Time Reasoning Agents in Evolving Environments](https://arxiv.org/abs/2511.04898) (ICLR 2026)
- Wang et al., [Humanoid Agents](https://arxiv.org/abs/2310.05418) (EMNLP 2023 demo)
- Yu et al., [Affordable Generative Agents](https://arxiv.org/abs/2402.02053) (TMLR 2024)
- Vezhnevets et al., [Multi-Actor Generative AI as a Game Engine](https://arxiv.org/abs/2507.08892) (Concordia, 2025)
- Evans and Short, [Versu](https://www.cs.uky.edu/~sgware/reading/papers/evans2014versu.pdf) (2014)
- Kreminski et al., [Winnow](https://ojs.aaai.org/index.php/AIIDE/article/view/18903) (AIIDE 2021), [Felt](https://github.com/mkremins/felt)
- Li et al., [Measuring and Controlling Instruction (In)Stability in Language Model Dialogs](https://arxiv.org/abs/2402.10962) (2024)
- [Too Good to be Bad: On the Failure of LLMs to Role-Play Villains](https://arxiv.org/abs/2511.04962) (2025)
- Cemri et al., [Why Do Multi-Agent LLM Systems Fail?](https://arxiv.org/abs/2503.13657) (2025)
- [The Genius AI Behind The Sims](https://gameindustrylibrary.com/documents/gmtk-the-genius-ai-behind-the-sims) (GMTK)
- TypeSafe, [System One models and Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
