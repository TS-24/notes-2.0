import { useState } from "react";
import { Masonry } from "masonic";
import { Pin, Trash2, Palette, Archive, Sparkles, Check } from "lucide-react";
import { COLORS } from "~/lib/colors";
import NoteMaker from "~/notes/notemaker";

interface Note {
  id: string;
  title: string;
  content: string;
  colorId: string; // References COLORS key
  isPinned: boolean;
}

const INITIAL_NOTES: Note[] = [
  {
    id: "1",
    title: "💡 Project Ideas",
    content: "Build a high-performance notes app using React Router v7. Focus on micro-animations, theme support, and seamless database sync using Postgres.",
    colorId: "indigo",
    isPinned: true,
  },
  {
    id: "2",
    title: "🥦 Weekly Groceries",
    content: "• Almond milk (unsweetened)\n• Fresh avocados\n• Baby spinach & kale\n• Greek yogurt\n• Chia seeds",
    colorId: "emerald",
    isPinned: true,
  },
  {
    id: "3",
    title: "📚 COMP 325 Architecture Study",
    content: "Review Instruction Set Architectures (ISA), memory caches, pipeline hazards, and assembly practice questions.",
    colorId: "amber",
    isPinned: false,
  },
  {
    id: "4",
    title: "💡 Internship Goals",
    content: "Complete Duke Energy onboarding, meet with the senior database engineers, and learn more about their SQL Server query optimization techniques.",
    colorId: "sky",
    isPinned: false,
  },
  {
    id: "5",
    title: "☕ Coffee Shops to Try",
    content: "Optimist Hall Coffee, Undercurrent Coffee (Charlotte), and local spots near Grove City.",
    colorId: "purple",
    isPinned: false,
  },
];

// 1. Separate Child Component declared OUTSIDE to fix unmounting & state-loss bug
interface NoteCardProps {
  data: Note;
  onTogglePin: (id: string) => void;
  onDelete: (id: string) => void;
  onChangeColor: (id: string, colorId: string) => void;
}

function NoteCard({ data, onTogglePin, onDelete, onChangeColor }: NoteCardProps) {
  const [showColorPicker, setShowColorPicker] = useState(false);
  const currentColor = COLORS.find(c => c.id === data.colorId) || COLORS[0];

  return (
    <div
      className={`group relative flex flex-col justify-between p-5 rounded-2xl border ${currentColor.bg} ${currentColor.border} shadow-xs hover:shadow-md transition-all duration-300 backdrop-blur-xs`}
    >
      <div>
        <div className="flex items-start justify-between gap-3 mb-2">
          {data.title && (
            <h3 className="font-bold text-sm tracking-tight text-zinc-900 dark:text-zinc-50">
              {data.title}
            </h3>
          )}
          <button
            onClick={() => onTogglePin(data.id)}
            className={`p-1.5 rounded-lg opacity-0 group-hover:opacity-100 focus:opacity-100 hover:bg-zinc-950/5 dark:hover:bg-white/5 transition-all cursor-pointer ${
              data.isPinned ? "opacity-100 text-zinc-900 dark:text-zinc-50" : "text-zinc-400"
            }`}
          >
            <Pin className="size-3.5 fill-current" />
          </button>
        </div>
        <p className="text-xs leading-relaxed text-zinc-700 dark:text-zinc-300 whitespace-pre-line">
          {data.content}
        </p>
      </div>

      <div className="flex flex-col gap-2 mt-4 pt-2 border-t border-zinc-950/5 dark:border-white/5">
        {/* Action Toolbar */}
        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
          <button
            onClick={() => onDelete(data.id)}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-red-500 hover:bg-red-500/10 transition-colors cursor-pointer"
            title="Delete note"
          >
            <Trash2 className="size-3.5" />
          </button>
          
          <div className="relative">
            <button
              onClick={() => setShowColorPicker(!showColorPicker)}
              className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
                showColorPicker 
                  ? "text-zinc-900 dark:text-zinc-50 bg-zinc-950/10 dark:bg-white/10" 
                  : "text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-100 hover:bg-zinc-950/5 dark:hover:bg-white/5"
              }`}
              title="Change color"
            >
              <Palette className="size-3.5" />
            </button>

            {/* Quick Color Picker Dropdown */}
            {showColorPicker && (
              <div className="absolute bottom-full left-0 z-20 mb-2 p-2 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-xl flex gap-1.5 items-center">
                {COLORS.map((c) => (
                  <button
                    key={c.id}
                    onClick={() => {
                      onChangeColor(data.id, c.id);
                      setShowColorPicker(false);
                    }}
                    className={`size-5 rounded-full border cursor-pointer flex items-center justify-center transition-transform hover:scale-110 ${c.dot} ${
                      data.colorId === c.id 
                        ? "border-zinc-900 dark:border-zinc-50 scale-105" 
                        : "border-zinc-300 dark:border-zinc-600"
                    }`}
                    title={c.name}
                  >
                    {data.colorId === c.id && <Check className="size-2.5 text-white dark:text-zinc-950 stroke-[3px]" />}
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-100 hover:bg-zinc-950/5 dark:hover:bg-white/5 transition-colors cursor-pointer"
            title="Archive"
          >
            <Archive className="size-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

// 2. Parent Container Component
export default function Notegrid() {
  const [notes, setNotes] = useState<Note[]>(INITIAL_NOTES);

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

  const changeColor = (id: string, colorId: string) => {
    setNotes(prev =>
      prev.map(note =>
        note.id === id ? { ...note, colorId } : note
      )
    );
  };

  const addNote = (newNote: { title: string; content: string; colorId: string; isPinned: boolean }) => {
    setNotes(prev => [
      {
        id: Date.now().toString(),
        ...newNote,
      },
      ...prev,
    ]);
  };

  const pinnedNotes = notes.filter(n => n.isPinned);
  const otherNotes = notes.filter(n => !n.isPinned);

  return (
    <main className="flex-1 p-8 space-y-10 bg-zinc-50 dark:bg-zinc-950 min-h-screen font-sans">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-zinc-950/5 dark:bg-white/5 border border-zinc-200 dark:border-zinc-800 rounded-xl">
            <Sparkles className="size-6 text-zinc-900 dark:text-zinc-50" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">My Notes</h1>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Manage your tasks, files, and daily thoughts.
            </p>
          </div>
        </div>
      </div>

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
                onChangeColor={changeColor}
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
                onChangeColor={changeColor}
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