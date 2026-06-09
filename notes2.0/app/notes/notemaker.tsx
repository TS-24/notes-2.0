import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Pin, Palette, Check, Plus } from "lucide-react";
import { COLORS } from "~/lib/colors";

interface NoteMakerProps {
  onAddNote: (note: { title: string; content: string; colorId: string; isPinned: boolean; createdAt: string }) => void;
}

export default function NoteMaker({ onAddNote }: NoteMakerProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");

  const containerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLTextAreaElement>(null);

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
  }, [isExpanded, title, content]);

  const handleClose = () => {
    if (title.trim() || content.trim()) {
      const randomColor = COLORS[Math.floor(Math.random() * COLORS.length)].id;
      onAddNote({
        title: title.trim(),
        content: content.trim(),
        colorId: randomColor,
        isPinned: false,
        createdAt: new Date().toISOString(),
      });
    }
    // Reset state
    setTitle("");
    setContent("");
    setIsExpanded(false);
  };

  return (
    <div className="flex justify-center w-full px-4 mb-8">
      <motion.div
        layout
        transition={{ type: "spring", bounce: 0, duration: 0.3 }}
        ref={containerRef}
        className={`w-full max-w-2xl border shadow-sm hover:shadow-md overflow-hidden ${
          isExpanded 
            ? "bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 p-5 rounded-3xl" 
            : "bg-white dark:bg-zinc-900 border-zinc-200 dark:border-zinc-800 py-3 px-5 flex items-center gap-3 cursor-pointer rounded-full"
        }`}
        onClick={() => !isExpanded && setIsExpanded(true)}
      >
        <AnimatePresence mode="popLayout" initial={false}>
          {!isExpanded ? (
            <motion.div 
              key="collapsed"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="flex items-center justify-between w-full pl-2"
            >
              <span className="text-sm text-zinc-500 dark:text-zinc-400">
                Start typing a note...
              </span>
              <div className="p-2.5 rounded-full text-white bg-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 hover:opacity-90 shadow-sm">
                <Plus className="size-4" />
              </div>
            </motion.div>
          ) : (
            <motion.div 
              key="expanded"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="flex flex-col gap-3 w-full"
            >
              {/* Title Bar */}
              <div className="flex items-center justify-between gap-3">
                <input
                  type="text"
                  placeholder="Title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-transparent border-none outline-none font-semibold text-base text-zinc-900 dark:text-zinc-50 placeholder-zinc-400 dark:placeholder-zinc-500 px-1"
                  autoFocus
                />
              </div>

              {/* Content Field */}
              <textarea
                ref={contentRef}
                placeholder="What's on your mind?"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleClose();
                  }
                }}
                rows={2}
                className="w-full bg-transparent border-none outline-none resize-none text-sm text-zinc-700 dark:text-zinc-300 placeholder-zinc-400 dark:placeholder-zinc-500 leading-relaxed min-h-[48px] px-1"
              />

              {/* Bottom Controls */}
              <div className="flex items-center justify-end mt-2 pt-3 border-t border-zinc-100 dark:border-zinc-800">
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  type="button"
                  onClick={handleClose}
                  className="px-6 py-2 text-sm font-medium text-white bg-zinc-900 dark:bg-zinc-50 dark:text-zinc-900 rounded-full shadow-sm cursor-pointer"
                >
                  Save Note
                </motion.button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}
