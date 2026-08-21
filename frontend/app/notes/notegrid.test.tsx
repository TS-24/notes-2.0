/**
 * @vitest-environment jsdom
 *
 * jsdom per file, matching workspace.test.tsx — the suite's default is node.
 *
 * These pin the *gestures*, which is all jsdom can speak to: it has no layout,
 * so nothing here says anything about where a card sits or how it animates.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeAll, expect, test } from "vitest";

import Notegrid from "~/notes/notegrid";
import type { Chat, Note } from "~/lib/types";

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

beforeAll(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
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

const chat = (id: number, title: string): Chat => ({
  id,
  user_id: 1,
  title,
  messages: [],
  summary: null,
  created_at: NOW,
  updated_at: NOW,
});

let cleanup = () => {};
afterEach(() => cleanup());

function mount(notes: Note[], chats: Chat[]) {
  const container = document.createElement("div");
  document.body.append(container);
  const router = createMemoryRouter(
    [
      {
        path: "/notes",
        action: () => ({ ok: true }),
        Component: () => <Notegrid notes={notes} chats={chats} />,
      },
      { path: "/chats/:chatId", Component: () => <div /> },
    ],
    { initialEntries: ["/notes"] },
  );
  const root = createRoot(container);
  act(() => {
    root.render(<RouterProvider router={router} />);
  });
  cleanup = () => {
    act(() => root.unmount());
    container.remove();
  };
  return { router, container };
}

const click = (el: Element, detail: number) =>
  el.dispatchEvent(new MouseEvent("click", { bubbles: true, detail }));

/**
 * A card renders `cursor: pointer` but only carried `onDoubleClick`, so a
 * single click — what the cursor promises — did nothing at all.
 */
test("a single click on a note card opens it", async () => {
  const { router, container } = mount([note(7, "First")], []);
  const card = container.querySelector("[data-note-card]");
  expect(card).not.toBeNull();

  await act(async () => {
    click(card!, 1);
  });

  expect(router.state.location.pathname).toBe("/notes");
  expect(router.state.location.search).toBe("?open=7");
});

/**
 * A chat opens on the same gesture a note does — one click. The destination
 * differs (a conversation gets its own page, a note opens in the library) but
 * the hand does the same thing to both, which is the point.
 */
test("a single click on a chat card opens the full chat page", async () => {
  const { router, container } = mount([], [chat(4, "A conversation")]);
  const card = container.querySelector("[data-note-card]");
  expect(card).not.toBeNull();

  await act(async () => {
    click(card!, 1);
  });

  expect(router.state.location.pathname).toBe("/chats/4");
});

/**
 * A summarised conversation is shown as the note it produced, not as a second
 * card saying the same thing. Chats summarised before that existed have no note
 * to show instead, so they keep their card — hence the test is on `note_id`,
 * not on `summary`.
 */
test("a chat that became a note leaves the grid", () => {
  const became = {
    ...chat(4, "Finished"),
    summary: {
      general: "g",
      topics: [],
      questions: "q",
      answers: "a",
      summarized_at: NOW,
      note_id: 12,
    },
  } as Chat;
  const older = {
    ...chat(5, "Older"),
    summary: {
      general: "g",
      topics: [],
      questions: "q",
      answers: "a",
      summarized_at: NOW,
      note_id: null,
    },
  } as Chat;

  const { container } = mount([], [became, older]);
  const titles = [...container.querySelectorAll("h3")].map(h => h.textContent);

  expect(titles).not.toContain("Finished");
  expect(titles).toContain("Older");
});
