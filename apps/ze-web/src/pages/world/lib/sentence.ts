export interface SentenceCounts {
  slipped: number;
  watched: number;
  waiting: number;
}

const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];
const word = (n: number) => WORDS[n] ?? String(n);
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Ze's one sentence on World, built from counts and never generated. */
export function worldSentence({ slipped, watched, waiting }: SentenceCounts): string {
  const parts: string[] = [];
  parts.push(slipped === 0 ? "Nothing has slipped." : `${cap(word(slipped))} ${slipped === 1 ? "promise" : "promises"} slipped.`);
  parts.push(watched === 0 ? "I am not watching anything yet." : `I am watching ${word(watched)} ${watched === 1 ? "concern" : "concerns"}.`);
  if (waiting > 0) parts.push(`${cap(word(waiting))} ${waiting === 1 ? "decision is" : "decisions are"} waiting on you.`);
  return parts.join(" ");
}
