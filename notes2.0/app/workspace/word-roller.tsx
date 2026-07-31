import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ChevronUp, ChevronDown } from "lucide-react";

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
 * Where the replacement comes from. For now a word rolls to itself, so the
 * animation can be judged before the vocabulary behind it exists.
 */
function nextWord(word: string) {
  return word;
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

  const startRoll = (direction: 1 | -1) => {
    if (!span || roll) return;
    setRoll({ span, to: nextWord(span.word), direction });
    rollTimer.current = setTimeout(() => {
      onReplace(span.start, span.end, nextWord(span.word));
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
                {i === REEL - 1 && roll.direction === 1 ? roll.to : active.word}
              </div>
            ))}
          </motion.div>
        </div>
      ) : null}

      {(["up", "down"] as const).map(which => (
        <button
          key={which}
          type="button"
          aria-label={which === "up" ? "Previous word" : "Next word"}
          // Keep the caret where it is: losing focus would take the chevrons
          // away before the click landed.
          onMouseDown={event => event.preventDefault()}
          onClick={() => startRoll(which === "up" ? -1 : 1)}
          className="absolute flex items-center justify-center text-ink/35 transition-colors hover:text-rose-ink"
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
      ))}
    </>
  );
}
