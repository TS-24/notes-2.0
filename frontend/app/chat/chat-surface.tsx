import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { Link, useFetcher, useNavigate } from "react-router";
import { motion, useReducedMotion } from "framer-motion";
import { CornerDownLeft, Sparkles } from "lucide-react";

import ModelPicker from "~/chat/model-picker";
import Markdown from "~/notes/markdown";
import {
  CHROME_TRANSITION,
  fitToText,
  NOTE_LAYOUT_TRANSITION,
  PAGE_SCROLLER,
  useAutoHeight,
  useMeasureEffect,
} from "~/workspace/note-surface";
import type { Chat, ProviderSettings } from "~/lib/types";
import {
  MessageScrollerProvider,
  MessageScroller,
  MessageScrollerViewport,
  MessageScrollerContent,
  MessageScrollerItem,
} from "~/components/ui/message-scroller";
import { Message, MessageContent } from "~/components/ui/message";
import { Bubble, BubbleContent } from "~/components/ui/bubble";
import { Marker } from "~/components/ui/marker";

export const chatLayoutId = (id: number) => `chat-${id}`;

/*
  Both modes spell out every property that differs between them, including the
  ones a page-mode conversation does not appear to have.

  That is the note surface's arrangement and it is what makes the change an
  animation rather than a swap: a property present in one style object and
  absent from the other has nothing to tween from, so it lands in one frame
  while everything around it glides. The transparent background and the
  zero-strength shadow below are that shadow at rest, not an omission.
*/
const BOXED_STYLE = {
  borderRadius: 24,
  minHeight: "68vh",
  padding: "2.25rem 2.5rem",
  backgroundColor: "var(--color-paper-raised)",
  boxShadow: "0px 25px 50px -12px rgb(56 56 90 / 0.15)",
} as const;

const PAGE_STYLE = {
  borderRadius: 24,
  minHeight: "68vh",
  padding: "2.25rem 2.5rem",
  backgroundColor: "transparent",
  boxShadow: "0px 25px 50px -12px rgb(56 56 90 / 0)",
} as const;

export default function ChatSurface({
  chat: initialChat,
  provider: initialProvider,
  mode = "page",
  onClose,
  onReturn,
}: {
  chat: Chat;
  provider: ProviderSettings;
  mode?: "page" | "boxed";
  onClose: () => void;
  /** Boxed only: take the conversation out to its own page. */
  onReturn?: () => void;
}) {
  const navigate = useNavigate();
  const sender = useFetcher();
  const finisher = useFetcher();
  const chooser = useFetcher();
  const renamer = useFetcher();

  const [draft, setDraft] = useState("");
  /*
    One message may wait behind the turn in front of it — one, not a list. A
    backlog you can neither see nor edit is worse than a field you have to send
    from twice.
  */
  const [queued, setQueued] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const titleField = useAutoHeight();

  const fromAction = [finisher.data, sender.data].find(
    (data): data is { ok: true; chat: Chat } =>
      Boolean(data && typeof data === "object" && "ok" in data && data.ok && "chat" in data),
  );
  const chat: Chat = fromAction?.chat ?? initialChat;
  const finished = chat.summary !== null;

  const pending = sender.state !== "idle";
  const finishing = finisher.state !== "idle";

  const chosen = chooser.json as { provider: string; model: string } | undefined;
  const provider = chosen
    ? { ...initialProvider, active: chosen }
    : initialProvider;

  const inFlight = sender.formData?.get("content");
  const shown: Chat =
    pending && typeof inFlight === "string"
      ? {
          ...chat,
          messages: [
            ...chat.messages,
            {
              id: -1,
              role: "user" as const,
              content: inFlight,
              created_at: new Date().toISOString(),
            },
          ],
        }
      : chat;

  /*
    The note this conversation was started from, and the turns actually taken.

    The seed is stored as a `system` message so the provider and the summariser
    both see it — see backend/app/services/llm.py, which folds it into the
    leading system prompt. It is not a turn, though: rendering it would show the
    reader their own note pasted back as the thing they opened with, and a long
    note would fill the conversation before it began.
  */
  const seed = shown.messages.find(message => message.role === "system") ?? null;
  const turns = shown.messages.filter(message => message.role !== "system");

  const sendError =
    sender.data && !(sender.data as { ok: boolean }).ok
      ? (sender.data as { error: string }).error
      : null;
  const error =
    sendError ??
    (finisher.data && !(finisher.data as { ok: boolean }).ok ? (finisher.data as { error: string }).error : null);

  /*
    The composer grows with what is in it and then scrolls inside itself.

    `fitToText` rather than a bare `scrollHeight` assignment: letting a field
    shrink means collapsing it to `auto` first, and the collapse shortens the
    page under it, so the browser clamps the scroll position before the real
    height goes back on. That is the same trap the note's fields are written
    around, and this is the same solution rather than a second one.
  */
  useMeasureEffect(() => {
    const el = composer.current;
    if (el && el.clientWidth > 0) fitToText(el, [PAGE_SCROLLER]);
  }, [draft, finished]);

  /*
    Finishing writes a note, so finishing goes to it.

    What a conversation leaves behind is the note, not the transcript — it is
    the thing you can correct, add to and pin. Staying here to read the summary
    in place would show it in the one form you cannot edit, and then leave the
    reader to go and find the note themselves.

    Guarded by a ref because the fetcher's data outlives the navigation: without
    it the effect re-fires on every later render and pins the route here.
  */
  const wroteNote = useRef(false);
  useEffect(() => {
    const data = finisher.data as { ok?: boolean; chat?: Chat } | undefined;
    const noteId = data?.ok ? data.chat?.summary?.note_id : null;
    if (finisher.state !== "idle" || !noteId || wroteNote.current) return;
    wroteNote.current = true;
    navigate(`/notes?open=${noteId}`, { replace: true });
  }, [finisher.state, finisher.data, navigate]);

  /** The turn in flight, kept so a failure can hand its words back. */
  const lastSent = useRef<string | null>(null);

  const submit = useCallback(
    (content: string) => {
      lastSent.current = content;
      sender.submit(
        { intent: "send", content },
        { method: "post", action: `/chats/${chat.id}` },
      );
    },
    [sender, chat.id],
  );

  /*
    Sending clears the field rather than waiting for the turn to land, because
    the field is no longer locked while it does: the next thing you want to say
    has to have somewhere to go. A turn that fails hands its words back — see
    below.
  */
  const send = () => {
    const content = draft.trim();
    if (!content || finished) return;
    if (pending) {
      if (queued !== null) return;
      setQueued(content);
      setDraft("");
      return;
    }
    setDraft("");
    submit(content);
  };

  // The queued message goes the moment the turn in front of it lands. Not after
  // a failure: there the words come back to the composer instead, and sending
  // another into a chat that just refused one would only fail again.
  useEffect(() => {
    if (pending || queued === null || sendError) return;
    const content = queued;
    setQueued(null);
    submit(content);
  }, [pending, queued, sendError, submit]);

  /*
    A failed turn puts everything unsent back in the composer.

    When a provider has a bad minute the words belong in the one place you can
    edit and resend them — the alternative is a paragraph you typed once and an
    error message where it went. Anything already queued comes back with it,
    below whatever you have since typed.
  */
  const handedBack = useRef(false);
  useEffect(() => {
    if (sender.state !== "idle") {
      handedBack.current = false;
      return;
    }
    if (!sendError || handedBack.current) return;
    handedBack.current = true;
    const unsent = [lastSent.current, queued].filter(
      (text): text is string => Boolean(text),
    );
    lastSent.current = null;
    setQueued(null);
    setDraft(prev => [...unsent, prev.trim()].filter(Boolean).join("\n\n"));
  }, [sender.state, sendError, queued]);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    // Escape is on `document` below. This prop only fires while focus is inside
    // the surface, and opening a chat from its card leaves focus on `<body>`.
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    send();
  };

  /*
    Double click takes the conversation out to its own page, which is what the
    same gesture does to a note: one click opens it where it sits, a second
    asks for the room. It used to close the chat, so the two surfaces answered
    the same gesture with opposite things.
  */
  const handleDoubleClick = (event: React.MouseEvent) => {
    if ((event.target as HTMLElement).closest("input, textarea, button")) return;
    if (onReturn) onReturn();
  };

  /*
    The conversation's name, editable in place.

    It is derived from the first thing said in it, which is a guess, and it is
    the whole of what stands for the conversation in the library — so it is a
    field, like the note's title, not a heading. Local state rather than the
    chat's own value because a controlled field cannot be typed into otherwise;
    it re-seeds when the conversation changes underneath it.
  */
  const [title, setTitle] = useState(chat.title);
  const savedTitle = useRef(chat.title);
  useEffect(() => {
    if (chat.title === savedTitle.current) return;
    savedTitle.current = chat.title;
    setTitle(chat.title);
  }, [chat.title]);

  const saveTitle = () => {
    // "Untitled" is the placeholder a new chat and a new note both carry, and
    // the API refuses an empty title — but the field lets you clear it.
    const next = title.trim() || "Untitled";
    if (next === savedTitle.current.trim()) return;
    savedTitle.current = next;
    renamer.submit(
      { intent: "rename", id: String(chat.id), title: next },
      { method: "post", action: "/chats" },
    );
  };

  const collapse = useRef(() => {});
  useEffect(() => {
    collapse.current = () => onClose();
  });

  /*
    Escape, from anywhere on the page — the same treatment the note surface has.

    It hung off `onKeyDown` on the root, which only fires when focus is already
    inside. The composer autofocuses, so it worked until you clicked anything
    else; after that the key went nowhere. Opening a chat from its card leaves
    focus on `<body>`, which is every time.
  */
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.defaultPrevented) return;
      if (document.querySelector('[data-slot="dialog-content"]:not([data-closed])')) {
        return;
      }
      event.preventDefault();
      collapse.current();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);
  useEffect(() => {
    if (mode !== "boxed") return;
    const onMouseDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (rootRef.current?.contains(target)) return;
      if (target.closest("[data-note-card], button, a")) return;
      collapse.current();
    };
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [mode]);

  const boxed = mode === "boxed";
  /*
    §12 — reduced motion collapses the morph to nothing rather than dropping it,
    so the conversation still lands in its resting state, just in one frame. The
    note surface does exactly this; the two must agree or closing a chat and
    closing a note answer the preference differently.
  */
  const reduced = useReducedMotion();
  const layoutTransition = reduced
    ? { ...NOTE_LAYOUT_TRANSITION, duration: 0 }
    : NOTE_LAYOUT_TRANSITION;
  const chromeTransition = reduced ? "none" : CHROME_TRANSITION;

  return (
    <motion.div
      layout
      /*
        Measure only when the conversation is actually moving between its two
        states — the same guard the note surface carries, and for the same
        reason. Left to itself framer re-measures on every render, and this
        surface re-renders on every character typed into the composer and on
        every fetcher transition, so it was starting a fresh tween of a box that
        had not moved. Leaving one of those running is what made closing a chat
        lurch: the exit projects from wherever that spurious tween had got to
        rather than from the box on screen.
      */
      layoutDependency={`${mode}:${chat.id}`}
      layoutId={boxed ? chatLayoutId(chat.id) : undefined}
      transition={{ layout: layoutTransition }}
      ref={rootRef}
      role="dialog"
      aria-label={`Conversation: ${chat.title}`}
      onDoubleClick={handleDoubleClick}
      style={{
        ...(boxed ? BOXED_STYLE : PAGE_STYLE),
        // The other half of the morph. Without it the projection moved the box
        // while the paper it is made of changed in a single frame — geometry
        // gliding, chrome snapping, which is the jump on close.
        transition: chromeTransition,
      }}
      className="flex w-full flex-col"
    >
      {/*
        layout="position" counter-scales the contents, the way the cards and the
        note surface do. Without it the projection that resizes the box stretches
        the type inside it on the way out, so the words warp as the conversation
        leaves.
      */}
      <motion.div
        layout="position"
        layoutDependency={`${mode}:${chat.id}`}
        transition={{ layout: layoutTransition }}
        className="mx-auto flex w-full max-w-4xl flex-1 flex-col"
      >
        {/*
          Same contract as the note's title: a wrapper that fits the field
          exactly, one line to start, grown to its text by `useAutoHeight`.
          Enter commits and steps out rather than adding a line — a title is
          not a place to write a paragraph.
        */}
        <div className="relative w-full">
          <textarea
            ref={titleField.ref}
            value={title}
            onChange={event => setTitle(event.target.value)}
            onBlur={saveTitle}
            onKeyDown={event => {
              if (event.key !== "Enter" || event.shiftKey) return;
              event.preventDefault();
              (event.target as HTMLTextAreaElement).blur();
            }}
            rows={1}
            spellCheck={false}
            placeholder="Untitled"
            aria-label="Conversation title"
            className="block w-full resize-none overflow-hidden border-none bg-transparent p-0 text-center font-display text-3xl font-medium leading-[1.2] tracking-tight text-ink caret-accent-ink outline-none placeholder:text-ink/25"
          />
        </div>

        {/*
          Where this started — one serif line at Meta size, the house form for
          an aside (DESIGN.md §8). It answers the question a reader has the
          moment they open a conversation from a note and find it empty: was
          the note actually taken along?
        */}
        {seed && chat.note_id !== null && (
          <p className="mt-4 text-center text-sm italic text-ink/45">
            Started from{" "}
            <Link
              to={`/notes?open=${chat.note_id}`}
              className="tracking-wide not-italic text-ink/55 transition-colors hover:text-ink"
            >
              your note →
            </Link>
          </p>
        )}

        {turns.length === 0 && !pending ? (
          <p className="mt-8 flex flex-1 items-center justify-center text-lg italic text-ink/40">
            Ask something.
          </p>
        ) : (
          <MessageScrollerProvider autoScroll>
            <MessageScroller className="mt-8 flex flex-1 flex-col overflow-hidden">
              {/*
                A ceiling, not a claim. It used to be a flat 46vh, which the
                composer's own growth then added to — the two together could
                outrun the box. Now the transcript gives way as the composer
                grows and never falls below a few turns' worth.
              */}
              <MessageScrollerViewport
                className="flex-1"
                style={{ minHeight: "12rem", maxHeight: "46vh" }}
              >
                <MessageScrollerContent className="gap-6">
                  {turns.map(message => (
                    <MessageScrollerItem
                      key={message.id}
                      messageId={`msg-${message.id}`}
                      scrollAnchor={message.role === "user"}
                    >
                      <Message align={message.role === "user" ? "end" : "start"}>
                        {/*
                          One box on screen, and it is the model's.

                          This was the other way round: the reader's own turns
                          were the filled thing and the answers were `ghost` —
                          transparent and unpadded, which is to say unstyled
                          prose lying on the page. So the only half marked out
                          was the half you already wrote, and the replies ran
                          into the background and into each other.

                          Only the answer is lifted, because §5 allows one step
                          off the page ground and never two. What separates the
                          reader's turn is the other two tools that rule reaches
                          for first: alignment, and the tone of its ink. A
                          second box would be a border doing type's job.
                        */}
                        <MessageContent>
                          {message.role === "user" ? (
                            <Bubble variant="ghost">
                              <BubbleContent className="max-w-[68ch] text-lg leading-relaxed text-ink/70 whitespace-pre-line">
                                {message.content}
                              </BubbleContent>
                            </Bubble>
                          ) : (
                            <Bubble variant="muted" className="max-w-none">
                              {/* Rendered: models write markdown whether or not
                                  anything is listening, so the alternative is
                                  not plain prose — it is asterisks and hashes
                                  in the middle of the answer. `remark-breaks`
                                  keeps the line breaks `whitespace-pre-line`
                                  used to carry. */}
                              <BubbleContent className="max-w-[76ch] rounded-3xl px-7 py-5 text-lg leading-relaxed text-ink/85">
                                <Markdown>{message.content}</Markdown>
                              </BubbleContent>
                            </Bubble>
                          )}
                        </MessageContent>
                      </Message>
                    </MessageScrollerItem>
                  ))}

                  {pending && (
                    <MessageScrollerItem messageId="pending">
                      <Marker>
                        Thinking…
                      </Marker>
                    </MessageScrollerItem>
                  )}

                </MessageScrollerContent>
              </MessageScrollerViewport>
            </MessageScroller>
          </MessageScrollerProvider>
        )}

        {error && (
          <p role="alert" className="mt-6 text-base text-accent-ink">
            {error}
          </p>
        )}

        {finished ? (
          <p className="mt-8 text-center text-base italic text-ink/50">
            This conversation is finished. What it came to is{" "}
            {chat.note_id !== null ? (
              <Link
                to={`/notes?open=${chat.note_id}`}
                className="not-italic tracking-wide text-ink/70 transition-colors hover:text-ink"
              >
                a note in your library →
              </Link>
            ) : (
              "a note in your library."
            )}
          </p>
        ) : (
          <div className="mt-8 w-full">
            <ModelPicker provider={provider} onChoose={(p, m) =>
              chooser.submit(
                { provider: p, model: m },
                { method: "post", action: "/api/active-model", encType: "application/json" },
              )
            } />
            <div className="relative w-full">
              <textarea
                ref={composer}
                value={draft}
                onChange={event => setDraft(event.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                autoFocus
                placeholder="Ask something..."
                aria-label="Your message"
                /*
                  Not disabled while a reply is in flight. That is precisely the
                  stretch where you have the next thing to say, and graying the
                  field out made you wait for the model before you could write
                  it down.
                */
                style={{ maxHeight: "38vh", overflowY: "auto" }}
                className="block w-full resize-none rounded-2xl border border-ink/10 bg-paper px-5 py-3 pr-14 font-sans text-lg leading-relaxed text-ink caret-accent-ink outline-none transition-colors placeholder:text-ink/30 focus:border-ink/25"
              />
              <button
                type="button"
                onClick={send}
                disabled={draft.trim().length === 0 || (pending && queued !== null)}
                aria-label="Send"
                title="Send"
                className="absolute bottom-3 right-3 rounded-xl p-2 text-ink/45 transition-colors hover:text-ink disabled:opacity-30 disabled:hover:text-ink/45 cursor-pointer disabled:cursor-default"
              >
                <CornerDownLeft className="size-5" />
              </button>
            </div>
            {queued !== null && (
              <p className="mt-2 text-sm italic text-ink/45">
                One message queued — it sends when this reply lands.
              </p>
            )}
          </div>
        )}
      </motion.div>

      <motion.div
        layout="position"
        layoutDependency={`${mode}:${chat.id}`}
        transition={{ layout: layoutTransition }}
        className="mx-auto mt-6 flex w-full max-w-4xl shrink-0 items-center justify-between gap-4"
      >
        <span className="text-sm italic text-ink/40">
          {finished
            ? "Esc to go back"
            : "Enter to send · Shift+Enter for a new line · Esc to leave"}
        </span>
        {!finished && (
          <button
            type="button"
            onClick={() =>
              finisher.submit(
                { intent: "finish" },
                { method: "post", action: `/chats/${chat.id}` },
              )
            }
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
      </motion.div>
    </motion.div>
  );
}
