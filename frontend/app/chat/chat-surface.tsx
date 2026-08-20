import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { CornerDownLeft, Sparkles } from "lucide-react";

import ModelPicker from "~/chat/model-picker";
import { NOTE_LAYOUT_TRANSITION } from "~/workspace/note-surface";
import type { Chat, ProviderSettings } from "~/lib/types";

/**
 * A conversation, in the box an open note sits in.
 *
 * Deliberately the same chrome as `note-surface.tsx` in its boxed mode — the
 * radius, the raised paper, the shadow, the reading column, the footer with its
 * rose button. Opening a chat should feel like opening a note, because it is
 * the same act in the same library.
 *
 * Where it differs, it differs because a dialogue is not prose. A note is
 * centred, and centring turns exchange into poetry; these turns are ranged left
 * with the reader's own indented, so the eye can find who is speaking without a
 * rule or an avatar to tell it. That is the same instinct as DESIGN.md §5 —
 * whitespace carries the hierarchy.
 *
 * No `layoutId` and no shared transition into the grid: a chat opens on its own
 * page rather than morphing out of its card, so there is nothing on the other
 * side to hand measurements to.
 */

// useLayoutEffect warns during SSR, where there is nothing to measure.
const useMeasureEffect =
  typeof window === "undefined" ? useEffect : useLayoutEffect;

export default function ChatSurface({
  chat,
  pending,
  finishing,
  /** Set when the last attempt was refused — a missing key, a provider saying no. */
  error,
  provider,
  onSend,
  onFinish,
  onChoose,
  onLeave,
}: {
  chat: Chat;
  /** True while a turn is in flight; the composer waits and says so. */
  pending: boolean;
  /** True while the summary is being written. */
  finishing: boolean;
  error?: string | null;
  /** The keys on file and what is in use, for the picker above the composer. */
  provider: ProviderSettings;
  onSend: (content: string) => void;
  onFinish: () => void;
  onChoose: (provider: string, model: string) => void;
  onLeave: () => void;
}) {
  const [draft, setDraft] = useState("");
  const transcript = useRef<HTMLDivElement>(null);

  const finished = chat.summary !== null;

  /*
    While the conversation is live the newest turn is the one worth reading, so
    the transcript stays at its foot.

    Not once it is finished. The summary is appended below the last turn, so
    following the foot would open a finished chat on its own conclusion with no
    sign that there is a conversation above it — which is what it did, and it
    read as a chat with its transcript missing.

    `scrollTop` rather than scrollIntoView: PROGRESS.md trap 7 — a framer
    transform fools scrollIntoView into thinking the element is already in view.
  */
  useMeasureEffect(() => {
    const box = transcript.current;
    if (box && !finished) box.scrollTop = box.scrollHeight;
  }, [chat.messages.length, pending, finished]);

  /*
    Clear the composer only once the turn has actually landed.

    Counting *stored* turns, not shown ones. The turn being sent is displayed
    optimistically with a negative id, and counting that as an arrival cleared
    the box the instant you pressed Enter — so a refusal (no key on file, a
    provider saying no) took your question with it, at exactly the moment you
    most want it back to try again.
  */
  const landed = chat.messages.filter(message => message.id > 0).length;
  const sentCount = useRef(landed);
  useEffect(() => {
    if (landed !== sentCount.current) {
      sentCount.current = landed;
      setDraft("");
    }
  }, [landed]);

  const send = () => {
    const content = draft.trim();
    if (!content || pending || finished) return;
    onSend(content);
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      onLeave();
      return;
    }
    // The app's rule everywhere but a note's body: Enter commits, Shift+Enter
    // is a newline. A composer is a field you finish, not a page you write on.
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    send();
  };

  return (
    <motion.div
      layout
      transition={{ layout: NOTE_LAYOUT_TRANSITION }}
      role="dialog"
      aria-label={`Conversation: ${chat.title}`}
      style={{
        borderRadius: 24,
        minHeight: "68vh",
        padding: "2.25rem 2.5rem",
        backgroundColor: "var(--color-paper-raised)",
        boxShadow: "0px 25px 50px -12px rgb(56 56 90 / 0.15)",
      }}
      className="flex w-full flex-col"
    >
      <div className="mx-auto flex w-full max-w-4xl flex-1 flex-col">
        <h1 className="text-center font-display text-3xl font-medium leading-[1.2] tracking-tight text-ink">
          {chat.title}
        </h1>

        {/*
          The window onto the conversation: it scrolls rather than growing the
          page, so the composer stays where you left it however long the
          exchange runs.

          Plain utilities rather than a shared scroll class. There is one on
          another branch for the note surface, and reaching for it here would
          tie this to a change that has not landed — a missing class fails
          silently, by simply not scrolling.
        */}
        <div
          ref={transcript}
          className="mt-8 flex flex-1 flex-col gap-6 overflow-y-auto"
          style={{ maxHeight: "46vh" }}
        >
          {chat.messages.length === 0 && !pending && (
            <p className="my-auto text-center text-lg italic text-ink/40">
              Ask something.
            </p>
          )}

          {chat.messages.map(message =>
            message.role === "user" ? (
              // Indented and on the page's own paper: a step down from the box
              // it sits in, which is enough to mark a change of speaker without
              // a bubble, a border, or a second accent colour.
              <div key={message.id} className="self-end max-w-[85%]">
                <div className="rounded-2xl bg-paper px-5 py-3 text-lg leading-relaxed text-ink whitespace-pre-line">
                  {message.content}
                </div>
              </div>
            ) : (
              <div
                key={message.id}
                className="max-w-[68ch] text-lg leading-relaxed text-ink/85 whitespace-pre-line"
              >
                {message.content}
              </div>
            ),
          )}

          {pending && (
            <p className="text-lg italic text-ink/40" aria-live="polite">
              Thinking…
            </p>
          )}

          {finished && chat.summary && <Summary summary={chat.summary} />}
        </div>

        {error && (
          <p role="alert" className="mt-6 text-base text-accent-ink">
            {error}
          </p>
        )}

        {finished ? (
          <p className="mt-8 text-center text-base italic text-ink/50">
            This conversation is finished. Its summary is on its card in the
            library.
          </p>
        ) : (
          /*
            The picker sits with the composer rather than in the header: it is
            part of asking, and the moment anyone wants to change model is the
            moment they are about to type something the current one is wrong
            for. A finished conversation does not get one — there is nothing
            left to send.
          */
          <div className="mt-8 w-full">
            <ModelPicker provider={provider} onChoose={onChoose} />
            <div className="relative w-full">
            <textarea
              value={draft}
              onChange={event => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              autoFocus
              disabled={pending}
              placeholder="Ask something…"
              aria-label="Your message"
              className="block w-full resize-none rounded-2xl border border-ink/10 bg-paper px-5 py-3 pr-14 font-sans text-lg leading-relaxed text-ink caret-accent-ink outline-none transition-colors placeholder:text-ink/30 focus:border-ink/25 disabled:opacity-60"
            />
            <button
              type="button"
              onClick={send}
              disabled={pending || draft.trim().length === 0}
              aria-label="Send"
              title="Send"
              className="absolute bottom-3 right-3 rounded-xl p-2 text-ink/45 transition-colors hover:text-ink disabled:opacity-30 disabled:hover:text-ink/45 cursor-pointer disabled:cursor-default"
            >
              <CornerDownLeft className="size-5" />
            </button>
            </div>
          </div>
        )}
      </div>

      {/* The same footer the open note has: a hint at Meta size on the left, the
          one rose action on the right. */}
      <div className="mx-auto mt-6 flex w-full max-w-4xl shrink-0 items-center justify-between gap-4">
        <span className="text-sm italic text-ink/40">
          {finished
            ? "Esc to go back"
            : "Enter to send · Shift+Enter for a new line · Esc to leave"}
        </span>
        {!finished && (
          <button
            type="button"
            onClick={onFinish}
            disabled={pending || chat.messages.length === 0}
            title={
              chat.messages.length === 0
                ? "Say something first"
                : "Finish and summarise this conversation"
            }
            className="flex items-center gap-2 rounded-xl bg-accent px-5 py-2 text-base text-on-accent transition-opacity hover:opacity-90 disabled:opacity-40 cursor-pointer disabled:cursor-default"
          >
            <Sparkles className="size-4" />
            {finishing ? "Summarising…" : "Finish & summarise"}
          </button>
        )}
      </div>
    </motion.div>
  );
}

/**
 * The three parts, once the conversation is done.
 *
 * Shown here as well as on the card because finishing a chat should visibly
 * produce something — pressing the button and being sent away with nothing to
 * read would make the summary feel like a background job rather than the point.
 */
function Summary({ summary }: { summary: NonNullable<Chat["summary"]> }) {
  const parts = [
    { heading: "What this was about", body: summary.general },
    { heading: "What you were asking", body: summary.questions },
    { heading: "What the answers covered", body: summary.answers },
  ];

  return (
    <section className="mt-10 border-t border-hairline pt-8">
      {summary.topics.length > 0 && (
        <ul className="mb-6 flex flex-wrap gap-x-4 gap-y-1">
          {summary.topics.map(topic => (
            <li key={topic} className="text-sm italic text-accent-ink">
              {topic}
            </li>
          ))}
        </ul>
      )}
      <div className="space-y-6">
        {parts.map(part => (
          <div key={part.heading}>
            <h2 className="font-display text-lg font-medium tracking-tight text-ink">
              {part.heading}
            </h2>
            <p className="mt-1 text-base leading-relaxed text-ink/85">
              {part.body}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
