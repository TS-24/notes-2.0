import { useFetcher } from "react-router";
import { motion } from "framer-motion";
import { Trash2 } from "lucide-react";

import { chatLayoutId } from "~/chat/chat-surface";
import { NOTE_LAYOUT_TRANSITION } from "~/workspace/note-surface";
import LocalTime from "~/lib/local-time";
import type { Chat } from "~/lib/types";

/**
 * A conversation, sitting in the library beside the notes.
 *
 * Same geometry as a note card on purpose — the grid is one surface, and a
 * conversation is another thing you wrote. What distinguishes it is the ink
 * marking that the ghost button also carries, and what it shows: a note shows
 * its text, and a chat shows what it was *about*, because nobody rereads a
 * transcript.
 *
 * Carries a `layoutId` shared with the chat surface, so opening one morphs the
 * card into the boxed conversation on the library — the same way a note card
 * becomes the open note.
 */
export default function ChatCard({
  data,
  onOpen,
}: {
  data: Chat;
  onOpen: (chat: Chat) => void;
}) {
  // Its own fetcher, like the note card's: simultaneous deletes must not
  // clobber each other's pending state.
  const fetcher = useFetcher();
  const isDeleting = fetcher.formData?.get("intent") === "delete";

  // Remove the card immediately rather than waiting for the round trip.
  if (isDeleting) return null;

  const summary = data.summary;
  const turns = data.messages.length;

  return (
    <motion.div
      layout
      layoutId={chatLayoutId(data.id)}
      data-note-card
      onDoubleClick={event => {
        if ((event.target as HTMLElement).closest("button")) return;
        onOpen(data);
      }}
      whileHover={{
        y: -4,
        boxShadow:
          "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)",
      }}
      transition={{ layout: NOTE_LAYOUT_TRANSITION, duration: 0.2 }}
      style={{ borderRadius: 16 }}
      title="Double click to open"
      className="group relative flex flex-col justify-between p-7 bg-paper-raised cursor-pointer select-none"
    >
      <div>
        {/* The one mark that says this is a conversation rather than a note.
            Ink, matching the ghost button that started it. */}
        <p className="text-xs uppercase tracking-[0.14em] text-ink/45">
          Conversation
        </p>

        <h3 className="mt-2 font-display text-lg font-medium leading-snug tracking-tight text-ink">
          {data.title}
        </h3>

        {summary ? (
          <>
            {/* Capped like a note card's text, and for the same reason: the
                card is what the conversation was about, not the whole of it. */}
            <p className="note-preview mt-3 text-base leading-relaxed text-ink/85">
              {summary.general}
            </p>
            {summary.topics.length > 0 && (
              <ul className="mt-4 flex flex-wrap gap-x-3 gap-y-1">
                {summary.topics.map(topic => (
                  <li key={topic} className="text-sm italic text-ink/55">
                    {topic}
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : (
          // Unfinished. Saying so is the point: the summary is what a chat
          // leaves behind, and this one has not left it yet.
          <p className="mt-3 text-base italic leading-relaxed text-ink/50">
            {turns === 0
              ? "Nothing said yet."
              : `${turns} ${turns === 1 ? "turn" : "turns"}, not yet summarised.`}
          </p>
        )}

        <div className="mt-6 text-sm italic text-ink/45">
          <LocalTime value={data.updated_at} />
        </div>
      </div>

      <div className="mt-8 flex items-center opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
        <fetcher.Form method="post" action="/chats">
          <input type="hidden" name="intent" value="delete" />
          <input type="hidden" name="id" value={data.id} />
          <motion.button
            type="submit"
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={event => event.stopPropagation()}
            className="p-1.5 rounded-lg text-ink/35 hover:text-danger transition-colors cursor-pointer"
            title="Delete conversation"
          >
            <Trash2 className="size-3.5" />
          </motion.button>
        </fetcher.Form>
      </div>
    </motion.div>
  );
}
