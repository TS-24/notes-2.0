import { useNavigate } from "react-router";

import type { Route } from "./+types/chat";
import ChatSurface from "~/chat/chat-surface";
import { api, ApiError } from "~/lib/api.server";
import { requireToken } from "~/lib/session.server";

/**
 * A conversation on a page of its own, and the actions that drive it.
 *
 * The same `ChatSurface` the library renders as a boxed overlay, in its `page`
 * mode — it has always taken that mode, and for a while nothing rendered it.
 * The overlay is where a *new* chat lands, because it is started from a card in
 * the grid and morphs out of it; this is where an existing one is opened, for
 * the room a long exchange needs.
 *
 * Its own loader rather than the workspace layout's: this route sits outside
 * that layout, and it needs one chat and the provider settings rather than
 * every note, every chat and the account.
 */
export async function loader({ request, params }: Route.LoaderArgs) {
  const token = await requireToken(request);
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
    if (error instanceof ApiError) return { ok: false as const, error: error.detail };
    throw error;
  }
}

export default function ChatRoute({ loaderData }: Route.ComponentProps) {
  const { chat, provider } = loaderData;
  const navigate = useNavigate();

  return (
    <ChatSurface
      chat={chat}
      provider={provider}
      mode="page"
      // The library is where a conversation came from, so it is where leaving
      // one goes. `replace` so the back button does not walk into the chat again.
      onClose={() => navigate("/notes", { replace: true })}
    />
  );
}
