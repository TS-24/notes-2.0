import { useState, useEffect, useMemo } from "react";
import { 
  Sheet, 
  SheetContent, 
  SheetHeader, 
  SheetTitle, 
  SheetDescription, 
  SheetTrigger 
} from "~/components/ui/sheet";

interface VocabularyAnalysis {
  total_difficult_words: number;
  definitions: Record<string, string>;
}

export default function Analytics() {
  const [vocabData, setVocabData] = useState<VocabularyAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchVocabulary() {
      try {
        const storedNotes = localStorage.getItem("notes");
        const notes = storedNotes ? JSON.parse(storedNotes) : [];
        
        if (notes.length === 0) {
          setLoading(false);
          return;
        }

        const combinedText = notes.map((n: any) => n.content).join("\n\n");
        const dummyNote = {
          id: "combined",
          title: "All Notes",
          content: combinedText,
          colorId: "default",
          isPinned: false
        };

        const response = await fetch("http://127.0.0.1:8000/api/analyze/vocabulary", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(dummyNote),
        });

        if (!response.ok) {
          throw new Error("Failed to fetch vocabulary analysis");
        }

        const data = await response.json();
        setVocabData(data.vocabulary_analysis);
      } catch (err: any) {
        setError(err.message || "An error occurred");
      } finally {
        setLoading(false);
      }
    }

    fetchVocabulary();
  }, []);

  // Generate randomized scattered pattern for each word
  const wordsWithStyles = useMemo(() => {
    if (!vocabData) return [];
    const entries = Object.entries(vocabData.definitions);
    
    // sizes: text-sm to text-6xl
    const sizes = [
      "text-sm", "text-base", "text-lg", "text-xl", "text-2xl", 
      "text-3xl", "text-4xl", "text-5xl", "text-6xl"
    ];
    // font weights
    const weights = ["font-light", "font-normal", "font-medium", "font-semibold", "font-bold", "font-extrabold"];
    // text colors (shadcn themed)
    const colors = [
      "text-zinc-400 dark:text-zinc-500", 
      "text-zinc-500 dark:text-zinc-400",
      "text-zinc-600 dark:text-zinc-300",
      "text-zinc-700 dark:text-zinc-200",
      "text-zinc-800 dark:text-zinc-100",
      "text-zinc-900 dark:text-zinc-50"
    ];

    return entries.map(([word, definition]) => {
      const sizeClass = sizes[Math.floor(Math.random() * sizes.length)];
      const weightClass = weights[Math.floor(Math.random() * weights.length)];
      const colorClass = colors[Math.floor(Math.random() * colors.length)];
      
      // Random margin for a scattered mosaic effect
      const margin = `${Math.floor(Math.random() * 20) + 10}px`;

      return {
        word,
        definition,
        style: { margin },
        className: `cursor-pointer transition-colors hover:text-blue-500 ${sizeClass} ${weightClass} ${colorClass}`
      };
    });
  }, [vocabData]);

  return (
    <main className="flex-1 relative overflow-hidden bg-zinc-50 dark:bg-zinc-950 min-h-screen font-sans flex flex-col">
      <div className="absolute top-8 left-8 z-10">
        <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">Vocabulary Cloud</h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
          Click on any word to view its definition in a sidenote.
        </p>
        
        {loading && <p className="mt-4 text-sm text-zinc-500">Analyzing notes...</p>}
        {error && <p className="mt-4 text-sm text-red-500">Error: {error}</p>}
        {!loading && vocabData?.total_difficult_words === 0 && (
          <p className="mt-4 text-sm text-zinc-500">No complex vocabulary found in your notes.</p>
        )}
      </div>

      <div className="flex-1 flex items-center justify-center pt-32 pb-12 px-12 overflow-y-auto">
        <div className="flex flex-wrap items-center justify-center w-full max-w-5xl">
          {wordsWithStyles.map(({ word, definition, style, className }) => (
            <Sheet key={word}>
              <SheetTrigger asChild>
                <span className={className} style={style}>
                  {word}
                </span>
              </SheetTrigger>
              <SheetContent side="right">
                <SheetHeader>
                  <SheetTitle className="capitalize text-3xl mb-4 text-blue-600 dark:text-blue-400">
                    {word}
                  </SheetTitle>
                  <SheetDescription className="text-lg text-zinc-700 dark:text-zinc-300 leading-relaxed">
                    {definition}
                  </SheetDescription>
                </SheetHeader>
              </SheetContent>
            </Sheet>
          ))}
        </div>
      </div>
    </main>
  );
}
