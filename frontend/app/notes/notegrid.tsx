import { useCallback, useEffect, useRef, useState } from "react";
import { useFetcher, useNavigate } from "react-router";
import { motion } from "framer-motion";
import { Pin, Trash2, Archive, Plus } from "lucide-react";
import {
  noteLayoutId,
  NOTE_LAYOUT_TRANSITION,
} from "~/workspace/note-surface";
import type { Note } from "~/lib/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "~/components/ui/dialog";

/**
 * The empty card that starts a new note. It sits in the grid rather than above
 * it. No real note has id 0.
 */
const GHOST_ID = 0;
type GhostItem = { id: typeof GHOST_ID; ghost: true };
type GridItem = Note | GhostItem;
const GHOST: GhostItem = { id: GHOST_ID, ghost: true };

function GhostNote({ onClick }: { onClick: () => void }) {
  return (
    <motion.button
      type="button"
      layoutId={noteLayoutId(GHOST_ID)}
      onClick={onClick}
      title="New note"
      aria-label="New note"
      style={{ borderRadius: 16 }}
      transition={{ layout: NOTE_LAYOUT_TRANSITION }}
      className="flex min-h-[200px] w-full items-center justify-center border-2 border-dashed border-hairline text-rose-ink cursor-pointer transition-colors hover:border-rose-ink/60 hover:bg-paper-raised/60"
    >
      <Plus className="size-7" strokeWidth={1.5} />
    </motion.button>
  );
}

// 1. Separate Child Component declared OUTSIDE to fix unmounting & state-loss bug
function NoteCard({
  data,
  onExpand,
}: {
  data: Note;
  onExpand: (note: Note) => void;
}) {
  // Each card owns its fetcher so simultaneous pins/deletes don't clobber
  // each other's pending state.
  const fetcher = useFetcher();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [vocabData, setVocabData] = useState<{ total_difficult_words: number, definitions: Record<string, string> } | null>(null);
  const [loading, setLoading] = useState(false);

  // Flashcard State
  const [isQuizMode, setIsQuizMode] = useState(false);
  const [currentWordIndex, setCurrentWordIndex] = useState(0);

  // Optimistic UI: while a mutation is in flight, render what the user asked
  // for rather than the stale server value.
  const isPinned = fetcher.formData
    ? fetcher.formData.get("isPinned") === "false"
    : data.is_pinned;
  const isDeleting = fetcher.formData?.get("intent") === "delete";
  const title = data.title;
  const content = data.content;

  const handleCardDoubleClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button')) return;
    onExpand(data);
  };

  const handleQuizClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsQuizMode(true);
    setCurrentWordIndex(0);
    setIsDialogOpen(true);
    if (!vocabData) {
      fetchVocabulary();
    }
  };

  // TODO: the endpoint exists now, but this and analytics.tsx are the last
  // places the browser still calls the backend directly. The hardcoded host
  // breaks anywhere the API is not on the viewer's own localhost.
  const fetchVocabulary = async () => {
    setLoading(true);
    try {
      const response = await fetch("http://127.0.0.1:8700/api/analyze/vocabulary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (response.ok) {
        const result = await response.json();
        setVocabData(result.vocabulary_analysis);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const words = vocabData ? Object.keys(vocabData.definitions) : [];
  const currentWord = words[currentWordIndex];

  const handleNext = () => {
    setCurrentWordIndex((prev) => (prev + 1) % words.length);
  };

  const markAsKnown = async (word: string) => {
    if (vocabData) {
      const newDefs = { ...vocabData.definitions };
      delete newDefs[word];
      const remainingWords = Object.keys(newDefs);
      
      setVocabData({
        ...vocabData,
        definitions: newDefs,
        total_difficult_words: remainingWords.length
      });
      
      if (currentWordIndex >= remainingWords.length) {
        setCurrentWordIndex(Math.max(0, remainingWords.length - 1));
      }
    }

    try {
      await fetch("http://127.0.0.1:8700/api/words/known", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ words: [word] })
      });
    } catch (e) {
      console.error(e);
    }
  };

  // Remove the card immediately on delete instead of waiting for the round trip.
  if (isDeleting) return null;

  return (
    <>
      <motion.div
        // Shared with the expanded editor, so the card morphs into it — and so
        // the other cards glide to their new spots when the grid reflows.
        layoutId={noteLayoutId(data.id)}
        data-note-card
        onDoubleClick={handleCardDoubleClick}
        whileHover={{ y: -4, boxShadow: "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)" }}
        transition={{ layout: NOTE_LAYOUT_TRANSITION, duration: 0.2 }}
        style={{ borderRadius: 16 }}
        title="Double click to open"
        // No border, no shadow, no blur — one step of paper tone (DESIGN.md §5).
        className="group relative flex flex-col justify-between p-7 bg-paper-raised cursor-pointer select-none"
      >
        {/*
          layout="position" counter-scales the card's contents, so collapsing
          back out of the editor resizes the box without warping the text.
        */}
        <motion.div
          layout="position"
          transition={{ layout: NOTE_LAYOUT_TRANSITION }}
        >
          <div className="flex items-start justify-between gap-3 mb-2">
            {title && (
              <h3 className="font-display text-lg font-medium leading-snug tracking-tight text-ink">
                {title}
              </h3>
            )}
            <fetcher.Form method="post">
              <input type="hidden" name="intent" value="togglePin" />
              <input type="hidden" name="id" value={data.id} />
              <input type="hidden" name="isPinned" value={String(data.is_pinned)} />
              <motion.button
                type="submit"
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={(e) => e.stopPropagation()}
                className={`p-1.5 rounded-lg opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all cursor-pointer ${isPinned ? "opacity-100 text-rose-ink" : "text-ink/35 hover:text-ink"
                  }`}
              >
                <Pin className="size-3.5 fill-current" />
              </motion.button>
            </fetcher.Form>
          </div>
          <p className="mt-2 text-base leading-relaxed text-ink/85 whitespace-pre-line">
            {content}
          </p>
          {data.created_at && (
            <div className="mt-6 text-sm italic text-ink/45">
              {new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(data.created_at))}
            </div>
          )}
        </motion.div>

        <motion.div
          layout="position"
          transition={{ layout: NOTE_LAYOUT_TRANSITION }}
          className="flex flex-col gap-2 mt-8"
        >
          {/* Action Toolbar — separated by space, not a rule. */}
          <div className="flex items-center justify-between opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
            <div className="flex items-center gap-2">
              <fetcher.Form method="post">
                <input type="hidden" name="intent" value="delete" />
                <input type="hidden" name="id" value={data.id} />
                <motion.button
                  type="submit"
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  onClick={(e) => e.stopPropagation()}
                  className="p-1.5 rounded-lg text-ink/35 hover:text-red-600 transition-colors cursor-pointer"
                  title="Delete note"
                >
                  <Trash2 className="size-3.5" />
                </motion.button>
              </fetcher.Form>

              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={(e) => e.stopPropagation()}
                className="p-1.5 rounded-lg text-ink/35 hover:text-ink transition-colors cursor-pointer"
                title="Archive"
              >
                <Archive className="size-3.5" />
              </motion.button>
            </div>
            
            <button
              onClick={handleQuizClick}
              className="px-4 py-1.5 text-sm rounded-lg bg-accent-rose text-on-rose hover:opacity-90 transition-opacity cursor-pointer"
            >
              Review Words
            </button>
          </div>
        </motion.div>
      </motion.div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-md max-h-[80vh] flex flex-col p-0 overflow-hidden">
          <DialogHeader className="px-6 pt-6 pb-2 shrink-0 flex flex-row items-start justify-between">
            <div>
              <DialogTitle>Vocabulary Analysis</DialogTitle>
              <DialogDescription>
                Difficult words found in "{title || 'this note'}".
              </DialogDescription>
            </div>
          </DialogHeader>
          <div className="flex-1 overflow-y-auto custom-scrollbar px-6 pb-6 mt-2">
            {loading ? (
              <p className="text-sm text-zinc-500">Analyzing vocabulary...</p>
            ) : vocabData ? (
              words.length > 0 ? (
                isQuizMode ? (
                  <div className="flex flex-col items-center justify-center min-h-[250px] p-6 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-sm relative">
                    <button 
                      onClick={() => setIsQuizMode(false)}
                      className="absolute top-4 left-4 text-xs font-medium text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200 cursor-pointer"
                    >
                      &larr; Back to List
                    </button>
                    
                    <div className="flex flex-col items-center justify-center w-full mt-6">
                      <h2 className="text-3xl font-bold capitalize text-blue-600 dark:text-blue-400 mb-2">
                        {currentWord}
                      </h2>
                      <p className="text-base text-center font-medium text-zinc-700 dark:text-zinc-300 mb-6">
                        {vocabData.definitions[currentWord]}
                      </p>
                      
                      <div className="w-full text-center space-y-4">
                        <p className="text-sm text-zinc-500">Keep this word in your difficult words list?</p>
                        <div className="flex items-center justify-center gap-3">
                          {words.length > 1 && (
                            <button
                              onClick={handleNext}
                              className="px-4 py-2 text-sm font-medium bg-zinc-100 text-zinc-700 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700 rounded-lg transition-colors cursor-pointer"
                            >
                              Keep
                            </button>
                          )}
                          <button
                            onClick={() => markAsKnown(currentWord)}
                            className="px-4 py-2 text-sm font-medium bg-red-100 text-red-700 hover:bg-red-200 dark:bg-red-900/30 dark:text-red-400 dark:hover:bg-red-900/50 rounded-lg transition-colors cursor-pointer"
                          >
                            Remove
                          </button>
                        </div>
                      </div>
                    </div>
                    
                    <div className="absolute bottom-4 text-xs text-zinc-400 font-medium">
                      Word {currentWordIndex + 1} of {words.length}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4 pr-2">
                    {Object.entries(vocabData.definitions).map(([word, def]) => (
                      <div key={word} className="border-b border-zinc-100 dark:border-zinc-800 pb-2 last:border-0">
                        <h4 className="font-semibold capitalize text-blue-600 dark:text-blue-400">{word}</h4>
                        <p className="text-sm text-zinc-600 dark:text-zinc-300 mt-1">{def}</p>
                      </div>
                    ))}
                  </div>
                )
              ) : (
                <div className="flex flex-col items-center justify-center py-10 text-center space-y-3">
                  <div className="p-3 bg-green-100 dark:bg-green-900/20 rounded-full text-green-500">
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">You know all the words here!</p>
                  <p className="text-xs text-zinc-500">No complex vocabulary remaining in this note.</p>
                </div>
              )
            ) : (
              <p className="text-sm text-red-500">Failed to load vocabulary analysis.</p>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// 2. Parent Container Component
// Notes now arrive from the route loader, so this component holds no data state
// of its own — the database is the single source of truth.
export default function Notegrid({
  notes,
  openNoteId = null,
}: {
  notes: Note[];
  /** Set when the landing hero handed a note over to be opened on arrival. */
  openNoteId?: number | null;
}) {
  // The open note is the workspace layout's, not the grid's — the grid only
  // has to leave a gap where it went. `?open=` is the single source of truth,
  // so opening is a URL change rather than local state.
  const navigate = useNavigate();
  const createFetcher = useFetcher<{ ok: boolean; id?: number }>();

  const gridNotes = notes.filter(n => n.id !== openNoteId);
  const pinnedNotes = gridNotes.filter(n => n.is_pinned);
  const otherNotes: GridItem[] = [
    GHOST,
    ...gridNotes.filter(n => !n.is_pinned),
  ];

  const handleExpand = useCallback(
    (note: Note) => navigate(`/notes?open=${note.id}`, { preventScrollReset: true }),
    [navigate],
  );

  // A new note has to exist before it can be the focused note, so the ghost
  // creates it and then opens it by id.
  const handleCompose = useCallback(() => {
    createFetcher.submit(
      { intent: "create", title: "Untitled", content: "" },
      { method: "post", action: "/notes" },
    );
  }, [createFetcher]);

  const openedNew = useRef(false);
  useEffect(() => {
    const id = createFetcher.data?.id;
    if (createFetcher.state !== "idle" || !id || openedNew.current) return;
    openedNew.current = true;
    navigate(`/notes?open=${id}`, { preventScrollReset: true });
  }, [createFetcher.state, createFetcher.data, navigate]);

  /**
   * CSS columns rather than a masonry library. The browser balances the
   * columns, every card is a keyed child that updates instead of remounting,
   * and it server-renders — so opening a note animates the rest of the grid
   * into its new shape rather than tearing the grid down and rebuilding it.
   */
  const columns = (items: GridItem[]) => (
    <div className="columns-[280px] gap-6">
      {items.map(item => (
        <div key={item.id} className="mb-6 break-inside-avoid">
          {"ghost" in item ? (
            <GhostNote onClick={handleCompose} />
          ) : (
            <NoteCard data={item} onExpand={handleExpand} />
          )}
        </div>
      ))}
    </div>
  );

  return (
    // The surrounding page and the open note belong to the workspace layout;
    // this is only the grid that arrives beneath them.
    <div className="space-y-16">
      {pinnedNotes.length > 0 && (
        <div className="space-y-4">
          <h2 className="font-display text-2xl font-medium tracking-tight text-ink">
            Pinned
          </h2>
          {columns(pinnedNotes)}
        </div>
      )}

      {otherNotes.length > 0 && (
        <div className="space-y-4">
          {pinnedNotes.length > 0 && (
            <h2 className="font-display text-2xl font-medium tracking-tight text-ink pt-4">
              Others
            </h2>
          )}
          {columns(otherNotes)}
        </div>
      )}
    </div>
  );
}