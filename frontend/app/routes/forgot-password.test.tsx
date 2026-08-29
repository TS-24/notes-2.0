/**
 * @vitest-environment jsdom
 *
 * Per file; jsdom held below 30 for the reason workspace.test.tsx gives.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, RouterProvider } from "react-router";
import { afterEach, beforeAll, expect, test } from "vitest";

import ForgotPassword from "~/routes/forgot-password";
import type { Route } from "./+types/forgot-password";

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

beforeAll(() => {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
});

const params = {};

function propsWith(
  actionData: Route.ComponentProps["actionData"],
): Route.ComponentProps {
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
        id: "routes/forgot-password",
        params,
        pathname: "/forgot-password",
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
    [{ path: "/forgot-password", Component: () => <ForgotPassword {...props} /> }],
    { initialEntries: ["/forgot-password"] },
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

test("asks for an email before the action has run", () => {
  const container = mount(propsWith(undefined));

  expect(container.querySelector('input[type="email"]')).not.toBeNull();
  expect(container.querySelector('[role="status"]')).toBeNull();
});

test("swaps the form for a confirmation once sent", () => {
  const container = mount(propsWith({ ok: true }));

  expect(container.querySelector('input[type="email"]')).toBeNull();
  expect(container.querySelector('[role="status"]')?.textContent).toMatch(
    /reset link is on its way/i,
  );
});
