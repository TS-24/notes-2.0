import { useRouteLoaderData, useSearchParams } from "react-router";
import type { Route } from "./+types/notes";
import Notegrid from "~/notes/notegrid";
import { api, ApiError } from "~/lib/api.server";
import { requireToken } from "~/lib/session.server";
import type { Note } from "~/lib/types";

export function meta() {
  return [{ title: "Notes" }, { name: "description", content: "Your notes" }];
}

// No loader: the workspace layout above holds the note list, so there is one
// fetch and one revalidation shared by the landing page and the grid.

/**
 * Every note mutation goes through here. The browser submits a form, React
 * Router runs this on the server, and the loader above re-runs automatically —
 * so the UI reflects the database without any manual refetching.
 */
export async function action({ request }: Route.ActionArgs) {
  const token = await requireToken(request);
  const formData = await request.formData();
  const intent = formData.get("intent");

  try {
    switch (intent) {
      case "create": {
        const title = String(formData.get("title") ?? "").trim();
        const content = String(formData.get("content") ?? "").trim();
        // The API requires a non-empty title, but the composer allows
        // body-only notes, so fall back to a placeholder.
        // The id comes back so the ghost card can open the note it just made.
        const created = await api.createNote(token, { title: title || "Untitled", content });
        return { ok: true, id: created.id };
      }
      case "update": {
        const id = Number(formData.get("id"));
        const title = String(formData.get("title") ?? "").trim();
        const content = String(formData.get("content") ?? "").trim();
        // Same fallback as create: the API rejects an empty title, but the
        // expanded editor lets you clear the field.
        await api.updateNote(token, id, { title: title || "Untitled", content });
        return { ok: true };
      }
      case "togglePin": {
        const id = Number(formData.get("id"));
        const isPinned = formData.get("isPinned") === "true";
        await api.updateNote(token, id, { is_pinned: !isPinned });
        return { ok: true };
      }
      case "touch": {
        // Opening a note counts as an update for "where you left off".
        await api.touchNote(token, Number(formData.get("id")));
        return { ok: true };
      }
      case "delete": {
        await api.deleteNote(token, Number(formData.get("id")));
        return { ok: true };
      }
      case "markKnown": {
        // Moved off a browser fetch to a hardcoded host. It is a user-scoped
        // write, so it is the one of the three that silently did nothing
        // rather than merely failing to load.
        const words = formData.getAll("word").map(String);
        await api.markWordsKnown(token, words);
        return { ok: true };
      }
      default:
        return { ok: false, error: `Unknown intent: ${String(intent)}` };
    }
  } catch (error) {
    // Surface API failures to the UI instead of crashing the whole route.
    if (error instanceof ApiError) {
      return { ok: false, error: error.detail };
    }
    throw error;
  }
}

export default function Notes() {
  const workspace = useRouteLoaderData("routes/workspace") as { notes: Note[] };
  const [searchParams] = useSearchParams();
  const open = Number(searchParams.get("open"));

  // No chats: the library is a list of notes, and a conversation is reached by
  // opening the note it belongs to. `?chat=` is the workspace layout's to read.
  return (
    <Notegrid
      notes={workspace.notes}
      openNoteId={Number.isFinite(open) && open > 0 ? open : null}
    />
  );
}
