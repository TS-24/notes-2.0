/** @vitest-environment jsdom */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeAll, expect, test } from "vitest";

import Workspace from "~/routes/workspace";
import type { Route } from "./+types/workspace";
import type { Note, User } from "~/lib/types";

/**
 * Switching notes has to give the surface a new element, not a new prop.
 *
 * The surface carries `layoutId={noteLayoutId(note.id)}`, and a layoutId is an
 * identity: Framer registers the element under it and crossfades whenever one
 * element takes an id another is giving up. Changing the id on an element that
 * stays mounted makes it both halves of that crossfade at once — it hands
 * `note-A` to the card reappearing in the grid, so Framer fades it out and
 * projects it into that card's slot, then never restores it because the element
 * never unmounted. The result is an editor left at `opacity: 0`, which is to
 * say a blank page.
 *
 * So the check is on the DOM node rather than on anything visual: jsdom has no
 * layout and Framer's projection is a no-op here, and the point is the identity
 * anyway, not the pixels it would produce.
 */

declare global {
  // React reads this to decide whether act() is allowed at all.
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

beforeAll(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  // jsdom has no ResizeObserver, and the surface measures itself with one.
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

const NOW = "2026-01-01T00:00:00Z";

const note = (id: number, title: string): Note => ({
  id,
  title,
  content: `The text of ${title}.`,
  user_id: 1,
  is_pinned: false,
  created_at: NOW,
  updated_at: NOW,
  words: [],
});

const user: User = { id: 1, username: "reader", email: "reader@example.com" };

const notes = [note(1, "First"), note(2, "Second")];

const loaderData = { notes, user, chats: [] };

/**
 * The route module's props, as the framework would hand them over. Only
 * `loaderData` is read — everything else the component needs comes from router
 * context — but the match tree is spelled out rather than cast away, so a
 * change to the route's shape shows up here as a type error.
 */
const params = {};
const props: Route.ComponentProps = {
  loaderData,
  params,
  matches: [
    {
      id: "root",
      params,
      pathname: "/",
      data: undefined,
      loaderData: undefined,
      handle: undefined,
    },
    {
      id: "routes/workspace",
      params,
      pathname: "/notes",
      data: loaderData,
      loaderData,
      handle: undefined,
    },
  ],
};

let cleanup = () => {};
afterEach(() => cleanup());

function mount() {
  const container = document.createElement("div");
  document.body.append(container);
  const router = createMemoryRouter(
    [
      {
        path: "/notes",
        // The surface touches the note it opens through this action.
        action: () => ({ ok: true }),
        Component: () => <Workspace {...props} />,
      },
    ],
    { initialEntries: ["/notes?open=1"] },
  );
  const root = createRoot(container);
  act(() => {
    root.render(<RouterProvider router={router} />);
  });
  cleanup = () => {
    act(() => root.unmount());
    container.remove();
  };
  return {
    router,
    surface: () => container.querySelector("[role=dialog]"),
    body: () =>
      container.querySelector<HTMLTextAreaElement>('textarea[aria-label="Note text"]'),
  };
}

test("opens a different note on a different element", async () => {
  const { router, surface } = mount();
  const first = surface();
  expect(first).not.toBeNull();

  await act(async () => {
    await router.navigate("/notes?open=2");
  });

  expect(surface()).not.toBe(first);
});

test("shows the newly opened note's text", async () => {
  const { router, body } = mount();
  expect(body()?.value).toBe("The text of First.");

  await act(async () => {
    await router.navigate("/notes?open=2");
  });

  expect(body()?.value).toBe("The text of Second.");
});
