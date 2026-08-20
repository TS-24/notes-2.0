import { useEffect, useRef } from "react";
import {
  Outlet,
  useFetcher,
  useLocation,
  useNavigate,
  useSearchParams,
} from "react-router";
import type { Route } from "./+types/workspace";
import AccountBubble from "~/notes/account-bubble";
import NoteSurface from "~/workspace/note-surface";
import { api } from "~/lib/api.server";
import { requireToken } from "~/lib/session.server";

/**
 * The workspace shell.
 *
 * This is a layout route, which is the whole point: React Router keeps a parent
 * mounted while its children change, so the note surface survives navigation
 * between the landing page and the grid. The note you are in is not torn down
 * and rebuilt on that trip — only the child below it comes and goes.
 */
export async function loader({ request }: Route.LoaderArgs) {
  // requireToken redirects to /login when there is no session, so everything
  // under this layout is behind authentication by virtue of being under it.
  const token = await requireToken(request);
  // Loaded once here and read by both children, so there is a single list and
  // a single revalidation after any mutation.
  // The user comes back with the notes rather than from a loader of its own.
  // Only /notes draws the account bubble, but a loader on that child would
  // refetch the account after every note edit, and this one is already running
  // and already revalidating.
  // Chats come from the same loader as the notes so the library has one fetch
  // and one revalidation for everything it shows.
  const [notes, user, chats] = await Promise.all([
    api.listNotes(token),
    api.getCurrentUser(token),
    api.listChats(token),
  ]);

  // An account with no notes has nothing for the surface below to render, and
  // this page is the whole interface — no nav bar, no sidebar — so it would be
  // a genuinely blank screen with no way out. A new account gets an empty note
  // instead, which is also the truthful answer to "what were you last writing".
  //
  // A write in a loader is not free: two parallel requests against a brand-new
  // account could both see zero and create one each. It happens once per
  // account at most, the surplus is an empty untitled note, and the reader can
  // delete it. That is a better failure than the blank page it replaces.
  if (notes.length === 0) {
    return {
      notes: [await api.createNote(token, { title: "Untitled", content: "" })],
      user,
      chats,
    };
  }

  return { notes, user, chats };
}

export default function Workspace({ loaderData }: Route.ComponentProps) {
  const { notes, user } = loaderData;
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
        The library gets a way to the account; the landing page does not. While
        you are in the note, the note is the only thing on screen — DESIGN.md
        §9 rule 8. Rendered here rather than by the notes route because only the
        layout can place it above the note surface, and it has to sit above
        everything to reserve space rather than float over it. No negative
        margin to close the gap below: that pulls the grid back up underneath
        it, which is the overlap this arrangement exists to avoid.
      */}
      {!onLanding && (
        <div className="flex justify-end">
          <AccountBubble user={user} />
        </div>
      )}

      {/*
        No exit link: double clicking the note toggles between its own page and
        the library, in both directions, so the gesture is the navigation.
      */}
      {focused && (
        <NoteSurface
          /*
            Keyed by the note, so switching notes mounts a fresh surface rather
            than re-pointing this one. `layoutId` is an identity to Framer, and
            moving one from a live element to another element in the same commit
            makes this element the departing half of that crossfade: it was
            faded to nothing and projected into the card reappearing in the
            grid, and — never having unmounted — it stayed there. The page went
            blank with the note still in it.

            It does not cost the continuity this layout exists for. The trip
            between the landing page and the library keeps the same note, so the
            key holds and the surface is the same element throughout; only a
            change of note, which is a change of subject, remounts.
          */
          key={focused.id}
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
