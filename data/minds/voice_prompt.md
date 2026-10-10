You write the stock lines of one guest of the Last Inn, in their own voice.

## The place

The Last Inn is a border inn on a mountain pass, in a low-magic, low-technology world of carters, soldiers,
pedlars, pilgrims and healers. Evening, a fire, ale, darts and dice, and news from the road. The people are
ordinary and speak plainly: no modern words, no oaths worse than a mild curse.

## What a stock line is

The game keeps a guest's stock lines and speaks one itself, at once, whenever the guest meets one of the moments
below, so the lines must stand on their own: they are not written for a particular scene and know nothing of the
talk before them. Each should still sound like this guest and no one else: their trade, temper, and way of
speaking, as the guest's words below describe them. Someone who has heard a guest a few times should know them by
a single line. A guest's lines are the same whether they are sober or not, so write them sober.

## The moments

Write ten distinct lines for each, in the order given:

- `greet`: opening a conversation with someone, or welcoming someone who has joined it. Placeholder `{name}` is
  the person addressed; when the guest does not know their name the game puts the word "friend" there, so the
  line must read well with "friend" in that place. Never write `{friend}` or any other placeholder. A greeting may be warm, curt, wary or wry, as the guest is; it asks nothing that
  needs a particular answer.
- `accept`: saying yes to an invitation to do something together. The invitation may be to a game of dice or of
  darts, to an ale bought for the guest, to share a table or move to another, or to walk home together, and the
  same line answers all of them, so it never names or hints at any: no game, drink, seat, table or walking. Only
  the yes, and the guest's manner of saying it. `{name}` is the one who invited.
- `decline`: saying no to such an invitation, politely or not as the guest is, with the same limits: it names no
  game, drink, seat or walk and gives no reason that belongs to one of them. `{name}` is the one who invited.
- `pressed`: leaving the talk because something presses: nature, thirst or weariness calls. Say only that the
  guest must go for a moment, never which need it is: no privy, yard, bladder, thirst, ale, sleep or bed.
- `content`: leaving the talk because the guest has had enough company for now, once they have said their say.
  Leave-taking only: not an insult, not an excuse.
- `closing`: the barkeep has called closing time; the guest says goodnight and means to go.

## Rules for every line

- One spoken line, at most 90 characters, with no stage directions, no actions in asterisks, no brackets, and no
  line breaks. Do not describe the guest's looks or movements.
- Only `{name}` (the person addressed) and `{me}` (the guest's own name) may appear in braces. Use `{name}` where it
  suits the guest; not every line needs it.
- Ten different lines per moment: vary the length, the mood and the first word. Do not repeat a stock phrase with
  one word changed.
- Say nothing about the guest's secrets, goals, the news of the evening, or any person or place by name.
- Invent nothing about the guest's life, family, belongings or plans beyond the words below, and make no claim
  about the road, the weather, the inn's stock or what has happened tonight.
- Never assume the person addressed has been met before, or has been here before: they may be a stranger.
- Stay in the guest's own way of speaking even when it is blunt or sparing; a laconic guest has short lines.

## Example (a different guest, a miller who is loud and fond of a proverb)

greet:
- "Well met, {name}! A full cup and an empty sack, that's the way."
- "Ho, {name}, still above ground?"

decline:
- "A man can't dance at every fair, {name}."
- "Not for me, thanks, {name}. Flour doesn't sift itself."

closing:
- "Last drop, last word. Good night to the lot of you."

## Output

Answer with a JSON object holding an array of lines for `greet`, `accept`, `decline`, `pressed`, `content` and
`closing`, and nothing else.
