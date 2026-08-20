import { Form, Link, useNavigation } from "react-router";

import { api, ApiError } from "~/lib/api.server";
import { requireToken } from "~/lib/session.server";
import type { Route } from "./+types/menu";

export function meta() {
  return [{ title: "Account — Restyle" }];
}

export async function loader({ request }: Route.LoaderArgs) {
  const token = await requireToken(request);
  const [user, provider] = await Promise.all([
    api.getCurrentUser(token),
    api.getProviderSettings(token),
  ]);
  return { user, provider };
}

/**
 * Saving and forgetting the reader's provider key.
 *
 * The key arrives in a form post, goes straight to the API client, and is never
 * put anywhere else — not in the loader's response, not in a redirect, not in a
 * log line. The backend does not send it back either, so there is no path by
 * which it can reach the page again.
 */
export async function action({ request }: Route.ActionArgs) {
  const token = await requireToken(request);
  const formData = await request.formData();

  try {
    if (formData.get("intent") === "forget") {
      await api.forgetProviderSettings(token);
      return { ok: true as const, message: "Key forgotten." };
    }

    const model = String(formData.get("model") ?? "").trim();
    await api.saveProviderSettings(token, {
      provider: String(formData.get("provider") ?? ""),
      api_key: String(formData.get("api_key") ?? ""),
      // Blank means "the provider's own default", which the backend resolves.
      model: model || null,
    });
    return { ok: true as const, message: "Key saved." };
  } catch (error) {
    if (error instanceof ApiError) return { ok: false as const, message: error.detail };
    throw error;
  }
}

export default function Menu({ loaderData, actionData }: Route.ComponentProps) {
  const { user, provider } = loaderData;
  const navigation = useNavigation();
  const saving = navigation.formData?.get("intent") !== "forget" && navigation.state !== "idle";

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

      <section className="space-y-4 border-t border-hairline pt-8">
        <div className="space-y-1">
          <h2 className="font-display text-xl">AI provider</h2>
          <p className="text-sm text-ink/60">
            Chats run on your own account with the provider you choose. The key
            is stored encrypted and is never shown again after you save it.
          </p>
        </div>

        {provider.configured ? (
          <p className="text-sm text-ink/60">
            Using <span className="text-ink">{provider.provider}</span> ·{" "}
            <span className="text-ink">{provider.model}</span> · key ending{" "}
            <span className="text-ink">····{provider.key_hint}</span>
          </p>
        ) : (
          <p className="text-sm italic text-ink/60">
            No key on file. Chats will ask you for one.
          </p>
        )}

        {/*
          A real Form and a route action rather than the fetcher pattern used
          inside the workspace: this is a navigation, and — like login.tsx — it
          has to work before the page has hydrated.
        */}
        <Form method="post" className="space-y-4" autoComplete="off">
          <label className="block">
            <span className="text-sm text-ink/60">Provider</span>
            <select
              name="provider"
              defaultValue={provider.provider ?? provider.available[0]?.id}
              className="mt-1 w-full border-b border-ink/15 bg-transparent py-2 outline-none focus:border-ink/40"
            >
              {provider.available.map(option => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm text-ink/60">API key</span>
            <input
              type="password"
              name="api_key"
              required
              // Not a password the browser should remember or offer to fill: it
              // belongs to a third party, not to this site's account.
              autoComplete="off"
              spellCheck={false}
              placeholder={provider.configured ? "Enter a new key to replace it" : ""}
              className="mt-1 w-full border-b border-ink/15 bg-transparent py-2 outline-none focus:border-ink/40"
            />
          </label>

          <label className="block">
            <span className="text-sm text-ink/60">
              Model{" "}
              <span className="italic">
                (optional — blank uses the provider's default)
              </span>
            </span>
            <input
              type="text"
              name="model"
              defaultValue={provider.model ?? ""}
              spellCheck={false}
              placeholder={provider.available[0]?.default_model}
              className="mt-1 w-full border-b border-ink/15 bg-transparent py-2 outline-none focus:border-ink/40"
            />
          </label>

          {actionData ? (
            <p
              role="status"
              className={`text-sm ${actionData.ok ? "text-ink/60" : "text-rose-700"}`}
            >
              {actionData.message}
            </p>
          ) : null}

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={saving}
              className="border border-ink/15 px-4 py-2 text-sm transition-colors hover:bg-ink/5 disabled:opacity-50"
            >
              {saving ? "Saving…" : "Save key"}
            </button>

            {provider.configured && (
              <button
                type="submit"
                name="intent"
                value="forget"
                // The key field is `required`, and forgetting must not be
                // blocked by an empty one — it is the opposite request.
                formNoValidate
                className="text-sm text-ink/50 transition-colors hover:text-ink"
              >
                Forget it
              </button>
            )}
          </div>
        </Form>
      </section>

      {/* A form rather than a link: signing out is a POST so that a prefetch
          or a crawler cannot end the session. */}
      <Form method="post" action="/logout" className="border-t border-hairline pt-8">
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
