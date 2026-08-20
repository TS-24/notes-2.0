import { useMemo } from "react";
import type { Route } from "./+types/analytics";
import { api } from "~/lib/api.server";
import { requireToken } from "~/lib/session.server";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetTrigger
} from "~/components/ui/sheet";

export async function loader({ request }: Route.LoaderArgs) {
  const token = await requireToken(request);
  const notes = await api.listNotes(token);
  // The analysis moved into the loader. It used to run in a useEffect against
  // a hardcoded 127.0.0.1, which worked only on the machine hosting the API
  // and could never carry an HttpOnly session cookie.
  const combined = notes.map((n) => n.content ?? "").join("\n\n");
  const analysis = notes.length
    ? (await api.analyzeVocabulary(token, { title: "All Notes", content: combined }))
        .vocabulary_analysis
    : null;
  return { notes, analysis };
}

export default function Analytics({ loaderData }: Route.ComponentProps) {
  const { analysis } = loaderData;

  // Generate randomized scattered pattern for each word
  const wordsWithStyles = useMemo(() => {
    if (!analysis) return [];
    const entries = Object.entries(analysis.definitions);
    
    // sizes: text-sm to text-6xl
    const sizes = [
      "text-sm", "text-base", "text-lg", "text-xl", "text-2xl", 
      "text-3xl", "text-4xl", "text-5xl", "text-6xl"
    ];
    // font weights
    const weights = ["font-light", "font-normal", "font-medium", "font-semibold", "font-bold", "font-extrabold"];
    // Six steps of the one ink ramp. Spelled out as literals rather than built
    // from a template, because Tailwind finds classes by scanning this source.
    const colors = [
      "text-ink/35",
      "text-ink/45",
      "text-ink/60",
      "text-ink/70",
      "text-ink/85",
      "text-ink",
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
        className: `cursor-pointer transition-colors hover:text-accent-ink ${sizeClass} ${weightClass} ${colorClass}`
      };
    });
  }, [analysis]);

  return (
    <main className="flex-1 relative overflow-hidden bg-paper min-h-screen font-sans flex flex-col">
      <div className="absolute top-8 left-8 z-10">
        <h1 className="text-3xl font-bold tracking-tight text-ink">Vocabulary Cloud</h1>
        <p className="text-sm text-ink/60 mt-1">
          Click on any word to view its definition in a sidenote.
        </p>
        
        {/* The analysis arrives with the page now, so there is no loading
            state to show and no fetch of its own to fail. */}
        {analysis?.total_difficult_words === 0 && (
          <p className="mt-4 text-sm text-ink/60">No complex vocabulary found in your notes.</p>
        )}
        {analysis === null && (
          <p className="mt-4 text-sm text-ink/60">Write a note first.</p>
        )}
      </div>

      <div className="flex-1 flex items-center justify-center pt-32 pb-12 px-12 overflow-y-auto">
        <div className="flex flex-wrap items-center justify-center w-full max-w-5xl">
          {wordsWithStyles.map(({ word, definition, style, className }) => (
            <Sheet key={word}>
              {/* Base UI merges props onto `render`; it has no asChild prop. */}
              <SheetTrigger render={<span className={className} style={style} />}>
                {word}
              </SheetTrigger>
              <SheetContent side="right">
                <SheetHeader>
                  <SheetTitle className="capitalize text-3xl mb-4 text-accent-ink">
                    {word}
                  </SheetTitle>
                  <SheetDescription className="text-lg text-ink/85 leading-relaxed">
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
