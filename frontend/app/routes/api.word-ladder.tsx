import { api, ApiError } from "~/lib/api.server";
import type { Route } from "./+types/api.word-ladder";

/**
 * The word roller's data source: `/api/word-ladder?word=use`.
 *
 * A resource route — a loader and nothing else, no component. It exists so the
 * roller can reach the backend without going through `/notes`'s action, which
 * revalidates the workspace loader on every submission and would therefore
 * refetch the entire note list every time a chevron is clicked.
 *
 * It also keeps the API client server-side, which is the rule everywhere except
 * the two direct-from-browser calls that are already logged as a bug.
 */
export async function loader({ request }: Route.LoaderArgs) {
  const params = new URL(request.url).searchParams;
  const sentence = params.get("sentence") ?? "";
  const caret = Number(params.get("caret") ?? -1);
  if (!sentence || caret < 0) {
    return { ladder: null };
  }

  try {
    return { ladder: await api.getWordLadder(sentence, caret) };
  } catch (error) {
    // A word with no ladder is an ordinary outcome, not a failure — the roller
    // just has nowhere to climb. Never break the editor over a synonym lookup.
    if (error instanceof ApiError) {
      return { ladder: null };
    }
    throw error;
  }
}
