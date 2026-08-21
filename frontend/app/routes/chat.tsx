import type { Route } from "./+types/chat";
import { api, ApiError } from "~/lib/api.server";
import { requireToken } from "~/lib/session.server";

/**
 * Actions for the chat overlay: send and finish.
 *
 * No component, no loader — the chat renders as a boxed overlay inside the
 * workspace layout. These actions are the target of the fetchers inside
 * ChatSurface, which post here explicitly.
 */
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

export default function ChatRoute() {
  return null;
}
