import { 
    type RouteConfig, 
    index, 
    route
} from "@react-router/dev/routes";

export default [
    index("routes/home.tsx"),
    route("notes", "routes/notes.tsx"),
    route("analytics", "routes/analytics.tsx"),
    route("settings", "routes/menu.tsx")
] satisfies RouteConfig;
