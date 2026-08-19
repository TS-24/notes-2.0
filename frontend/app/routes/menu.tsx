import { Form, Link } from "react-router";

import { api } from "~/lib/api.server";
import { requireToken } from "~/lib/session.server";
import type { Route } from "./+types/menu";

export function meta() {
  return [{ title: "Account — Restyle" }];
}

export async function loader({ request }: Route.LoaderArgs) {
  const token = await requireToken(request);
  return { user: await api.getCurrentUser(token) };
}

export default function Menu({ loaderData }: Route.ComponentProps) {
  const { user } = loaderData;

  return (
    <main className="mx-auto max-w-prose space-y-8 p-8">
      {/* The exit sits at the head of the column, at Meta size — DESIGN.md's
          form for leaving a view, in place of a back button or a rail. */}
      <Link to="/notes" className="block text-sm tracking-wide text-ink/50 hover:text-ink">
        ← Your notes
      </Link>

      <h1 className="font-display text-3xl">Account</h1>

      <section className="space-y-1">
        <h2 className="text-sm text-ink/60">Signed in as</h2>
        <p className="text-lg">{user.username}</p>
        <p className="text-sm text-ink/60">{user.email}</p>
      </section>

      {/* A form rather than a link: signing out is a POST so that a prefetch
          or a crawler cannot end the session. */}
      <Form method="post" action="/logout">
        <button
          type="submit"
          className="border border-ink/15 px-4 py-2 text-sm transition-colors hover:bg-ink/5"
        >
          Sign out
        </button>
      </Form>

    </main>
  );
}
