import { describe, expect, it } from "vitest";
import { worldSentence } from "./sentence";

describe("worldSentence", () => {
  it.each([
    [{ slipped: 0, watched: 0, waiting: 0 }, "Nothing has slipped. I am not watching anything yet."],
    [{ slipped: 0, watched: 1, waiting: 0 }, "Nothing has slipped. I am watching one concern."],
    [{ slipped: 1, watched: 4, waiting: 0 }, "One promise slipped. I am watching four concerns."],
    [{ slipped: 2, watched: 11, waiting: 0 }, "Two promises slipped. I am watching 11 concerns."],
    [{ slipped: 2, watched: 11, waiting: 1 }, "Two promises slipped. I am watching 11 concerns. One decision is waiting on you."],
    [{ slipped: 0, watched: 3, waiting: 3 }, "Nothing has slipped. I am watching three concerns. Three decisions are waiting on you."],
    [{ slipped: 12, watched: 20, waiting: 10 }, "12 promises slipped. I am watching 20 concerns. 10 decisions are waiting on you."],
  ])("%j", (counts, text) => {
    expect(worldSentence(counts)).toBe(text);
  });
});
