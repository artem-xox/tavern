/** How drink slurs a guest's line in their bubble: an s gone soft, a drawl and a hiccup. Only the bubble changes; the log keeps the words said. */
import type { Mind } from "./types.ts";

const HIC = "*hic*";
/** A wasted guest trails off one of these, picked by the line so the same line always ends the same way. */
const TAILS: readonly string[] = [HIC, `${HIC} …oh.`];
/** An s or S not already followed by an h. */
const SOFT_S = /([sS])(?![hH])/g;
const VOWEL = /[aeiou]/i;

/** A word with every soft s slurred to sh. */
function slurWord(word: string): string {
  return word.replace(SOFT_S, (_match: string, letter: string): string => `${letter}h`);
}

/** A word with its first vowel drawn out to three. */
function drawl(word: string): string {
  return word.replace(VOWEL, (vowel: string): string => vowel.repeat(3));
}

/** The index of the word with the most letters; the first on a tie. */
function longest(words: readonly string[]): number {
  const letters = (word: string): number => word.replace(/[^a-z]/gi, "").length;
  return words.reduce((best: number, word: string, index: number): number => letters(word) > letters(words[best]!) ? index : best, 0);
}

/**
 * Slur a line as a guest at this stage of drink would say it.
 *
 * A drunk guest slurs the first word with a soft s and hiccups after it (after the first word when none has one).
 * A wasted guest slurs every s, drawls their longest word, hiccups after the first slurred word and trails off.
 * The same line at the same stage always slurs the same way, so a bubble does not flicker between redraws.
 *
 * @param line The words as the guest said them.
 * @param stage The guest's stage of drink, as the server names it.
 * @returns The line as the bubble shows it; unchanged when sober or tipsy, or when empty.
 */
export function slur(line: string, stage: Mind["stage"]): string {
  if (line === "" || stage === "sober" || stage === "tipsy") return line;
  const words: string[] = line.split(" ");
  const first: number = Math.max(0, words.findIndex((word: string): boolean => slurWord(word) !== word));
  if (stage === "drunk") {
    words[first] = `${slurWord(words[first]!)} ${HIC}`;
    return words.join(" ");
  }
  const drawn: number = longest(words);
  const slurred: string[] = words.map((word: string, index: number): string => {
    const soft: string = slurWord(index === drawn ? drawl(word) : word);
    return index === first ? `${soft} ${HIC}` : soft;
  });
  return `${slurred.join(" ")} ${TAILS[line.length % TAILS.length]}`;
}
