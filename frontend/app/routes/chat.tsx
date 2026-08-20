import { useFetcher, useNavigate } from "react-router";

import type { Route } from "./+types/chat";
import ChatSurface from "~/chat/chat-surface";
import { api, ApiError } from "~/lib/api.server";
import { requireToken } from "~/lib/session.server";
import type { Chat } from "~/lib/types";

/**
 * One conversation, on its own page.
 *
 * Outside the workspace layout deliberately. That layout exists to keep one
 * note surface mounted across the trip between `/` and `/notes`, and it renders
 * that surface for whichever *note* is focused. A chat is not a note, so
 * nesting this inside it would mean a note surface on screen underneath a
 * conversation.
 */

export function meta({ data }: Route.MetaArgs) {
  return [{ title: `${data?.chat.title ?? "Conversation"} — Restyle` }];
}

export async function loader({ request, params }: Route.LoaderArgs) {
  const token = await requireToken(request);
  return { chat: await api.getChat(token, Number(params.chatId)) };
}

export async function action({ request, params }: Route.ActionArgs) {
  const token = await requireToken(request);
  const id = Number(params.chatId);
  const formData = await request.formData();
  const intent = formData.get("intent");

  try {
    switch (intent) {
      case "send": {
        // Slow on purpose — a model is thinking. The fetcher below shows the
        // pending turn rather than the page blocking on it.
        const chat = await api.sendChatMessage(
          token,
          id,
          String(formData.get("content") ?? ""),
        );
        return { ok: true as const, chat };
      }
      case "finish": {
        return { ok: true as const, chat: await api.summarizeChat(token, id) };
      }
      default:
        return { ok: false as const, error: `Unknown intent: ${String(intent)}` };
    }
  } catch (error) {
    /*
      The refusals are the interesting path here, and each one has a different
      remedy, so the backend's own words are passed through rather than
      flattened into "something went wrong":

        409  no key on file, or the chat is already finished
        502  the provider was reached and would not answer
    */
    if (error instanceof ApiError) return { ok: false as const, error: error.detail };
    throw error;
  }
}

export default function ChatRoute({ loaderData }: Route.ComponentProps) {
  const navigate = useNavigate();
  // Two fetchers, because the two actions have to be distinguishable while in
  // flight: one shows "Thinking…" in the transcript, the other "Summarising…"
  // on the button. A single fetcher could only say that something was busy.
  const sender = useFetcher<typeof action>();
  const finisher = useFetcher<typeof action>();

  /*
    The freshest version of this chat.

    An action's own response is newer than the loader data behind it, and it
    arrives first — the loader revalidates afterwards. Preferring it means the
    reply appears the moment it lands rather than one round trip later.
  */
  const fromAction = [finisher.data, sender.data].find(
    (data): data is { ok: true; chat: Chat } => Boolean(data?.ok && "chat" in data),
  );
  const chat = fromAction?.chat ?? loaderData.chat;

  const pending = sender.state !== "idle";
  const finishing = finisher.state !== "idle";

  // Optimistic: show the turn being sent, so the transcript reacts to the key
  // press rather than to the network. It carries a negative id, which no real
  // row has, so it cannot collide with the message it becomes.
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

  const error =
    (sender.data && !sender.data.ok ? sender.data.error : null) ??
    (finisher.data && !finisher.data.ok ? finisher.data.error : null);

  return (
    <main className="min-h-screen bg-paper px-8 py-12 text-ink md:px-16">
      {/* The house form for leaving a view — one serif line at Meta size,
          DESIGN.md §11. The library is where the summary ends up, so that is
          where this goes back to. */}
      <button
        type="button"
        onClick={() => navigate("/notes")}
        className="mb-8 block text-sm tracking-wide text-ink/50 transition-colors hover:text-ink cursor-pointer"
      >
        ← Your library
      </button>

      <ChatSurface
        chat={shown}
        pending={pending}
        finishing={finishing}
        error={error}
        onSend={content =>
          sender.submit({ intent: "send", content }, { method: "post" })
        }
        onFinish={() => finisher.submit({ intent: "finish" }, { method: "post" })}
        onLeave={() => navigate("/notes")}
      />
    </main>
  );
}
