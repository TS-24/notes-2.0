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
import type { AdminInvite, Invite, ProviderSettings, User } from "~/lib/types";
import { DEFAULT_THEME } from "~/lib/themes";
import { ALIGNMENTS, DEFAULT_ALIGNMENT } from "~/lib/alignment";

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

const user: User = {
  id: 1,
  username: "reader",
  email: "reader@example.com",
  is_superuser: false,
};

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

/**
 * What the loader hands the page. `everyone` is null for an ordinary account
 * and an object for the superuser, so one field carries both "may you see the
 * whole system" and "here it is" — two nullable arrays could disagree.
 */
type LoaderData = {
  user: User;
  provider: ProviderSettings;
  theme: typeof DEFAULT_THEME;
  alignment: typeof DEFAULT_ALIGNMENT;
  invites: Invite[];
  everyone: { invites: AdminInvite[]; users: User[] } | null;
};

function mount(answer: unknown, overrides: Partial<LoaderData> = {}) {
  const container = document.createElement("div");
  document.body.append(container);

  const loaderData: LoaderData = {
    user,
    provider,
    theme: DEFAULT_THEME,
    alignment: DEFAULT_ALIGNMENT,
    invites: [],
    everyone: null,
    ...overrides,
  };
  const params = {};
  const props: Route.ComponentProps = {
    loaderData,
    params,
    matches: [
      {
        id: "root",
        params,
        pathname: "/",
        data: { theme: DEFAULT_THEME, alignment: DEFAULT_ALIGNMENT },
        loaderData: { theme: DEFAULT_THEME, alignment: DEFAULT_ALIGNMENT },
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
    align: () => container.querySelector<HTMLSelectElement>('select[name="align"]'),
    inviteEmail: () => container.querySelector<HTMLInputElement>('input[name="email"]'),
    inviteForm: () => container.querySelector<HTMLFormElement>("[data-invite-form]"),
    inviteSaid: () =>
      container.querySelector("[data-invite-status]")?.textContent ?? "",
    codes: () =>
      [...container.querySelectorAll("[data-invite-code]")].map(
        node => node.textContent ?? "",
      ),
    everyInvite: () => container.querySelector("[data-every-invite]"),
    everyAccount: () => container.querySelector("[data-every-account]"),
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

/*
  The alignment picker. jsdom has no stylesheet, so nothing here can say which
  way the words actually run — `alignment.test.ts` checks the CSS backing it,
  and the look is a thing only a browser can settle. What is pinned here is
  that the choice is offered at all, that it offers the three the app ships,
  and that it starts on the one the reader is already reading in.
*/
test("the alignment is a setting rather than a constant", () => {
  const surface = mount({ ok: true });

  expect(surface.align()).not.toBeNull();
});

test("it offers exactly the alignments the app ships", () => {
  const surface = mount({ ok: true });

  const offered = [...surface.align()!.options].map((option) => option.value);
  expect(offered).toEqual(ALIGNMENTS.map((alignment) => alignment.id));
});

test("it opens on the alignment already in force", () => {
  const surface = mount({ ok: true });

  expect(surface.align()!.value).toBe(DEFAULT_ALIGNMENT.id);
});

test("changing it posts, so the cookie is what makes the choice stick", async () => {
  const surface = mount({ ok: true });
  const select = surface.align()!;

  await act(async () => {
    select.value = "right";
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });

  // A preference that only ran `applyAlignment` would be gone on reload.
  expect(new FormData(select.form!).get("intent")).toBe("align");
});

/*
  Invites.

  What is worth pinning is not that the form posts — it is that the code stays
  readable afterwards. Someone issues a code in order to send it to a person,
  and between issuing it and getting to their mail client the page may well have
  been re-rendered. A code shown once and then gone is a code reissued.
*/

const invite: Invite = {
  id: 1,
  code: "K7QN4M2XBQ9F",
  invited_email: "friend@example.com",
  created_at: "2026-08-27T10:00:00Z",
  used_at: null,
};

test("an issued code stays readable in the list, next to who it is for", () => {
  const surface = mount({ ok: true }, { invites: [invite] });

  expect(surface.codes()).toContain("K7QN4M2XBQ9F");
  expect(surface.inviteForm()).not.toBeNull();
  expect(document.body.textContent).toContain("friend@example.com");
});

test("a spent code says so, because it is no longer worth sending", () => {
  const surface = mount(
    { ok: true },
    { invites: [{ ...invite, used_at: "2026-08-28T09:00:00Z" }] },
  );

  expect(surface.everyAccount()).toBeNull();
  expect(document.body.textContent).toContain("Used");
});

test("a refusal shows the backend's own words", async () => {
  const surface = mount({ ok: false, message: "That email already has an account" });

  const field = surface.inviteEmail()!;
  field.value = "taken@example.com";
  field.dispatchEvent(new Event("input", { bubbles: true }));
  await act(async () => {
    surface.inviteForm()!.requestSubmit();
  });

  // The one thing that tells "already registered" from "not an email" apart.
  expect(surface.inviteSaid()).toContain("already has an account");
});

test("an ordinary account is shown neither listing", () => {
  const surface = mount({ ok: true }, { invites: [invite] });

  expect(surface.everyInvite()).toBeNull();
  expect(surface.everyAccount()).toBeNull();
});

test("the superuser is shown both, with who issued what", () => {
  const surface = mount(
    { ok: true },
    {
      user: { ...user, is_superuser: true },
      everyone: {
        invites: [
          {
            ...invite,
            issued_by_email: "someone.else@example.com",
            used_by_email: null,
          },
        ],
        users: [
          user,
          { id: 2, username: "other", email: "other@example.com", is_superuser: false },
        ],
      },
    },
  );

  expect(surface.everyInvite()).not.toBeNull();
  expect(surface.everyInvite()!.textContent).toContain("someone.else@example.com");
  expect(surface.everyAccount()!.textContent).toContain("other@example.com");
});
