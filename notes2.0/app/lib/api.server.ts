/**
 * Typed client for the FastAPI backend.
 *
 * The `.server.ts` suffix keeps this out of the browser bundle: it is only ever
 * imported by loaders and actions, which run on the React Router server. That
 * means the browser never talks to the backend directly, so there is no CORS to
 * configure and the API host stays private to the compose network.
 */

import type { Note, User, WordDefinition, WordLadder } from "./types";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!response.ok) {
    // FastAPI puts human-readable errors in `detail`; fall back to the status
    // text when the body is not JSON (e.g. a proxy returned HTML).
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // keep statusText
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content has an empty body, so there is nothing to parse.
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  /** The signed-in user. Currently the seeded dev user. */
  getCurrentUser: () => request<User>("/api/users/me"),

  listNotes: (options: { search?: string } = {}) => {
    const params = new URLSearchParams();
    if (options.search) params.set("search", options.search);
    const query = params.toString();
    return request<Note[]>(`/api/notes${query ? `?${query}` : ""}`);
  },

  getNote: (id: number) => request<Note>(`/api/notes/${id}`),

  createNote: (data: { title: string; content?: string | null }) =>
    request<Note>("/api/notes", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateNote: (
    id: number,
    data: { title?: string; content?: string | null; is_pinned?: boolean },
  ) =>
    request<Note>(`/api/notes/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  /** Records that a note was opened, moving it to the head of the list. */
  touchNote: (id: number) =>
    request<Note>(`/api/notes/${id}/touch`, { method: "POST" }),

  deleteNote: (id: number) =>
    request<void>(`/api/notes/${id}`, { method: "DELETE" }),

  listWords: () => request<WordDefinition[]>("/api/words"),

  /**
   * A word's replacements ordered plainest to rarest — what the roller climbs.
   *
   * `sentence` and the offsets within it are only read by the contextual
   * engine; the WordNet one answers from the word alone and ignores them.
   */
  getWordLadder: (
    word: string,
    context?: { sentence: string; start: number; end: number },
  ) => {
    const params = new URLSearchParams({ word });
    if (context) {
      params.set("sentence", context.sentence);
      params.set("start", String(context.start));
      params.set("end", String(context.end));
    }
    return request<WordLadder>(`/api/vocab/ladder?${params}`);
  },

  attachWord: (noteId: number, wordId: number) =>
    request<Note>(`/api/notes/${noteId}/words/${wordId}`, { method: "POST" }),

  detachWord: (noteId: number, wordId: number) =>
    request<Note>(`/api/notes/${noteId}/words/${wordId}`, { method: "DELETE" }),
};
