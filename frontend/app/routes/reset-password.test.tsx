/**
 * @vitest-environment jsdom
 *
 * Per file; jsdom held below 30 for the reason workspace.test.tsx gives.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeAll, expect, test } from "vitest";

import ResetPassword from "~/routes/reset-password";
import type { Route } from "./+types/reset-password";

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

beforeAll(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
});

const params = {};

function props(
  token: string,
  actionData: Route.ComponentProps["actionData"] = undefined,
): Route.ComponentProps {
  const loaderData = { token };
  return {
    loaderData,
    actionData,
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
        id: "routes/reset-password",
        params,
        pathname: "/reset-password",
        data: loaderData,
        loaderData,
        handle: undefined,
      },
    ],
  };
}

let cleanup = () => {};
afterEach(() => cleanup());

function mount(p: Route.ComponentProps) {
  const container = document.createElement("div");
  document.body.append(container);
  const router = createMemoryRouter(
    [{ path: "/reset-password", Component: () => <ResetPassword {...p} /> }],
    { initialEntries: ["/reset-password"] },
  );
  const root = createRoot(container);
  act(() => {
    root.render(<RouterProvider router={router} />);
  });
  cleanup = () => {
    act(() => root.unmount());
    container.remove();
  };
  return container;
}

test("shows the password fields when the link carried a token", () => {
  const container = mount(props("a-real-looking-token"));

  expect(container.querySelectorAll('input[type="password"]').length).toBe(2);
  expect(container.querySelector<HTMLInputElement>('input[name="token"]')?.value).toBe(
    "a-real-looking-token",
  );
});

test("tells the reader to get a new link when the token is missing", () => {
  const container = mount(props(""));

  expect(container.querySelector('input[type="password"]')).toBeNull();
  expect(container.querySelector('[role="alert"]')?.textContent).toMatch(
    /missing its token/i,
  );
  expect(
    container.querySelector<HTMLAnchorElement>('a[href="/forgot-password"]'),
  ).not.toBeNull();
});

test("surfaces the action's error", () => {
  const container = mount(props("tok", { error: "This reset link is invalid or has expired." }));

  expect(container.querySelector('[role="alert"]')?.textContent).toBe(
    "This reset link is invalid or has expired.",
  );
});
