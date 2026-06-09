export interface ColorOption {
  id: string;
  name: string;
  bg: string;
  border: string;
  dot: string;
}

export const COLORS: ColorOption[] = [
  { id: "slate-50", name: "Slate 50", bg: "bg-slate-50 dark:bg-slate-950/50", border: "border-slate-200 dark:border-slate-800/50", dot: "bg-slate-300 dark:bg-slate-600" },
  { id: "slate-100", name: "Slate 100", bg: "bg-slate-100 dark:bg-slate-900/50", border: "border-slate-300 dark:border-slate-700/50", dot: "bg-slate-400 dark:bg-slate-500" },
  { id: "slate-200", name: "Slate 200", bg: "bg-slate-200 dark:bg-slate-800/50", border: "border-slate-400 dark:border-slate-600/50", dot: "bg-slate-500 dark:bg-slate-400" },
];
