# The Last Inn — Prototype Plan

Build the smallest playable prototype that tests the central question in
[DESIGN.md](DESIGN.md). Each stage has an observable completion criterion.

## 1. Define the prototype rules

Choose the engine and define the three NPCs, their overlapping goals, available
actions, inventory rules, and agreement terms: parties, obligations, compensation,
deadlines, and status. Keep the initial item and action sets small.

**Done when:** a delivery-for-lodging example can be described entirely through these
rules, including rejection, completion, and a missed deadline.

## 2. Build the playable inn and shared simulation

Add the inn and yard, player and NPC movement, inventory, money, cooking, meals,
lodging, and a day cycle. Route actions through game-owned validation and execution.
Add saving and loading for this state.

**Done when:** the player can obtain ingredients, make a meal, sell it, rent a room,
and reload with resources and time preserved.

## 3. Connect conversations to persistent agreements

Add dialogue generation, structured offers and acceptance, obligation tracking,
relationships, memories, and individual NPC knowledge. Show active terms and outcomes
in a simple agreement record. Extend saving to preserve these systems.

**Done when:** a conversation creates a validated agreement, and its obligations,
completion or failure, and character knowledge survive saving and loading.

## 4. Make the three NPCs autonomous

Generate feasible actions from each NPC's observations and state. Integrate Jev
evaluations and controlled stochastic selection. Reconsider plans after tasks and
meaningful events; make accepted commitments influence behavior.

**Done when:** the cook, courier, and trader act independently, with limited knowledge,
and their actions change shared resources and agreement state.

## 5. Validate the emergent story loop

Play a small situation: the inn needs ingredients, the courier needs lodging, and the
cook needs supplies. Negotiate a delivery for lodging and observe its consequences.
Try successful delivery and delay, allowing further decisions and offers to emerge.

**Done when:** the agreement changes the courier's behavior, affects the cook, and
creates a new decision for the player without a fixed quest sequence. The player can
understand why it happened, and saving and loading preserve the consequences.

Expand content and property management after this loop works.
