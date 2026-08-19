import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { useFetcher } from "react-router";
import { motion } from "framer-motion";
import { Minimize2 } from "lucide-react";
import WordRoller from "~/workspace/word-roller";
import type { Note } from "~/lib/types";

/**
 * The one note surface in the app.
 *
 * It is mounted by the workspace layout and never unmounts across a route
 * change, so opening a note is not a page swap — the same title and body
 * elements stay put while a box wraps in around them and the type resizes.
 * Everything that differs between the landing page and the editor is a
 * property of this one element, which is what keeps the words from jumping.
 */

export type SurfaceMode = "page" | "boxed";

export const noteLayoutId = (id: number) => `note-${id}`;

/** Shared by the surface and by the cards reflowing around it. */
export const NOTE_LAYOUT_TRANSITION = {
  type: "tween",
  duration: 0.55,
  ease: [0.4, 0, 0.2, 1],
} as const;

const CHROME_TRANSITION =
  "font-size 550ms cubic-bezier(0.4,0,0.2,1), padding 550ms cubic-bezier(0.4,0,0.2,1), background-color 550ms cubic-bezier(0.4,0,0.2,1), box-shadow 550ms cubic-bezier(0.4,0,0.2,1), min-height 550ms cubic-bezier(0.4,0,0.2,1)";

const TYPE = {
  page: { title: "3.25rem", body: "1.25rem" },
  boxed: { title: "1.875rem", body: "1.125rem" },
};

// useLayoutEffect warns during SSR, where there is nothing to measure.
const useMeasureEffect =
  typeof window === "undefined" ? useEffect : useLayoutEffect;

/**
 * Grows a textarea to fit its text — the single sizing model in both modes, so
 * the field never switches contract mid-transition.
 *
 * Never trusts a zero-width measurement: `scrollHeight` on an unlaid-out field
 * reports the text wrapped one character per line, which once left the hero
 * title 603px tall.
 */
function useAutoHeight() {
  const ref = useRef<HTMLTextAreaElement>(null);
  const frame = useRef(0);

  const measure = useCallback(() => {
    const el = ref.current;
    if (!el || el.clientWidth === 0) return;
    /*
      Collapsing to `auto` is the only way to let the field shrink, but once a
      note is taller than the window that collapse also shortens the document,
      and the browser clamps the scroll position to the shorter page before the
      real height goes back on. The height is restored a statement later and the
      scroll position is not — so every keystroke past the first screenful threw
      the reader back to the top of the note.

      Both writes and the correction happen inside one synchronous block, before
      the browser paints, so the collapse is never seen.
    */
    const scrolled = window.scrollY;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
    if (window.scrollY !== scrolled) window.scrollTo(0, scrolled);
  }, []);

  /**
   * Re-measure every frame for `ms`, for the stretch where the type is being
   * tweened underneath us and no resize event describes it. Idempotent: a
   * second call while one is running just extends it.
   */
  const track = useCallback(
    (ms: number) => {
      const until = performance.now() + ms;
      const step = () => {
        measure();
        frame.current =
          performance.now() < until ? requestAnimationFrame(step) : 0;
      };
      if (!frame.current) frame.current = requestAnimationFrame(step);
    },
    [measure],
  );

  useEffect(
    () => () => {
      if (frame.current) cancelAnimationFrame(frame.current);
    },
    [],
  );

  useMeasureEffect(measure);

  useEffect(() => {
    const el = ref.current;
    if (!el?.parentElement) return;
    // The parent, not the field: observing the field would see the height we
    // just wrote and loop.
    const observer = new ResizeObserver(measure);
    observer.observe(el.parentElement);
    document.fonts?.ready.then(measure).catch(() => {});
    // A final correction once the type lands. Not enough on its own — see the
    // mode-change tracker in the component below.
    el.addEventListener("transitionend", measure);
    return () => {
      observer.disconnect();
      el.removeEventListener("transitionend", measure);
    };
  }, [measure]);

  return { ref, measure, track };
}

export default function NoteSurface({
  note,
  mode,
  onOpen,
  onClose,
  onReturn,
}: {
  note: Note;
  mode: SurfaceMode;
  /** Landing only: the user asked to open this note in the library. */
  onOpen: () => void;
  /** Boxed only: collapse the note, leaving the library behind. */
  onClose: () => void;
  /** Boxed only: take the note back out to its own page. */
  onReturn: () => void;
}) {
  const fetcher = useFetcher();
  const [title, setTitle] = useState(note.title);
  const [content, setContent] = useState(note.content ?? "");
  const rootRef = useRef<HTMLDivElement>(null);
  const titleField = useAutoHeight();
  const bodyField = useAutoHeight();

  const boxed = mode === "boxed";
  const type = boxed ? TYPE.boxed : TYPE.page;
  // What the fields actually sit on. The box is transparent on the landing
  // page, so there the surface is the page's own paper, not paper-raised —
  // the word roller masks against this and looked like a patch without it.
  const surface = boxed
    ? "var(--color-paper-raised)"
    : "var(--color-paper)";

  /*
    Where to put the caret after the word roller swaps a word out.

    It has to land just past the replacement, or the caret is no longer inside
    the word and the chevrons vanish mid-climb. Restoring it has to wait for
    React to commit the new text: a controlled textarea whose value changes puts
    the caret at the very end, so anything set before the commit — in the
    handler, or in a requestAnimationFrame, which is what this used to do — is
    immediately undone. A layout effect runs after the DOM is updated and before
    the browser paints, so the caret never visibly jumps.
  */
  const pendingCaret = useRef<{ field: HTMLTextAreaElement | null; at: number } | null>(
    null,
  );
  useMeasureEffect(() => {
    const pending = pendingCaret.current;
    if (!pending?.field) return;
    pendingCaret.current = null;
    pending.field.setSelectionRange(pending.at, pending.at);
  });

  // Re-measure when the mode flips: the type changes size, so the number of
  // lines can change even though the text did not.
  useMeasureEffect(() => {
    titleField.measure();
    bodyField.measure();
  });

  /*
    …and keep re-measuring for the length of the tween, not just at its ends.

    The type animates for 550ms, so the fields' heights have to animate with
    it. Nothing else reports that frame by frame: each field sits in a wrapper
    that fits it exactly (the word roller measures against it), so the parent
    the ResizeObserver watches is only as tall as the height we ourselves just
    wrote, and its width does not change during the tween at all — it fires
    once, not per frame. Measuring only at `transitionend` lets the height
    arrive in one step after the type has already moved, which reads as a blip
    in the heading.
  */
  useEffect(() => {
    // A little past the 550ms tween, so the last frame is the settled value.
    titleField.track(650);
    bodyField.track(650);
    // The hooks return a fresh object each render; the callbacks themselves are
    // stable, so depend on those or this runs on every keystroke.
  }, [boxed, titleField.track, bodyField.track]);

  // Adopt server values when the focused note changes underneath us.
  const shownId = useRef(note.id);
  if (shownId.current !== note.id) {
    shownId.current = note.id;
    setTitle(note.title);
    setContent(note.content ?? "");
  }

  const saved = useRef({ title: note.title, content: note.content ?? "" });
  const save = () => {
    const nextTitle = title.trim();
    const nextContent = content.trim();
    if (
      nextTitle === saved.current.title.trim() &&
      nextContent === saved.current.content.trim()
    ) {
      return;
    }
    saved.current = { title: nextTitle, content: nextContent };
    fetcher.submit(
      {
        intent: "update",
        id: String(note.id),
        title: nextTitle || "Untitled",
        content: nextContent,
      },
      { method: "post", action: "/notes" },
    );
  };

  // Whether the surface already had focus when this click sequence began. A
  // double click only navigates when the user was reading; once they are
  // editing, the second click has to keep selecting words like any other text.
  const wasEditing = useRef(false);
  const handleMouseDownCapture = (event: React.MouseEvent) => {
    // Only the opening click tells us anything — by the second mousedown the
    // first has already focused a field.
    if (event.detail > 1) return;
    wasEditing.current = !!rootRef.current?.contains(document.activeElement);
  };

  // Double click toggles between the note's own page and the library around
  // it, in both directions — not when the user is double clicking to select a
  // word in a field.
  const handleDoubleClick = (event: React.MouseEvent) => {
    if ((event.target as HTMLElement).closest("input, textarea, button")) return;
    if (boxed) {
      save();
      onReturn();
      return;
    }
    if (wasEditing.current) return;
    (document.activeElement as HTMLElement | null)?.blur();
    save();
    onOpen();
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      commitAndLeave(event);
      return;
    }

    if (event.key !== "Enter" || event.shiftKey) return;

    // Enter commits everywhere else in the app, but the body is the one place
    // that rule cannot hold: it is a multi-line writing surface, and a plain
    // Enter there is a paragraph break, not a request to stop writing. Sending
    // it away blurred the field mid-sentence — with onBlur saving and the
    // landing page having nothing to close, the note simply became untypable.
    if (event.target === bodyField.ref.current) return;

    commitAndLeave(event);
  };

  /** Save and step out of the field, which is what Enter means in a title. */
  const commitAndLeave = (event: React.KeyboardEvent) => {
    event.preventDefault();
    (event.target as HTMLElement).blur();
    if (boxed) onClose();
  };

  // Boxed only: clicking the page around the note collapses it.
  useEffect(() => {
    if (!boxed) return;
    const onMouseDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (rootRef.current?.contains(target)) return;
      // Not anything with its own meaning. A card is a request to open *that*
      // note, so closing here would fire a second navigation and race the one
      // the card is about to start.
      if (target.closest("[data-note-card], button, a")) return;
      save();
      onClose();
    };
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  });

  // Just the date. The landing page is not a "resume where you left off"
  // screen — it is the note itself, so the only context it needs is when the
  // note was last touched.
  const lastTouched = note.updated_at
    ? new Intl.DateTimeFormat("en-US", { dateStyle: "long" }).format(
        new Date(note.updated_at),
      )
    : null;

  return (
    <motion.div
      layout
      layoutId={noteLayoutId(note.id)}
      transition={{ layout: NOTE_LAYOUT_TRANSITION }}
      ref={rootRef}
      role={boxed ? "dialog" : undefined}
      aria-label={boxed ? `Edit note: ${note.title || "Untitled"}` : undefined}
      onMouseDownCapture={handleMouseDownCapture}
      onDoubleClick={handleDoubleClick}
      onKeyDown={handleKeyDown}
      onBlur={save}
      // Every difference between the two modes is a value on this one element,
      // so the change is an animation rather than a swap.
      style={{
        borderRadius: 24,
        minHeight: boxed ? "68vh" : "78vh",
        padding: boxed ? "2.25rem 2.5rem" : "0rem",
        backgroundColor: boxed ? "var(--color-paper-raised)" : "transparent",
        boxShadow: boxed
          ? "0px 25px 50px -12px rgb(56 56 90 / 0.15)"
          : "0px 25px 50px -12px rgb(56 56 90 / 0)",
        transition: CHROME_TRANSITION,
      }}
      className="flex w-full flex-col"
    >
      {/*
        The reading column is centred and vertically centred in *both* modes.
        Centring only on the landing page would make the text jump the moment
        the box appears, which is the one thing this whole structure exists to
        avoid — so the box moves around the text, and the text stays put.
      */}
      {/*
        Centred in both modes, deliberately. text-align cannot be tweened, so
        alignment that differs between the two states snaps the words sideways
        the instant the box arrives — the one visible discontinuity in an
        otherwise continuous transition. Everything else here animates, so the
        alignment has to be constant.
      */}
      <div
        className={`mx-auto flex w-full flex-1 flex-col justify-center text-center ${
          boxed ? "max-w-4xl" : "max-w-3xl"
        }`}
      >
        <p
          className="font-sans text-sm italic text-rose-ink transition-opacity duration-500"
          style={{ opacity: boxed ? 0 : 1 }}
        >
          {lastTouched}
        </p>

        {/* Same contract as the body below: a wrapper that fits the field
            exactly, so the roller can measure against its origin. */}
        <div className="relative mt-6 w-full">
          <textarea
            ref={titleField.ref}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            rows={1}
            spellCheck={false}
            placeholder="Untitled"
            aria-label="Note title"
            // text-center on the field itself: form controls do not inherit
            // text-align from an ancestor.
            style={{ fontSize: type.title, transition: CHROME_TRANSITION }}
            className="block w-full resize-none overflow-hidden border-none bg-transparent p-0 text-center font-display font-medium leading-[1.2] tracking-tight text-ink caret-rose-ink outline-none placeholder:text-ink/25"
          />
          <WordRoller
            fieldRef={titleField.ref}
            value={title}
            background={surface}
            onReplace={(start, end, word) => {
              setTitle(prev => prev.slice(0, start) + word + prev.slice(end));
              pendingCaret.current = {
                field: titleField.ref.current,
                at: start + word.length,
              };
            }}
          />
        </div>

        {/*
          The wrapper has to fit the field exactly and be the positioning
          context: the word roller measures against its origin.
        */}
        <div className="relative mx-auto mt-8 w-full max-w-[68ch]">
          <textarea
            ref={bodyField.ref}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            rows={1}
            placeholder="Start writing…"
            aria-label="Note text"
            style={{ fontSize: type.body, transition: CHROME_TRANSITION }}
            className="block w-full resize-none overflow-hidden border-none bg-transparent p-0 text-center font-sans leading-relaxed text-ink/85 caret-rose-ink outline-none placeholder:text-ink/25"
          />
          <WordRoller
            fieldRef={bodyField.ref}
            value={content}
            background={surface}
            onReplace={(start, end, word) => {
              setContent(prev => prev.slice(0, start) + word + prev.slice(end));
              pendingCaret.current = {
                field: bodyField.ref.current,
                at: start + word.length,
              };
            }}
          />
        </div>
      </div>

      {/*
        Chrome belongs to the box, so it fades in as the box wraps — but it
        keeps its height in both modes. Collapsing it on the landing page would
        shift the centred text as the box arrives.
      */}
      <div
        className="mx-auto flex h-20 w-full max-w-4xl shrink-0 items-center justify-between gap-4 transition-opacity duration-500"
        style={{ opacity: boxed ? 1 : 0, pointerEvents: boxed ? "auto" : "none" }}
      >
        <span className="text-sm italic text-ink/40">
          Esc to save · Enter for a new line
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-hidden={!boxed}
          tabIndex={boxed ? 0 : -1}
          className="flex items-center gap-2 rounded-xl bg-accent-rose px-5 py-2 text-base text-on-rose transition-opacity hover:opacity-90 cursor-pointer"
        >
          <Minimize2 className="size-4" />
          Done
        </button>
      </div>
    </motion.div>
  );
}
