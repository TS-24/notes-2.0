import {
  isRouteErrorResponse,
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
  useRouteLoaderData,
} from "react-router";

import type { Route } from "./+types/root";
import "./app.css";
import { TooltipProvider } from "./components/ui/tooltip";
import { getTheme } from "./lib/theme.server";
import { themeAttributes } from "./lib/themes";

/**
 * The palette is resolved here and nowhere else, because `<html>` is rendered
 * here and nowhere else. Reading it from the cookie on the server means the
 * markup leaves with the right theme already on it — no inline script blocking
 * the head, no first paint in the wrong colours.
 */
export async function loader({ request }: Route.LoaderArgs) {
  return { theme: await getTheme(request) };
}

// Fonts are bundled from @fontsource-variable, so there is nothing to preconnect to.
export const links: Route.LinksFunction = () => [];

export function Layout({ children }: { children: React.ReactNode }) {
  // Not `useLoaderData`: this component also wraps the error boundary, and there
  // the root loader never ran. `themeAttributes` takes the miss and defaults.
  const data = useRouteLoaderData<typeof loader>("root");

  return (
    <html lang="en" {...themeAttributes(data?.theme)}>
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>


      {/* No sidebar, no nav bar — DESIGN.md §9. The route owns the whole page. */}
      <body className="min-h-screen bg-paper text-ink antialiased">
        <TooltipProvider>{children}</TooltipProvider>

        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

export default function App() {
  return <Outlet />;
}

export function ErrorBoundary({ error }: Route.ErrorBoundaryProps) {
  let message = "Oops!";
  let details = "An unexpected error occurred.";
  let stack: string | undefined;

  if (isRouteErrorResponse(error)) {
    message = error.status === 404 ? "404" : "Error";
    details =
      error.status === 404
        ? "The requested page could not be found."
        : error.statusText || details;
  } else if (import.meta.env.DEV && error && error instanceof Error) {
    details = error.message;
    stack = error.stack;
  }

  return (
    <main className="pt-16 p-4 container mx-auto">
      <h1>{message}</h1>
      <p>{details}</p>
      {stack && (
        <pre className="w-full p-4 overflow-x-auto">
          <code>{stack}</code>
        </pre>
      )}
    </main>
  );
}
