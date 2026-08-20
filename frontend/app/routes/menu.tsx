import { Form, Link, redirect, useFetcher, useNavigation } from "react-router";

import { api, ApiError } from "~/lib/api.server";
import { requireToken } from "~/lib/session.server";
import { commitTheme, getTheme } from "~/lib/theme.server";
import { applyTheme, resolveTheme, THEMES, type Theme } from "~/lib/themes";
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
  return { user, provider, theme: await getTheme(request) };
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

  /*
    The theme is a cookie, not an account setting, so it never reaches the API.
    Redirecting rather than returning data is the point: it makes the browser
    re-request the page with the new cookie already set, which re-runs the root
    loader and puts the palette on `<html>` the same way a cold load would.
  */
  if (formData.get("intent") === "theme") {
    return redirect("/settings", {
      headers: { "Set-Cookie": await commitTheme(String(formData.get("theme") ?? "")) },
    });
  }

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

/**
 * One eyebrow style, borrowed from the chat card, so a section here announces
 * itself the same way a card in the library does. It is the only label rank the
 * app has below a heading, and inventing a second would be inventing a second.
 */
const EYEBROW = "text-xs uppercase tracking-[0.14em] text-ink/45";

/** A panel: one step of paper tone, no border and no shadow (DESIGN.md §5). */
const PANEL = "rounded-2xl bg-paper-raised p-7 sm:p-8";

const FIELD =
  "mt-1.5 w-full border-b border-ink/15 bg-transparent py-2 outline-none transition-colors focus:border-accent-ink";

/**
 * The palette picker.
 *
 * A plain `<select>` rather than a row of swatches: there are four of these and
 * there will be more, and a native control is the one thing that stays usable at
 * any length, on a phone, and by keyboard without any of it being written here.
 *
 * It submits on change, and `applyTheme` repaints immediately so the colours do
 * not wait on the post. The submit button is the no-JS path — without script the
 * change event still fires but nothing sends the form, so the button has to be
 * real rather than wrapped in `<noscript>`.
 */
function ThemePicker({ current }: { current: Theme }) {
  const fetcher = useFetcher();

  return (
    <fetcher.Form method="post" className="max-w-xs">
      <input type="hidden" name="intent" value="theme" />
      <label htmlFor="theme" className="text-sm text-ink/60">
        Palette
      </label>
      <select
        id="theme"
        name="theme"
        defaultValue={current.id}
        className={`${FIELD} cursor-pointer`}
        onChange={(event) => {
          applyTheme(resolveTheme(event.target.value));
          fetcher.submit(event.currentTarget.form);
        }}
      >
        {THEMES.map((theme) => (
          <option key={theme.id} value={theme.id}>
            {theme.label}
          </option>
        ))}
      </select>
      <button
        type="submit"
        className="mt-4 rounded-xl border border-ink/15 px-4 py-1.5 text-sm text-ink transition-colors hover:bg-paper"
      >
        Save
      </button>
    </fetcher.Form>
  );
}

export default function Menu({ loaderData, actionData }: Route.ComponentProps) {
  const { user, provider, theme } = loaderData;
  const navigation = useNavigation();
  const saving = navigation.formData?.get("intent") !== "forget" && navigation.state !== "idle";
  const initial = (user.username || user.email).trim().charAt(0).toUpperCase();

  return (
    <main className="mx-auto max-w-2xl space-y-8 px-8 py-12">
      {/* The exit sits at the head of the column, at Meta size — DESIGN.md's
          form for leaving a view, in place of a back button or a rail. */}
      <Link to="/notes" className="block text-sm tracking-wide text-ink/50 transition-colors hover:text-ink">
        ← Your notes
      </Link>

      {/*
        A title and a line saying what the page is for. The page was a stack of
        sections that all began at the same weight, so nothing said where to
        start reading; giving the head of the column its own rank is what makes
        the rest of it a list of things rather than one long thing.
      */}
      <header className="space-y-2">
        <p className={EYEBROW}>Settings</p>
        <h1 className="font-display text-4xl tracking-tight">Account</h1>
        <p className="text-ink/60">
          Who you are signed in as, and the provider your conversations run on.
        </p>
      </header>

      {/* Identity, as a card rather than a caption: it is the answer to the
          first question anyone opens this page with. */}
      <section className={`${PANEL} flex items-center gap-4`}>
        <span
          aria-hidden
          className="flex size-12 shrink-0 items-center justify-center rounded-full border border-ink/15 bg-paper font-display text-lg text-ink/70"
        >
          {initial}
        </span>
        <div className="min-w-0">
          <p className="truncate font-display text-lg text-ink">{user.username}</p>
          <p className="truncate text-sm text-ink/60">{user.email}</p>
        </div>
      </section>

      {/* Appearance before the provider key: it is the section someone is far
          more likely to have come here to change. */}
      <section className={`${PANEL} space-y-6`}>
        <div className="space-y-2">
          <p className={EYEBROW}>Appearance</p>
          <h2 className="font-display text-2xl tracking-tight">Theme</h2>
          <p className="text-sm leading-relaxed text-ink/60">
            Applies to this browser. Paper is the palette the app was drawn in;
            the rest are ports of colour schemes you may already read code in.
          </p>
        </div>

        <ThemePicker current={theme} />
      </section>

      <section className={`${PANEL} space-y-6`}>
        <div className="space-y-2">
          <p className={EYEBROW}>Conversations</p>
          <h2 className="font-display text-2xl tracking-tight">AI provider</h2>
          <p className="text-sm leading-relaxed text-ink/60">
            Chats run on your own account with the provider you choose. The key
            is stored encrypted and is never shown again after you save it.
          </p>
        </div>

        {/* What is on file, set apart from the prose above it so the state of
            the account reads at a glance rather than in a sentence. */}
        <div className="rounded-xl bg-paper px-4 py-3">
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
        </div>

        {/*
          A real Form and a route action rather than the fetcher pattern used
          inside the workspace: this is a navigation, and — like login.tsx — it
          has to work before the page has hydrated.
        */}
        <Form method="post" className="space-y-5" autoComplete="off">
          {/*
            Stacked, and in this order, on purpose. Chrome reads "a text input
            immediately above a password input" as a sign-in form and fills the
            pair with the saved account credentials — putting the model field
            there filled it with the reader's email and the key field with their
            Restyle password, which they would then have saved as an API key. A
            select is not a username, so the provider goes above the key and the
            model below it.
          */}
          <label className="block">
            <span className="text-sm text-ink/60">Provider</span>
            <select
              name="provider"
              defaultValue={provider.provider ?? provider.available[0]?.id}
              className={FIELD}
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
              autoComplete="new-password"
              spellCheck={false}
              placeholder={provider.configured ? "Enter a new key to replace it" : ""}
              className={FIELD}
            />
          </label>

          <label className="block">
            <span className="text-sm text-ink/60">Model</span>
            <input
              type="text"
              name="model"
              defaultValue={provider.model ?? ""}
              autoComplete="off"
              spellCheck={false}
              placeholder={provider.available[0]?.default_model}
              className={FIELD}
            />
            <span className="mt-1.5 block text-xs italic text-ink/45">
              Blank uses the provider's default.
            </span>
          </label>

          {actionData ? (
            <p
              role="status"
              className={`text-sm ${actionData.ok ? "text-ink/60" : "text-danger"}`}
            >
              {actionData.message}
            </p>
          ) : null}

          <div className="flex items-center gap-4 pt-1">
            {/* The rose pill the note editor's Done button already uses: this
                is the one action the page is asking for. */}
            <button
              type="submit"
              disabled={saving}
              className="rounded-xl bg-accent px-5 py-2 text-sm text-on-accent transition-opacity hover:opacity-90 disabled:opacity-50"
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
      <section className={`${PANEL} space-y-4`}>
        <div className="space-y-2">
          <p className={EYEBROW}>Session</p>
          <p className="text-sm text-ink/60">
            Signs out this browser only. Anywhere else you are signed in stays
            signed in.
          </p>
        </div>
        <Form method="post" action="/logout">
          <button
            type="submit"
            className="rounded-xl border border-ink/15 px-5 py-2 text-sm transition-colors hover:bg-ink/5"
          >
            Sign out
          </button>
        </Form>
      </section>
    </main>
  );
}
