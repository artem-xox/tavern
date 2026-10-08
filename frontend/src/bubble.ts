/** Speech bubbles: where one sits over its speaker, kept whole inside the map. */

/** Pixels the bubble keeps clear of the map edge, and its gap above a speaker's head or below their feet. */
const MARGIN = 4;
const ABOVE = 66;
const BELOW = 22;

/** Where to draw a bubble: its anchor point, and which edge of the bubble sits there (1 bottom, 0 top). */
export interface BubblePlacement {
  x: number;
  y: number;
  originY: 0 | 1;
}

/**
 * Place a bubble above a speaker, or below them when there is no room above.
 *
 * @param speakerX Speaker's x in map pixels.
 * @param speakerY Speaker's y in map pixels.
 * @param width Bubble width in pixels.
 * @param height Bubble height in pixels.
 * @param map Map size in pixels.
 * @returns Centre x, and the y of the bubble's bottom edge (above) or top edge (below). A bubble wider
 *   than the map is centred on it.
 */
export function placeBubble(speakerX: number, speakerY: number, width: number, height: number,
                            map: { width: number; height: number }): BubblePlacement {
  const half: number = width / 2;
  const x: number = map.width < width + 2 * MARGIN ? map.width / 2 : Math.min(Math.max(speakerX, MARGIN + half), map.width - MARGIN - half);
  if (speakerY - ABOVE - height >= MARGIN) return { x, y: speakerY - ABOVE, originY: 1 };
  return { x, y: Math.max(MARGIN, Math.min(speakerY + BELOW, map.height - MARGIN - height)), originY: 0 };
}

/** A piece holds whole sentences while it stays within this many characters, about three lines of the bubble. */
const MAX_PIECE_CHARS = 90;
/** A part cut from a long sentence leaves room for the ellipsis at each end. */
const MAX_PART_CHARS = MAX_PIECE_CHARS - 2;
const ELLIPSIS = "…";
/** A word ends a sentence at `.`, `!`, `?` or `…`, with any closing quote or bracket after it. */
const SENTENCE_END = /[.!?…]["'”’)\]»]*$/;
/** A word ends a clause at a comma, semicolon, colon or dash: the best place to cut a long sentence. */
const CLAUSE_END = /[,;:\u2013\u2014-]$/;
/** How many characters off the even cut a break after a clause may be, and still win. */
const CLAUSE_BONUS = 15;
/** Reading speed for a piece, in characters per second (the server's `chars_per_second`), and the least it stays up. */
const READ_CHARS_PER_SECOND = 15;
const MIN_CHUNK_MS = 1500;

/** The text of some words, as it is shown. */
function textOf(words: readonly string[]): string {
  return words.join(" ");
}

/** Group a line's words into sentences; a last sentence may lack an end mark. */
function sentencesOf(words: readonly string[]): string[][] {
  const sentences: string[][] = [];
  let current: string[] = [];
  for (const word of words) {
    current.push(word);
    if (SENTENCE_END.test(word)) { sentences.push(current); current = []; }
  }
  if (current.length > 0) sentences.push(current);
  return sentences;
}

/**
 * Where to cut `words` so that the first part is about `1 / parts` of them: after a clause when one is near,
 * leaving at least two words on each side (a one-word tail reads as an accident).
 *
 * @returns How many words the first part takes; all of them when they are too few to cut.
 */
function cutAfter(words: readonly string[], parts: number): number {
  const target: number = textOf(words).length / parts;
  let best: number = words.length;
  let bestScore: number = Infinity;
  for (let at: number = 2; at <= words.length - 2; at += 1) {
    const length: number = textOf(words.slice(0, at)).length;
    const score: number = Math.abs(length - target) - (CLAUSE_END.test(words[at - 1]!) ? CLAUSE_BONUS : 0) + (length > MAX_PART_CHARS ? 1000 : 0);
    if (score < bestScore) { best = at; bestScore = score; }
  }
  return best;
}

/** Cut a sentence over the limit into even parts, each but the last ending in an ellipsis and each but the first starting with one. */
function cutSentence(words: readonly string[]): string[] {
  const parts: string[] = [];
  let rest: readonly string[] = words;
  for (let left: number = Math.ceil(textOf(rest).length / MAX_PART_CHARS); left > 1; left -= 1) {
    const at: number = cutAfter(rest, left);
    if (at === rest.length) break;
    parts.push(textOf(rest.slice(0, at)));
    rest = rest.slice(at);
  }
  parts.push(textOf(rest));
  return parts.map((part: string, index: number): string => `${index > 0 ? ELLIPSIS : ""}${part}${index < parts.length - 1 ? ELLIPSIS : ""}`);
}

/**
 * Split a line into pieces that each end where a sentence does, so a bubble never stops mid-sentence.
 *
 * Whole sentences share a piece while it stays within `MAX_PIECE_CHARS`. Only a sentence longer than that is
 * cut, at a clause when one is near, with an ellipsis where it breaks. A line's last piece may be a cut one's
 * tail plus the sentences after it. "Mr." and the like end a sentence for this purpose; a line is one
 * sentence when it has no end mark.
 *
 * @param line One spoken line.
 * @returns The line's pieces in order; empty for an empty line.
 */
export function splitLine(line: string): string[] {
  const words: string[] = line.split(/\s+/).filter((word: string): boolean => word !== "");
  const pieces: string[] = [];
  let group: string = "";
  for (const sentence of sentencesOf(words)) {
    const text: string = textOf(sentence);
    if (group !== "" && group.length + 1 + text.length <= MAX_PIECE_CHARS) { group = `${group} ${text}`; continue; }
    if (group !== "") pieces.push(group);
    if (text.length <= MAX_PIECE_CHARS) { group = text; continue; }
    const parts: string[] = cutSentence(sentence);
    pieces.push(...parts.slice(0, -1));
    group = parts[parts.length - 1]!;
  }
  if (group !== "") pieces.push(group);
  return pieces;
}

/** How long a piece is shown, in milliseconds; the ellipses added at a cut are not read. */
export function chunkMs(chunk: string): number {
  return Math.max(MIN_CHUNK_MS, chunk.replaceAll(ELLIPSIS, "").length / READ_CHARS_PER_SECOND * 1000);
}

/**
 * Which piece is up `elapsedMs` after the line began.
 *
 * @param chunks Pieces of the line, at least one.
 * @param elapsedMs Milliseconds since the first piece appeared.
 * @returns Index of the piece to show; the last one once all have had their time.
 */
export function chunkAt(chunks: readonly string[], elapsedMs: number): number {
  let left: number = elapsedMs;
  for (let index: number = 0; index < chunks.length - 1; index += 1) {
    left -= chunkMs(chunks[index]!);
    if (left < 0) return index;
  }
  return chunks.length - 1;
}
