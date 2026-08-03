import { useRouteLoaderData, useSearchParams } from "react-router";
import type { Route } from "./+types/library";
import LibraryGrid from "~/library/grid";
import { api, ApiError } from "~/lib/api.server";
import type { Note } from "~/lib/types";

export function meta() {
  return [{ title: "Library · Restyle" }, { name: "description", content: "Everything you have written" }];
}

// No loader: the workspace layout above holds the note list, so there is one
// fetch and one revalidation shared by the landing page and the grid.

/**
 * Every note mutation goes through here. The browser submits a form, React
 * Router runs this on the server, and the loader above re-runs automatically —
 * so the UI reflects the database without any manual refetching.
 */
export async function action({ request }: Route.ActionArgs) {
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
        const created = await api.createNote({ title: title || "Untitled", content });
        return { ok: true, id: created.id };
      }
      case "update": {
        const id = Number(formData.get("id"));
        const title = String(formData.get("title") ?? "").trim();
        const content = String(formData.get("content") ?? "").trim();
        // Same fallback as create: the API rejects an empty title, but the
        // expanded editor lets you clear the field.
        await api.updateNote(id, { title: title || "Untitled", content });
        return { ok: true };
      }
      case "togglePin": {
        const id = Number(formData.get("id"));
        const isPinned = formData.get("isPinned") === "true";
        await api.updateNote(id, { is_pinned: !isPinned });
        return { ok: true };
      }
      case "touch": {
        // Opening a note counts as an update for "where you left off".
        await api.touchNote(Number(formData.get("id")));
        return { ok: true };
      }
      case "delete": {
        await api.deleteNote(Number(formData.get("id")));
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
  const workspace = useRouteLoaderData("routes/workspace") as {
    notes: Note[];
  };
  const [searchParams] = useSearchParams();
  const open = Number(searchParams.get("open"));

  return (
    <LibraryGrid
      notes={workspace.notes}
      openNoteId={Number.isFinite(open) && open > 0 ? open : null}
    />
  );
}
