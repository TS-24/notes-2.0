import { useState, useRef, useEffect } from "react";
import { Pin, Palette, Check, Plus } from "lucide-react";
import { COLORS } from "~/lib/colors";

interface NoteMakerProps {
  onAddNote: (note: { title: string; content: string; colorId: string; isPinned: boolean }) => void;
}

export default function NoteMaker({ onAddNote }: NoteMakerProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [colorId, setColorId] = useState("default");
  const [isPinned, setIsPinned] = useState(false);
  const [showColorPicker, setShowColorPicker] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLTextAreaElement>(null);

  const currentColor = COLORS.find(c => c.id === colorId) || COLORS[0];

  // Auto-resize textarea height
  useEffect(() => {
    if (contentRef.current) {
      contentRef.current.style.height = "auto";
      contentRef.current.style.height = `${contentRef.current.scrollHeight}px`;
    }
  }, [content]);

  // Click outside listener to auto-submit and collapse
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        handleClose();
      }
    }
    if (isExpanded) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isExpanded, title, content, colorId, isPinned]);

  const handleClose = () => {
    if (title.trim() || content.trim()) {
      onAddNote({
        title: title.trim(),
        content: content.trim(),
        colorId,
        isPinned,
      });
    }
    // Reset state
    setTitle("");
    setContent("");
    setColorId("default");
    setIsPinned(false);
    setIsExpanded(false);
    setShowColorPicker(false);
  };

  return (
    <div className="flex justify-center w-full px-4 mb-6">
      <div
        ref={containerRef}
        className={`w-full max-w-xl transition-all duration-300 border rounded-2xl shadow-sm hover:shadow-md ${
          isExpanded 
            ? `${currentColor.bg} ${currentColor.border} p-5` 
            : "bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 py-3 px-5 flex items-center gap-3 cursor-pointer"
        }`}
        onClick={() => !isExpanded && setIsExpanded(true)}
      >
        {!isExpanded ? (
          <div className="flex items-center justify-between w-full">
            <span className="text-sm font-medium text-zinc-400 dark:text-zinc-500">
              Take a note...
            </span>
            <div className="p-1 rounded-lg text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-50 hover:bg-zinc-50 dark:hover:bg-zinc-800 transition-colors">
              <Plus className="size-4" />
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {/* Title & Pin Bar */}
            <div className="flex items-center justify-between gap-3">
              <input
                type="text"
                placeholder="Title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-transparent border-none outline-none font-bold text-sm text-zinc-900 dark:text-zinc-50 placeholder-zinc-400 dark:placeholder-zinc-500"
                autoFocus
              />
              <button
                type="button"
                onClick={() => setIsPinned(!isPinned)}
                className={`p-1.5 rounded-lg transition-colors cursor-pointer hover:bg-zinc-950/5 dark:hover:bg-white/5 ${
                  isPinned ? "text-zinc-900 dark:text-zinc-50" : "text-zinc-400"
                }`}
                title="Pin note"
              >
                <Pin className="size-4 fill-current" />
              </button>
            </div>

            {/* Content Field */}
            <textarea
              ref={contentRef}
              placeholder="Take a note..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={1}
              className="w-full bg-transparent border-none outline-none resize-none text-xs text-zinc-700 dark:text-zinc-300 placeholder-zinc-400 dark:placeholder-zinc-500 leading-relaxed min-h-[36px]"
            />

            {/* Bottom Controls */}
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-zinc-950/5 dark:border-white/5">
              <div className="flex items-center gap-1">
                {/* Palette trigger */}
                <div className="relative">
                  <button
                    type="button"
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

                  {/* Inline Color Palette Bubble Selector */}
                  {showColorPicker && (
                    <div className="absolute bottom-full left-0 z-30 mb-2 p-2 bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-xl flex gap-1.5 items-center">
                      {COLORS.map((c) => (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => {
                            setColorId(c.id);
                            setShowColorPicker(false);
                          }}
                          className={`size-5 rounded-full border cursor-pointer flex items-center justify-center transition-transform hover:scale-110 ${c.dot} ${
                            colorId === c.id 
                              ? "border-zinc-900 dark:border-zinc-50 scale-105" 
                              : "border-zinc-300 dark:border-zinc-600"
                          }`}
                          title={c.name}
                        >
                          {colorId === c.id && <Check className="size-2.5 text-white dark:text-zinc-950 stroke-[3px]" />}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Close / Add Button */}
              <button
                type="button"
                onClick={handleClose}
                className="px-4 py-1.5 text-xs font-semibold text-zinc-50 dark:text-zinc-950 bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-50 dark:hover:bg-zinc-200 rounded-lg shadow-sm hover:shadow transition-all cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
