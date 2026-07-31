import { useEffect, useRef } from "react";
import {
  Outlet,
  useFetcher,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router";
import type { Route } from "./+types/workspace";
import NoteSurface from "~/workspace/note-surface";
import { api } from "~/lib/api.server";

/**
 * The workspace shell.
 *
 * This is a layout route, which is the whole point: React Router keeps a parent
 * mounted while its children change, so the note surface survives navigation
 * between the landing page and the grid. Nothing about the note is torn down
 * and rebuilt — only the child below it comes and goes.
 */
export async function loader() {
  // Loaded once here and read by both children, so there is a single list and
  // a single revalidation after any mutation.
  return { notes: await api.listNotes() };
}

export default function Workspace({ loaderData }: Route.ComponentProps) {
  const { notes } = loaderData;
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const touchFetcher = useFetcher();

  const onLanding = location.pathname === "/";
  const openId = Number(searchParams.get("open"));

  // Landing shows whatever note was touched last; the grid shows whichever the
  // URL points at. The URL is the single source of truth for "open".
  const focused = onLanding
    ? (notes[0] ?? null)
    : (notes.find(n => n.id === openId) ?? null);

  // Opening a note counts as an update, so it becomes "where you left off".
  // Guarded by id so revalidation does not re-touch in a loop.
  const touched = useRef<number | null>(null);
  useEffect(() => {
    if (onLanding || !focused || touched.current === focused.id) return;
    touched.current = focused.id;
    touchFetcher.submit(
      { intent: "touch", id: String(focused.id) },
      { method: "post", action: "/notes" },
    );
  }, [onLanding, focused, touchFetcher]);

  useEffect(() => {
    if (onLanding) touched.current = null;
  }, [onLanding]);

  return (
    <main
      className={`min-h-screen bg-paper text-ink px-8 md:px-16 ${
        onLanding
          ? "flex flex-col justify-center py-12"
          : "flex flex-col justify-start py-12 space-y-16"
      }`}
    >
      {/*
        No exit link: double clicking the note toggles between its own page and
        the library, in both directions, so the gesture is the navigation.
      */}
      {focused && (
        <NoteSurface
          note={focused}
          mode={onLanding ? "page" : "boxed"}
          onOpen={() => navigate(`/notes?open=${focused.id}`)}
          onClose={() => navigate("/notes", { replace: true })}
          onReturn={() => navigate("/")}
        />
      )}

      <Outlet />
    </main>
  );
}
