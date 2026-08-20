/**
 * @vitest-environment jsdom
 *
 * Per file, for the reason workspace.test.tsx gives — and jsdom is pinned below
 * 30 there for a Node 20 reason that applies to every file that asks for it.
 *
 * What is pinned here is the one thing the dialog exists to do. Adding a key is
 * a credential leaving the machine, so it is not a field you tab past: the
 * dialog holds the reader there until the provider has answered, and if the
 * answer is no it says so and stays open. A form that navigated away on submit
 * could not do either.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeAll, expect, test } from "vitest";

import Menu from "~/routes/menu";
import type { Route } from "./+types/menu";
import type { ProviderSettings, User } from "~/lib/types";
import { DEFAULT_THEME } from "~/lib/themes";

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

beforeAll(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  // base-ui measures the popup it portals into the body.
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

const user: User = { id: 1, username: "reader", email: "reader@example.com" };

const provider: ProviderSettings = {
  available: [
    { id: "anthropic", label: "Anthropic", default_model: "claude-opus-5" },
    { id: "openrouter", label: "OpenRouter", default_model: "openai/gpt-5.1" },
  ],
  configured: [],
  active: null,
};

const REFUSAL = "That key would not answer. 401 Incorrect API key provided";

let cleanup = () => {};
afterEach(() => cleanup());

function mount(answer: unknown) {
  const container = document.createElement("div");
  document.body.append(container);

  const loaderData = { user, provider, theme: DEFAULT_THEME };
  const params = {};
  const props: Route.ComponentProps = {
    loaderData,
    params,
    matches: [
      {
        id: "root",
        params,
        pathname: "/",
        data: { theme: DEFAULT_THEME },
        loaderData: { theme: DEFAULT_THEME },
        handle: undefined,
      },
      {
        id: "routes/menu",
        params,
        pathname: "/settings",
        data: loaderData,
        loaderData,
        handle: undefined,
      },
    ],
  };

  const router = createMemoryRouter(
    [{ path: "/settings", action: () => answer, Component: () => <Menu {...props} /> }],
    { initialEntries: ["/settings"] },
  );
  const root = createRoot(container);
  act(() => {
    root.render(<RouterProvider router={router} />);
  });
  cleanup = () => {
    act(() => root.unmount());
    container.remove();
  };

  // The dialog is portalled, so it is not inside `container` — everything below
  // looks for it on the body.
  return {
    open: () => container.querySelector<HTMLButtonElement>('[data-add-key]')!,
    dialog: () => document.body.querySelector("[data-slot=dialog-content]"),
    key: () => document.body.querySelector<HTMLInputElement>('input[name="api_key"]'),
    form: () => document.body.querySelector<HTMLFormElement>("[data-key-form]"),
    said: () => document.body.querySelector("[data-key-status]")?.textContent ?? "",
  };
}

async function submit(surface: ReturnType<typeof mount>, key: string) {
  await act(async () => {
    surface.open().click();
  });

  const field = surface.key()!;
  field.value = key;
  field.dispatchEvent(new Event("input", { bubbles: true }));

  await act(async () => {
    surface.form()!.requestSubmit();
  });
}

test("the dialog opens on its own rather than as a field on the page", async () => {
  const surface = mount({ ok: true });
  expect(surface.dialog()).toBeNull();

  await act(async () => {
    surface.open().click();
  });

  expect(surface.dialog()).not.toBeNull();
});

test("a key the provider refuses keeps the dialog open", async () => {
  const surface = mount({ ok: false, message: REFUSAL });
  await submit(surface, "not-a-real-key-0000");

  expect(surface.dialog()).not.toBeNull();
});

test("a key the provider refuses says what the provider said", async () => {
  const surface = mount({ ok: false, message: REFUSAL });
  await submit(surface, "not-a-real-key-0000");

  // The provider's own words: they are what tells a wrong character apart from
  // a spent quota, and they are the only clue the reader gets.
  expect(surface.said()).toContain("Incorrect API key");
});

test("a key that works reports what it can reach", async () => {
  const surface = mount({ ok: true, message: "Connected. 42 models available." });
  await submit(surface, "a-key-that-works-1234");

  expect(surface.said()).toContain("42 models");
});
