import { Form, Link, redirect, useNavigation } from "react-router";

import { ApiError, api } from "~/lib/api.server";
import { getToken } from "~/lib/session.server";
import type { Route } from "./+types/forgot-password";

export function meta() {
  return [{ title: "Reset your password — Restyle" }];
}

export async function loader({ request }: Route.LoaderArgs) {
  // Signed in already: nothing to reset from here.
  if (await getToken(request)) throw redirect("/");
  return null;
}

export async function action({ request }: Route.ActionArgs) {
  const formData = await request.formData();
  const email = String(formData.get("email") ?? "");

  try {
    await api.forgotPassword(email);
  } catch (error) {
    // The confirmation must read the same whether or not the address has an
    // account, so an API failure falls through to it rather than surfacing.
    // Anything that is not an ApiError (a thrown redirect, say) still bubbles.
    if (!(error instanceof ApiError)) throw error;
  }

  return { ok: true as const };
}

const field =
  "mt-1 w-full border-b border-ink/15 bg-transparent py-2 outline-none focus:border-ink/40";

export default function ForgotPassword({ actionData }: Route.ComponentProps) {
  const navigation = useNavigation();
  const submitting = navigation.formAction === "/forgot-password";

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6">
      <h1 className="font-display text-4xl">Restyle</h1>

      {actionData?.ok ? (
        <>
          <p className="mt-4 text-sm text-ink/70" role="status">
            If an account exists for that address, a reset link is on its way.
            It expires in an hour.
          </p>
          <Link to="/login" className="mt-6 text-sm text-ink/60 underline">
            Back to sign in
          </Link>
        </>
      ) : (
        <>
          <p className="mt-2 text-sm text-ink/60">
            Enter your email and we'll send a link to set a new password.
          </p>

          <Form method="post" className="mt-8 space-y-4">
            <label className="block">
              <span className="text-sm text-ink/60">Email</span>
              <input
                type="email"
                name="email"
                autoComplete="username"
                required
                autoFocus
                className={field}
              />
            </label>

            <button
              type="submit"
              disabled={submitting}
              className="w-full border border-ink/15 py-2 text-sm transition-colors hover:bg-ink/5 disabled:opacity-50"
            >
              {submitting ? "Sending…" : "Send reset link"}
            </button>
          </Form>

          <Link to="/login" className="mt-6 text-sm text-ink/60 underline">
            Remembered it? Sign in
          </Link>
        </>
      )}
    </main>
  );
}
