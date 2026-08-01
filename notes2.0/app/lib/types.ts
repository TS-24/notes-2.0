/**
 * Shapes returned by the backend API.
 *
 * These live outside api.server.ts so that client components can import them
 * without pulling server-only code into the browser bundle. Keep them in sync
 * with the Pydantic schemas in backend/app/schemas/.
 */

/** Mirrors backend/app/schemas/word_definition.py::WordDefinitionRead */
export interface WordDefinition {
  id: number;
  word: string;
  definition: string | null;
}

/** Mirrors backend/app/schemas/word_ladder.py::WordLadderRead */
export interface WordLadder {
  id: number;
  word: string;
  /** The WordNet part of speech the rungs were drawn from; "" when none. */
  pos: string;
  /** Plainest first. Climbing up the ladder means climbing this array. */
  rungs: string[];
  /** Where `word` itself sits in `rungs`. */
  origin_index: number;
}

/** Mirrors backend/app/schemas/note.py::NoteRead */
export interface Note {
  id: number;
  title: string;
  content: string | null;
  user_id: number;
  is_pinned: boolean;
  created_at: string;
  /** Bumped by edits and by opening the note — drives "where you left off". */
  updated_at: string;
  words: WordDefinition[];
}

/** Mirrors backend/app/schemas/user.py::UserRead */
export interface User {
  id: number;
  username: string;
  email: string;
}
