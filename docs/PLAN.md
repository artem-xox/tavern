# The Last Inn — Prototype Plan

Build the smallest playable prototype that tests the central question in
[DESIGN.md](DESIGN.md). Each stage has an observable completion criterion.

## 0. Validate agents in a browser tavern — done

Phaser/TypeScript frontend and Python/FastAPI backend. Visitors move, drink, sit, chat,
play darts, use the WC, and go home, with Jev scoring their options from a plain-language
briefing. See [Stage 0](stages/0_DEMO.md).

## 1. A believable evening

Four to six guests from character cards spend one evening in the hall. They queue,
react to noise, talk through Claude Haiku 4.5 with speech acts, pass on news, get drunk,
and sometimes shove or fight. The player only sets up the evening and watches.
See [Stage 1 tasks](stages/1_EVENING.md).

**Done when:** recorded live evenings meet the Stage 1 metrics, an observer can retell
a story from at least one of them, and its chronicle cites only logged events.

## 2. Staff and commands

Add a barkeep and a bouncer whose actions use the same activity system, and let the
player give them commands: serve, refill, calm someone down, throw someone out.

**Done when:** a player command changes how an evening's incident ends.

## 3. The inn's economy

Guests carry money; drinks and food have prices; supplies run out and are restocked;
tabs, tips, and damage cost or earn money.

**Done when:** an evening ends with a ledger the player can trace to guests' actions.

## 4. Several evenings and agreements

Guests return as regulars. The evening is summarized into memories, opinions persist,
and invitations from conversations can become validated obligations: debts, deliveries,
meetings. Saving and loading preserve them.

**Done when:** an agreement made in one evening changes a guest's behavior in the next
and creates a new situation for the player.

Expand property, the yard, and lodging after this loop works.
