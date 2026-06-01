export interface ColorOption {
  id: string;
  name: string;
  bg: string;
  border: string;
  dot: string;
}

export const COLORS: ColorOption[] = [
  { id: "default", name: "Default", bg: "bg-white dark:bg-zinc-900", border: "border-zinc-200 dark:border-zinc-800", dot: "bg-zinc-200 dark:bg-zinc-700" },
  { id: "rose", name: "Coral", bg: "bg-rose-50/75 dark:bg-rose-950/20", border: "border-rose-200 dark:border-rose-900/40", dot: "bg-rose-400 dark:bg-rose-600" },
  { id: "orange", name: "Peach", bg: "bg-orange-50/75 dark:bg-orange-950/20", border: "border-orange-200 dark:border-orange-900/40", dot: "bg-orange-400 dark:bg-orange-600" },
  { id: "amber", name: "Sand", bg: "bg-amber-50/75 dark:bg-amber-950/20", border: "border-amber-200 dark:border-amber-900/40", dot: "bg-amber-400 dark:bg-amber-600" },
  { id: "emerald", name: "Mint", bg: "bg-emerald-50/75 dark:bg-emerald-950/20", border: "border-emerald-200 dark:border-emerald-900/40", dot: "bg-emerald-400 dark:bg-emerald-600" },
  { id: "teal", name: "Sage", bg: "bg-teal-50/75 dark:bg-teal-950/20", border: "border-teal-200 dark:border-teal-900/40", dot: "bg-teal-400 dark:bg-teal-600" },
  { id: "sky", name: "Fog", bg: "bg-sky-50/75 dark:bg-sky-950/20", border: "border-sky-200 dark:border-sky-900/40", dot: "bg-sky-400 dark:bg-sky-600" },
  { id: "indigo", name: "Dusk", bg: "bg-indigo-50/75 dark:bg-indigo-950/20", border: "border-indigo-200 dark:border-indigo-900/40", dot: "bg-indigo-400 dark:bg-indigo-600" },
  { id: "purple", name: "Blossom", bg: "bg-purple-50/75 dark:bg-purple-950/20", border: "border-purple-200 dark:border-purple-900/40", dot: "bg-purple-400 dark:bg-purple-600" },
];
