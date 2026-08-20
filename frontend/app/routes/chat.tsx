import { useEffect, useState } from "react";
import { useFetcher, useNavigate } from "react-router";
import { motion, useReducedMotion } from "framer-motion";

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
 *
 * Being outside it also costs this page the one thing the workspace gets for
 * free: a conversation arrives and leaves as a whole screen rather than as a
 * re-composition of one, and a hard swap is exactly the tear DESIGN.md §7 rule
 * 1 rules out. It cannot be fixed the way the note surface fixes it — an
 * AnimatePresence at the route level would remount the workspace layout on
 * every navigation and take the persistent note surface down with it — so the
 * page carries its own arrival and departure instead.
 */

/**
 * Long enough to read as a movement, short enough not to sit between clicks.
 * Matches `.page-enter`, which is the same movement in the other direction.
 */
const PAGE_TRANSITION = { duration: 0.28, ease: [0.4, 0, 0.2, 1] } as const;

export function meta({ data }: Route.MetaArgs) {
  return [{ title: `${data?.chat.title ?? "Conversation"} — Restyle` }];
}

export async function loader({ request, params }: Route.LoaderArgs) {
  const token = await requireToken(request);
  // Both together: the picker above the composer is drawn from the same load as
  // the transcript, so a conversation never renders without saying what it is
  // running on.
  const [chat, provider] = await Promise.all([
    api.getChat(token, Number(params.chatId)),
    api.getProviderSettings(token),
  ]);
  return { chat, provider };
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
    A third, and to a resource route rather than to this page's action: which
    model the account uses is not a property of this chat, and posting it here
    would revalidate the transcript to change a dropdown.

    It carries the choice optimistically — `chosen` below — because a select
    that snaps back to its old value while the post is in flight reads as a
    control that ignored you.
  */
  const chooser = useFetcher();

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

  const chosen = chooser.json as { provider: string; model: string } | undefined;
  const provider = chosen
    ? { ...loaderData.provider, active: chosen }
    : loaderData.provider;

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

  // The page is on its way out. The departure has to start before the
  // navigation or there is nothing left to animate — leaving unmounts this —
  // but the navigation must not be *hostage* to the animation finishing: a
  // backgrounded tab does not run animation frames, and hanging "go back" off
  // one meant the button did nothing at all there. A timer of the same length
  // owes nothing to the frame loop, so the fade is decoration over a departure
  // that happens either way.
  const [leaving, setLeaving] = useState(false);
  const leave = () => setLeaving(true);
  useEffect(() => {
    if (!leaving) return;
    const timer = setTimeout(() => navigate("/notes"), PAGE_TRANSITION.duration * 1000);
    return () => clearTimeout(timer);
  }, [leaving, navigate]);
  // §12: reduced motion keeps the cross-fade and drops the travel.
  const rise = useReducedMotion() ? 0 : 12;

  const error =
    (sender.data && !sender.data.ok ? sender.data.error : null) ??
    (finisher.data && !finisher.data.ok ? finisher.data.error : null);

  return (
    /*
      Arrival is `.page-enter` in app.css and owes nothing to this component;
      only the departure needs state, because it has to finish before the
      navigation starts — leaving unmounts this, and there is nothing left to
      animate once it has. So the button sets the flag and the navigation waits
      on the animation rather than the other way round.

      `initial={false}` is what keeps the page visible without a script: the
      motion element renders its resting values into the server's HTML instead
      of an `opacity: 0` that only hydration can undo.
    */
    <motion.main
      initial={false}
      animate={leaving ? { opacity: 0, y: rise } : { opacity: 1, y: 0 }}
      transition={PAGE_TRANSITION}
      className="page-enter min-h-screen bg-paper px-8 py-12 text-ink md:px-16"
    >
      {/* The house form for leaving a view — one serif line at Meta size,
          DESIGN.md §11. The library is where the summary ends up, so that is
          where this goes back to. */}
      <button
        type="button"
        onClick={leave}
        className="mb-8 block text-sm tracking-wide text-ink/50 transition-colors hover:text-ink cursor-pointer"
      >
        ← Your library
      </button>

      <ChatSurface
        chat={shown}
        pending={pending}
        finishing={finishing}
        error={error}
        provider={provider}
        onSend={content =>
          sender.submit({ intent: "send", content }, { method: "post" })
        }
        onFinish={() => finisher.submit({ intent: "finish" }, { method: "post" })}
        onChoose={(provider, model) =>
          chooser.submit(
            { provider, model },
            { method: "post", action: "/api/active-model", encType: "application/json" },
          )
        }
        onLeave={leave}
      />
    </motion.main>
  );
}
