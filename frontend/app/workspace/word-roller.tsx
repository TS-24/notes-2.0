import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useFetcher } from "react-router";
import { motion } from "framer-motion";
import { ChevronUp, ChevronDown } from "lucide-react";
import type { WordLadder } from "~/lib/types";

/**
 * The chevrons that appear above and below the word the caret is sitting in,
 * and the slot-machine roll that swaps that word out.
 *
 * A textarea gives no way to ask where a word is on screen, so the position
 * comes from a mirror: a hidden div that copies the field's box and typography
 * exactly, with the target word wrapped in a span we can measure. The mirror
 * has to sit at the field's origin, which is why the field needs a tightly
 * fitting relative wrapper.
 */

/** Letters, digits, and the punctuation that lives inside a word. */
const WORD_CHAR = /[\p{L}\p{N}'’-]/u;

/**
 * The chevron buttons' hit area, and how far it clears the word. Sized so the
 * 16px chevron keeps the centre it has always had: half of `height` plus `GAP`
 * is the 11px the mark sits from the edge of the word.
 */
const HIT = { width: 40, height: 20 };
const GAP = 1;

/** Styles the mirror must copy for its line breaks to match the field's. */
const MIRRORED_STYLES = [
  "boxSizing",
  "width",
  "fontFamily",
  "fontSize",
  "fontWeight",
  "fontStyle",
  "fontVariant",
  "letterSpacing",
  "wordSpacing",
  "lineHeight",
  "textAlign",
  "textIndent",
  "textTransform",
  "paddingTop",
  "paddingRight",
  "paddingBottom",
  "paddingLeft",
  "borderTopWidth",
  "borderRightWidth",
  "borderBottomWidth",
  "borderLeftWidth",
] as const;

export type WordSpan = {
  start: number;
  end: number;
  word: string;
  left: number;
  top: number;
  width: number;
  height: number;
  /** The field's typography, so the reel renders the word identically. */
  type: {
    fontFamily: string;
    fontSize: string;
    fontWeight: string;
    fontStyle: string;
    letterSpacing: string;
    color: string;
  };
};

/** The word the caret is inside, or null when it is not in one. */
function wordAtCaret(value: string, caret: number) {
  let start = caret;
  let end = caret;
  while (start > 0 && WORD_CHAR.test(value[start - 1])) start--;
  while (end < value.length && WORD_CHAR.test(value[end])) end++;
  if (start === end) return null;
  return { start, end, word: value.slice(start, end) };
}

function measure(
  field: HTMLTextAreaElement,
  value: string,
  start: number,
  end: number,
) {
  const styles = getComputedStyle(field);
  const mirror = document.createElement("div");
  for (const property of MIRRORED_STYLES) {
    mirror.style[property] = styles[property];
  }
  mirror.style.position = "absolute";
  mirror.style.top = "0";
  mirror.style.left = "0";
  mirror.style.visibility = "hidden";
  mirror.style.pointerEvents = "none";
  // Match how a textarea wraps.
  mirror.style.whiteSpace = "pre-wrap";
  mirror.style.overflowWrap = "break-word";

  const target = document.createElement("span");
  target.textContent = value.slice(start, end);
  mirror.append(
    document.createTextNode(value.slice(0, start)),
    target,
    // A trailing newline is not rendered, so give the last line something to
    // hold its height.
    document.createTextNode(`${value.slice(end)}​`),
  );

  field.parentElement?.appendChild(mirror);
  const origin = mirror.getBoundingClientRect();
  const box = target.getBoundingClientRect();
  mirror.remove();

  return {
    left: box.left - origin.left,
    top: box.top - origin.top,
    width: box.width,
    height: box.height,
    // The reel sits outside the field, so it inherits the surface's type
    // rather than the field's — which is wrong by a lot on the display-face
    // title. Carry the field's own typography across.
    type: {
      fontFamily: styles.fontFamily,
      fontSize: styles.fontSize,
      fontWeight: styles.fontWeight,
      fontStyle: styles.fontStyle,
      letterSpacing: styles.letterSpacing,
      color: styles.color,
    },
  };
}

/**
 * Where the replacement comes from: a ladder of synonyms ordered plainest to
 * rarest, fetched once per word from `/api/word-ladder`. Up climbs toward the
 * rarer, more formal end; down walks back toward the plain one.
 */
type Climb = {
  /** Plainest first — the ladder as the backend built it. */
  rungs: string[];
  /** Which rung the field is showing right now. */
  at: number;
};

/** Worth asking the backend about? Numbers and stray punctuation are not. */
function isWorthLookingUp(word: string) {
  return word.length <= 64 && /\p{L}/u.test(word);
}

/** How far either side of the caret to look for a sentence boundary. */
const CONTEXT_LIMIT = 400;

/** How long the caret has to hold still before the backend is asked about it. */
const SETTLE_DELAY = 350;

/**
 * `value`, but only once it has held still for `delay`.
 *
 * The caret passes through a great many words on its way to the one the writer
 * means: every character of a word being typed is a different question, and so
 * is every position an arrow key travels through. Asking each of them meant one
 * request per keystroke against a backend that has to consult WordNet and rank
 * the senses — and they queue, so the tenth answer came back slower than the
 * first, for a word the caret had long since left. Waiting for the caret to
 * settle asks once, about the word actually landed on.
 */
function useSettled<T>(value: T, delay: number) {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return settled;
}

/**
 * The sentence around an offset, and where that sentence starts in the field.
 *
 * The backend resolves the caret to a *unit* — which may be a phrase, or a word
 * with its article — and answers in sentence coordinates, so the offset of the
 * sentence is needed to map the answer back onto the field.
 */
function sentenceAround(value: string, at: number) {
  const BOUNDARY = ".!?\n";
  const before = value.slice(Math.max(0, at - CONTEXT_LIMIT), at);
  const after = value.slice(at, at + CONTEXT_LIMIT);

  // -1 when the window holds no boundary at all, which lands `from` at the
  // start of the window — the behaviour we want.
  const opensAt = Math.max(...[...BOUNDARY].map(mark => before.lastIndexOf(mark)));
  const closesAt = [...after].findIndex(character => BOUNDARY.includes(character));
  const rawFrom = at - (before.length - opensAt - 1);
  const to = at + (closesAt === -1 ? after.length : closesAt + 1);

  const slice = value.slice(rawFrom, to);
  // Trimming shifts the sentence right, so the field offset moves with it.
  const from = rawFrom + (slice.length - slice.trimStart().length);
  return { sentence: slice.trim(), from };
}

export default function WordRoller({
  fieldRef,
  value,
  background,
  onReplace,
}: {
  fieldRef: React.RefObject<HTMLTextAreaElement | null>;
  value: string;
  /**
   * What the reel masks the live word with. It has to be the surface the field
   * actually sits on, which is not the same colour on the two pages: the
   * landing page is bare paper, the boxed note is paper-raised.
   */
  background: string;
  /** Swap the range for a new word. */
  onReplace: (start: number, end: number, word: string) => void;
}) {
  const [span, setSpan] = useState<WordSpan | null>(null);
  const [roll, setRoll] = useState<{
    span: WordSpan;
    to: string;
    direction: 1 | -1;
  } | null>(null);
  const rollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [climb, setClimb] = useState<Climb | null>(null);
  /*
    The unit currently being climbed, held across re-locates.

    `wordAtCaret` only ever finds a single word, so once the span has been
    widened to a unit — "a model", "gave up" — every caret move would shrink it
    straight back and the climb would lose its anchor, leaving "down" dead after
    the first press. This remembers the wider span so `locate` can keep it for
    as long as the text still says what we put there.
  */
  const unit = useRef<{ start: number; end: number; word: string } | null>(null);

  const locate = useCallback(() => {
    const field = fieldRef.current;
    if (!field || document.activeElement !== field) {
      setSpan(null);
      return;
    }
    // A field with no width yet measures as one character per line, which
    // would scatter the chevrons — the same trap the auto-height hook hits.
    if (field.clientWidth === 0) {
      setSpan(null);
      return;
    }
    // Only a plain caret, not a selection the user is working with.
    if (field.selectionStart !== field.selectionEnd) {
      setSpan(null);
      return;
    }
    // Keep the wider unit span while the caret is still inside it and the text
    // still reads as we left it.
    const held = unit.current;
    const caret = field.selectionStart;
    if (
      held &&
      caret >= held.start &&
      caret <= held.end &&
      field.value.slice(held.start, held.end) === held.word
    ) {
      setSpan({ ...held, ...measure(field, field.value, held.start, held.end) });
      return;
    }
    unit.current = null;

    const found = wordAtCaret(field.value, field.selectionStart);
    if (!found) {
      setSpan(null);
      return;
    }
    setSpan({ ...found, ...measure(field, field.value, found.start, found.end) });
  }, [fieldRef]);

  useEffect(() => {
    const field = fieldRef.current;
    if (!field) return;
    // selectionchange is the only event that catches every caret move —
    // arrows, clicks, and typing alike.
    document.addEventListener("selectionchange", locate);
    field.addEventListener("focus", locate);
    field.addEventListener("blur", locate);
    const observer = new ResizeObserver(locate);
    observer.observe(field);
    return () => {
      document.removeEventListener("selectionchange", locate);
      field.removeEventListener("focus", locate);
      field.removeEventListener("blur", locate);
      observer.disconnect();
    };
  }, [fieldRef, locate]);

  // Re-locate when the text changes underneath the caret.
  useEffect(() => {
    locate();
  }, [value, locate]);

  useEffect(
    () => () => {
      if (rollTimer.current) clearTimeout(rollTimer.current);
    },
    [],
  );

  const word = span?.word;
  const lookup = word && isWorthLookingUp(word) ? word : null;
  // The sentence the caret sits in, and where that sentence starts in the
  // field — the backend answers in sentence coordinates.
  const context = span ? sentenceAround(value, span.start) : null;
  const caretInSentence = context && span ? span.start - context.from : null;

  /*
    What to ask about, and where the answer will map back to — held still.

    Memoised on the primitives, so its identity changes only when the question
    does; that is what lets `useSettled` recognise a caret that has stopped
    moving. Everything the reader can see keeps tracking the caret immediately —
    only the round trip waits.
  */
  const question = useMemo(
    () =>
      lookup && context && caretInSentence !== null
        ? { sentence: context.sentence, caret: caretInSentence, from: context.from }
        : null,
    [lookup, context?.sentence, caretInSentence, context?.from],
  );
  const settled = useSettled(question, SETTLE_DELAY);

  /*
    One fetcher per unit, keyed by the sentence and the caret in it.

    The caret can cross several words faster than the network answers for any of
    them, and a single shared fetcher keeps only the most recent response — so a
    slow reply for a word the caret has already left can land on top of the word
    it is on now. Keying makes that impossible rather than merely unlikely, and
    it doubles as a cache: returning to a word already visited needs no request.
  */
  const ladder = useFetcher<{ ladder: WordLadder | null }>({
    key: `word-ladder:${settled?.sentence ?? ""}:${settled?.caret ?? ""}`,
  });

  /*
    The climb, but only while it still describes the word under the caret.

    Replacing a word moves the caret into the *replacement*: roll "use" to
    "utilise" and the caret now sits in "utilise". That has to keep climbing the
    same ladder — otherwise pressing down would not walk back to "use" and a few
    presses would wander off somewhere unrelated. Checking the rung against the
    word does both jobs: it holds the climb across our own replacement, and it
    drops it the moment the caret lands somewhere genuinely different.
  */
  const current = climb && climb.rungs[climb.at] === word ? climb : null;

  useEffect(() => {
    if (!settled || current) return;
    // Nothing in flight and nothing already fetched for this unit.
    if (ladder.state !== "idle" || ladder.data) return;
    const query = new URLSearchParams({
      sentence: settled.sentence,
      caret: String(settled.caret),
    });
    ladder.load(`/api/word-ladder?${query}`);
  }, [settled, current, ladder]);

  /*
    Adopt the unit the backend resolved to.

    It is often wider than the word under the caret — "give up" rather than
    "up", "an example" rather than "example" — and everything downstream keys off
    `span`: where the chevrons sit, what the reel masks, what gets replaced. So
    widen the span to the unit and carry its text as the word, which also keeps
    the climb anchor working, since the rungs are unit text too.
  */
  useEffect(() => {
    if (current) return;
    const fetched = ladder.data?.ladder;
    if (!fetched || !fetched.rungs.length || !settled) return;

    const field = fieldRef.current;
    // The settled question, not the live one: these offsets are in the
    // coordinates of the sentence that was actually asked about, and the
    // writer may have typed on since.
    const start = settled.from + fetched.start;
    const end = settled.from + fetched.end;
    if (!field || field.value.slice(start, end) !== fetched.word) return;

    setClimb({ rungs: fetched.rungs, at: fetched.origin_index });
    unit.current = { start, end, word: fetched.word };
    setSpan(previous =>
      previous && previous.start === start && previous.end === end
        ? previous
        : {
            start,
            end,
            word: fetched.word,
            ...measure(field, field.value, start, end),
          },
    );
  }, [ladder.data, settled, current, fieldRef]);

  /** Where a press would land, or null when that end of the ladder is reached. */
  const rungAfter = (step: 1 | -1) => {
    if (!current) return null;
    const next = current.at + step;
    return next >= 0 && next < current.rungs.length ? next : null;
  };

  // `step` is movement along the ladder: +1 rarer, -1 plainer.
  const startRoll = (step: 1 | -1) => {
    if (!span || roll || !current) return;
    const next = rungAfter(step);
    if (next === null) return;
    // Resolved once, here: the reel shows this word and the commit below writes
    // the same one, so what lands is what was shown.
    const to = current.rungs[next];
    setRoll({ span, to, direction: step === 1 ? -1 : 1 });
    rollTimer.current = setTimeout(() => {
      setClimb({ ...current, at: next });
      // The unit is now the replacement, and it has to be held under that name
      // or the next re-locate shrinks it back to a single word.
      unit.current = { start: span.start, end: span.start + to.length, word: to };
      // Move the span onto the new word in the same batch as the climb.
      // Without this the two disagree for a render — the climb has advanced to
      // "model" while the span still says "example" — and in that window the
      // climb reads as belonging to some other word, which is enough for the
      // effects below to throw it away and start a fresh one. `locate` corrects
      // the measurements a moment later; what matters here is that the word
      // never lags behind the rung.
      setSpan(prev =>
        prev ? { ...prev, word: to, end: prev.start + to.length } : prev,
      );
      onReplace(span.start, span.end, to);
      setRoll(null);
    }, 460);
  };

  const active = roll?.span ?? span;
  if (!active) return null;

  // The reel is three deep so the word passes twice before landing, which is
  // what makes it read as a spin rather than a nudge.
  const REEL = 3;
  const centre = active.left + active.width / 2;

  return (
    <>
      {/*
        Underline what a press would replace.

        With phrases in play the unit is no longer obviously the word under the
        caret — "running through the park" resolves to the phrasal verb "running
        through", which is a defensible reading of the words and the wrong
        reading of the sentence. Nothing in the lexicon can tell those apart, so
        the honest fix is to show the selection rather than to guess in silence.
      */}
      {!roll && current ? (
        <div
          aria-hidden
          className="pointer-events-none absolute bg-rose-ink/10"
          style={{
            left: active.left,
            top: active.top + active.height - 2,
            width: active.width,
            height: 2,
          }}
        />
      ) : null}

      {roll ? (
        <div
          aria-hidden
          className="pointer-events-none absolute overflow-hidden"
          style={{
            left: active.left,
            top: active.top,
            width: active.width,
            height: active.height,
            background,
            ...active.type,
          }}
        >
          <motion.div
            initial={{ y: roll.direction === 1 ? 0 : -(REEL - 1) * active.height }}
            animate={{ y: roll.direction === 1 ? -(REEL - 1) * active.height : 0 }}
            transition={{ duration: 0.46, ease: [0.16, 1, 0.3, 1] }}
          >
            {Array.from({ length: REEL }, (_, i) => (
              <div
                key={i}
                style={{ height: active.height, lineHeight: `${active.height}px` }}
              >
                {/*
                  The new word goes in whichever cell the reel comes to rest on:
                  the last one when the strip travels up, the first when it
                  travels down. Every other cell repeats the old word, which is
                  what makes the spin read as a spin.
                */}
                {i === (roll.direction === 1 ? REEL - 1 : 0) ? roll.to : active.word}
              </div>
            ))}
          </motion.div>
        </div>
      ) : null}

      {(["up", "down"] as const).map(which => {
        // Up the ladder is toward the rarer, more formal word.
        const step = which === "up" ? 1 : -1;
        const exhausted = rungAfter(step) === null;
        return (
        <button
          key={which}
          type="button"
          aria-label={which === "up" ? "A more formal word" : "A simpler word"}
          // Nothing left in that direction — this word is already the plainest
          // or the rarest thing WordNet offers. Say so by going faint rather
          // than by rolling the word to itself.
          disabled={exhausted}
          aria-disabled={exhausted}
          // Keep the caret where it is: losing focus would take the chevrons
          // away before the click landed.
          onMouseDown={event => event.preventDefault()}
          onClick={() => startRoll(step)}
          className={`absolute flex items-center justify-center transition-colors ${
            exhausted
              ? "cursor-default text-ink/10"
              : "text-ink/35 hover:text-rose-ink"
          }`}
          // The box is a hit target, not the mark — it is much larger than the
          // chevron drawn in it, centred on where that chevron already sat, so
          // growing it moves nothing on screen. It stops 1px clear of the word
          // on purpose: these sit directly against running text, and a target
          // that overlapped the line would swallow clicks meant to put the
          // caret in it.
          style={{
            left: centre - HIT.width / 2,
            top:
              which === "up"
                ? active.top - GAP - HIT.height
                : active.top + active.height + GAP,
            width: HIT.width,
            height: HIT.height,
          }}
        >
          {which === "up" ? (
            <ChevronUp className="size-4" strokeWidth={2.25} />
          ) : (
            <ChevronDown className="size-4" strokeWidth={2.25} />
          )}
        </button>
        );
      })}
    </>
  );
}
