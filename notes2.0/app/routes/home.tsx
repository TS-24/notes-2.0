import type { Route } from "./+types/home";
import Welcome from "../welcome/welcome";

export function meta({}: Route.MetaArgs) {
  return [
    { title: "Notes 2.0" },
    { name: "description", content: "Welcome to Notes!" },
  ];
}

export default function Home() {
  return <Welcome />;
}
