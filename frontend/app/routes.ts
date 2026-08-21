import {
    type RouteConfig,
    index,
    layout,
    route
} from "@react-router/dev/routes";

export default [
    // Outside the workspace layout on purpose: that layout's loader requires a
    // session, so nesting the login page inside it would redirect to itself.
    route("login", "routes/login.tsx"),
    route("register", "routes/register.tsx"),
    route("logout", "routes/logout.tsx"),
    // The landing page and the grid share a layout so the note surface inside
    // it survives navigation between them — see app/routes/workspace.tsx.
    layout("routes/workspace.tsx", [
        index("routes/home.tsx"),
        route("notes", "routes/notes.tsx"),
    ]),
    route("analytics", "routes/analytics.tsx"),
    route("settings", "routes/menu.tsx"),
    // Chat routes are action-only: the conversation itself renders as a boxed
    // overlay inside the workspace layout, morphing from its card in the grid.
    // "chats" handles create/delete from the library; "chats/:chatId" handles
    // send/finish from the overlay fetchers.
    route("chats", "routes/chats.tsx"),
    route("chats/:chatId", "routes/chat.tsx"),
    // Resource route (loader only, no component). Deliberately outside the
    // layout: the word roller reads from it constantly, and a lookup inside the
    // workspace would drag the note list's revalidation along with it.
    route("api/word-ladder", "routes/api.word-ladder.tsx"),
    route("api/vocabulary", "routes/api.vocabulary.tsx"),
    route("api/active-model", "routes/api.active-model.tsx"),
] satisfies RouteConfig;
