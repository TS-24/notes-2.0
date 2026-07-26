import { useState } from "react";
import { useFetcher } from "react-router";
import { motion } from "framer-motion";
import { Masonry } from "masonic";
import { Pin, Trash2, Archive } from "lucide-react";
import NoteMaker from "~/notes/notemaker";
import { ClientOnly } from "~/components/client-only";
import type { Note } from "~/lib/types";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "~/components/ui/dialog";

// 1. Separate Child Component declared OUTSIDE to fix unmounting & state-loss bug
function NoteCard({ data }: { data: Note }) {
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

  const handleCardClick = (e: React.MouseEvent) => {
    // Only open dialog if we aren't clicking an action button
    if ((e.target as HTMLElement).closest('button')) return;
    setIsQuizMode(false);
    setIsDialogOpen(true);
    if (!vocabData) {
      fetchVocabulary();
    }
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

  // TODO(step 6): /api/analyze/vocabulary does not exist yet, and this is the
  // last place the browser still calls the backend directly. Both are fixed
  // when the vocabulary service is built.
  const fetchVocabulary = async () => {
    setLoading(true);
    try {
      const response = await fetch("http://127.0.0.1:8000/api/analyze/vocabulary", {
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
      await fetch("http://127.0.0.1:8000/api/words/known", {
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
        layout
        onClick={handleCardClick}
        whileHover={{ y: -4, boxShadow: "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)" }}
        transition={{ duration: 0.2 }}
        className="group relative flex flex-col justify-between p-5 rounded-2xl border bg-slate-50 border-slate-200 hover:bg-slate-100 dark:bg-slate-900/60 dark:border-slate-800/50 dark:hover:bg-slate-800/80 shadow-xs backdrop-blur-xs cursor-pointer"
      >
        <div>
          <div className="flex items-start justify-between gap-3 mb-2">
            {data.title && (
              <h3 className="font-bold text-sm tracking-tight text-zinc-900 dark:text-zinc-50">
                {data.title}
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
                className={`p-1.5 rounded-lg opacity-0 group-hover:opacity-100 focus:opacity-100 hover:bg-zinc-950/5 dark:hover:bg-white/5 transition-all cursor-pointer ${isPinned ? "opacity-100 text-zinc-900 dark:text-zinc-50" : "text-zinc-400"
                  }`}
              >
                <Pin className="size-3.5 fill-current" />
              </motion.button>
            </fetcher.Form>
          </div>
          <p className="text-xs leading-relaxed text-zinc-700 dark:text-zinc-300 whitespace-pre-line">
            {data.content}
          </p>
          {data.created_at && (
            <div className="mt-4 text-[10px] text-zinc-400 dark:text-zinc-500 font-medium">
              {new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(data.created_at))}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-2 mt-4 pt-2 border-t border-zinc-950/5 dark:border-white/5">
          {/* Action Toolbar */}
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
                  className="p-1.5 rounded-lg text-zinc-400 hover:text-red-500 hover:bg-red-500/10 transition-colors cursor-pointer"
                  title="Delete note"
                >
                  <Trash2 className="size-3.5" />
                </motion.button>
              </fetcher.Form>

              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={(e) => e.stopPropagation()}
                className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-100 hover:bg-zinc-950/5 dark:hover:bg-white/5 transition-colors cursor-pointer"
                title="Archive"
              >
                <Archive className="size-3.5" />
              </motion.button>
            </div>
            
            <button
              onClick={handleQuizClick}
              className="px-3 py-1.5 text-xs font-medium rounded-md bg-zinc-900 text-zinc-50 hover:bg-zinc-900/90 dark:bg-zinc-50 dark:text-zinc-900 dark:hover:bg-zinc-50/90 shadow-sm transition-colors cursor-pointer"
            >
              Review Words
            </button>
          </div>
        </div>
      </motion.div>

      <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
        <DialogContent className="sm:max-w-md max-h-[80vh] flex flex-col p-0 overflow-hidden">
          <DialogHeader className="px-6 pt-6 pb-2 shrink-0 flex flex-row items-start justify-between">
            <div>
              <DialogTitle>Vocabulary Analysis</DialogTitle>
              <DialogDescription>
                Difficult words found in "{data.title || 'this note'}".
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
export default function Notegrid({ notes }: { notes: Note[] }) {
  const pinnedNotes = notes.filter(n => n.is_pinned);
  const otherNotes = notes.filter(n => !n.is_pinned);

  return (
    <main className="flex-1 p-8 space-y-10 bg-zinc-50 dark:bg-zinc-950 min-h-screen font-sans">

      <NoteMaker />

      {pinnedNotes.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-[10px] font-bold tracking-wider text-zinc-400 uppercase px-1">
            Pinned
          </h2>
          <ClientOnly>
            <Masonry
              key={`pinned-${pinnedNotes.map(n => n.id).join("-")}`}
              items={pinnedNotes}
              columnWidth={240}
              columnGutter={16}
              render={({ data }) => <NoteCard data={data} />}
            />
          </ClientOnly>
        </div>
      )}

      {otherNotes.length > 0 && (
        <div className="space-y-4">
          {pinnedNotes.length > 0 && (
            <h2 className="text-[10px] font-bold tracking-wider text-zinc-400 uppercase px-1 pt-4">
              Others
            </h2>
          )}
          <ClientOnly>
            <Masonry
              key={`others-${otherNotes.map(n => n.id).join("-")}`}
              items={otherNotes}
              columnWidth={240}
              columnGutter={16}
              render={({ data }) => <NoteCard data={data} />}
            />
          </ClientOnly>
        </div>
      )}

      {notes.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center space-y-3">
          <div className="p-4 bg-zinc-100 dark:bg-zinc-900 rounded-full text-zinc-400">
            <Archive className="size-8" />
          </div>
          <h3 className="font-semibold text-zinc-900 dark:text-zinc-50 text-sm">No notes yet</h3>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-xs">
            Create your first note to start organizing your schedule!
          </p>
        </div>
      )}
    </main>
  );
}