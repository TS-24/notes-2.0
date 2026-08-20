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
    // Chats sit outside the workspace layout for the same reason /analytics
    // does: that layout renders the focused *note*, and a conversation is a
    // different object. "chats" is action-only — starting and deleting one from
    // the library — and "chats/:chatId" is the conversation itself.
    route("chats", "routes/chats.tsx"),
    route("chats/:chatId", "routes/chat.tsx"),
    // Resource route (loader only, no component). Deliberately outside the
    // layout: the word roller reads from it constantly, and a lookup inside the
    // workspace would drag the note list's revalidation along with it.
    route("api/word-ladder", "routes/api.word-ladder.tsx"),
    route("api/vocabulary", "routes/api.vocabulary.tsx"),
] satisfies RouteConfig;
