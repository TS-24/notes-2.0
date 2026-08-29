/**
 * @vitest-environment jsdom
 *
 * Per file, so the suite's default node environment is left alone. jsdom is
 * held below 30 for the reason workspace.test.tsx gives.
 *
 * The load-bearing case here is the error line. api.server.ts turns a tokenless
 * 401 into an ApiError rather than a redirect, which is the only reason the
 * login action's `{ error }` ever reaches the page — before that fix a wrong
 * password silently reloaded a blank form.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeAll, expect, test } from "vitest";

import Login from "~/routes/login";
import type { Route } from "./+types/login";

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

beforeAll(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
});

const params = {};

function propsWith(actionData: Route.ComponentProps["actionData"]): Route.ComponentProps {
  return {
    loaderData: null,
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
        id: "routes/login",
        params,
        pathname: "/login",
        data: null,
        loaderData: null,
        handle: undefined,
      },
    ],
  };
}

let cleanup = () => {};
afterEach(() => cleanup());

function mount(props: Route.ComponentProps) {
  const container = document.createElement("div");
  document.body.append(container);
  const router = createMemoryRouter(
    [{ path: "/login", Component: () => <Login {...props} /> }],
    { initialEntries: ["/login"] },
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

test("shows the action's error message", () => {
  const container = mount(propsWith({ error: "Incorrect email or password" }));

  const alert = container.querySelector('[role="alert"]');
  expect(alert?.textContent).toBe("Incorrect email or password");
});

test("no error line when the action has not run", () => {
  const container = mount(propsWith(undefined));

  expect(container.querySelector('[role="alert"]')).toBeNull();
});

test("offers a way to the forgot-password page", () => {
  const container = mount(propsWith(undefined));

  const link = container.querySelector<HTMLAnchorElement>('a[href="/forgot-password"]');
  expect(link).not.toBeNull();
  expect(link?.textContent).toMatch(/forgot password/i);
});
