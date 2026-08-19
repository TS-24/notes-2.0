import { api } from "~/lib/api.server";
import { requireToken } from "~/lib/session.server";
import type { Route } from "./+types/api.vocabulary";

/**
 * The vocabulary analysis for one note, on demand.
 *
 * A resource route rather than a loader on the grid, because the analysis is
 * only wanted when the reader opens the quiz, and running it with the page
 * would analyse every note nobody asked about.
 *
 * Deliberately outside the workspace layout, for the same reason the word
 * ladder is: a fetcher submission to a route inside that layout revalidates
 * the whole note list, which would refetch every note each time the dialog
 * opens.
 *
 * An action rather than a loader because the analysis takes a note's whole
 * body, which is far too much to put in a query string.
 */
export async function action({ request }: Route.ActionArgs) {
  const token = await requireToken(request);
  const { title, content } = await request.json();
  const { vocabulary_analysis } = await api.analyzeVocabulary(token, {
    title: String(title ?? "Untitled"),
    content: String(content ?? ""),
  });
  return vocabulary_analysis;
}
