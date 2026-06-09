import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Masonry } from "masonic";
import { Pin, Trash2, Archive } from "lucide-react";
import NoteMaker from "~/notes/notemaker";

interface Note {
  id: string;
  title: string;
  content: string;
  colorId: string; // References COLORS key
  isPinned: boolean;
  createdAt?: string;
}


// 1. Separate Child Component declared OUTSIDE to fix unmounting & state-loss bug
interface NoteCardProps {
  data: Note;
  onTogglePin: (id: string) => void;
  onDelete: (id: string) => void;
}

function NoteCard({ data, onTogglePin, onDelete }: NoteCardProps) {
  return (
    <motion.div
      layout
      whileHover={{ y: -4, boxShadow: "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)" }}
      transition={{ duration: 0.2 }}
      className="group relative flex flex-col justify-between p-5 rounded-2xl border bg-slate-50 border-slate-200 hover:bg-slate-100 dark:bg-slate-900/60 dark:border-slate-800/50 dark:hover:bg-slate-800/80 shadow-xs backdrop-blur-xs"
    >
      <div>
        <div className="flex items-start justify-between gap-3 mb-2">
          {data.title && (
            <h3 className="font-bold text-sm tracking-tight text-zinc-900 dark:text-zinc-50">
              {data.title}
            </h3>
          )}
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => onTogglePin(data.id)}
            className={`p-1.5 rounded-lg opacity-0 group-hover:opacity-100 focus:opacity-100 hover:bg-zinc-950/5 dark:hover:bg-white/5 transition-all cursor-pointer ${data.isPinned ? "opacity-100 text-zinc-900 dark:text-zinc-50" : "text-zinc-400"
              }`}
          >
            <Pin className="size-3.5 fill-current" />
          </motion.button>
        </div>
        <p className="text-xs leading-relaxed text-zinc-700 dark:text-zinc-300 whitespace-pre-line">
          {data.content}
        </p>
        {data.createdAt && (
          <div className="mt-4 text-[10px] text-zinc-400 dark:text-zinc-500 font-medium">
            {new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(data.createdAt))}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2 mt-4 pt-2 border-t border-zinc-950/5 dark:border-white/5">
        {/* Action Toolbar */}
        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => onDelete(data.id)}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-red-500 hover:bg-red-500/10 transition-colors cursor-pointer"
            title="Delete note"
          >
            <Trash2 className="size-3.5" />
          </motion.button>

          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-100 hover:bg-zinc-950/5 dark:hover:bg-white/5 transition-colors cursor-pointer"
            title="Archive"
          >
            <Archive className="size-3.5" />
          </motion.button>
        </div>
      </div>
    </motion.div>
  );
}

// 2. Parent Container Component
export default function Notegrid() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("notes");
    if (saved) {
      try {
        setNotes(JSON.parse(saved));
      } catch (e) {}
    }
    setIsLoaded(true);
  }, []);

  useEffect(() => {
    if (isLoaded) {
      localStorage.setItem("notes", JSON.stringify(notes));
    }
  }, [notes, isLoaded]);

  const togglePin = (id: string) => {
    setNotes(prev =>
      prev.map(note =>
        note.id === id ? { ...note, isPinned: !note.isPinned } : note
      )
    );
  };

  const deleteNote = (id: string) => {
    setNotes(prev => prev.filter(note => note.id !== id));
  };

  const addNote = (newNote: { title: string; content: string; colorId: string; isPinned: boolean; createdAt?: string }) => {
    setNotes(prev => [
      {
        id: Date.now().toString(),
        createdAt: new Date().toISOString(),
        ...newNote,
      },
      ...prev,
    ]);
  };

  const pinnedNotes = notes.filter(n => n.isPinned);
  const otherNotes = notes.filter(n => !n.isPinned);

  return (
    <main className="flex-1 p-8 space-y-10 bg-zinc-50 dark:bg-zinc-950 min-h-screen font-sans">

      <NoteMaker onAddNote={addNote} />

      {pinnedNotes.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-[10px] font-bold tracking-wider text-zinc-400 uppercase px-1">
            Pinned
          </h2>
          <Masonry
            key={`pinned-${pinnedNotes.map(n => n.id).join("-")}`}
            items={pinnedNotes}
            columnWidth={240}
            columnGutter={16}
            render={({ data }) => (
              <NoteCard
                data={data}
                onTogglePin={togglePin}
                onDelete={deleteNote}
              />
            )}
          />
        </div>
      )}

      {otherNotes.length > 0 && (
        <div className="space-y-4">
          {pinnedNotes.length > 0 && (
            <h2 className="text-[10px] font-bold tracking-wider text-zinc-400 uppercase px-1 pt-4">
              Others
            </h2>
          )}
          <Masonry
            key={`others-${otherNotes.map(n => n.id).join("-")}`}
            items={otherNotes}
            columnWidth={240}
            columnGutter={16}
            render={({ data }) => (
              <NoteCard
                data={data}
                onTogglePin={togglePin}
                onDelete={deleteNote}
              />
            )}
          />
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