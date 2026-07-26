import { useSyncExternalStore, type ReactNode } from "react";

const emptySubscribe = () => () => {};

/**
 * Renders its children only in the browser.
 *
 * Some components cannot server-render because they reach for browser-only
 * APIs during render — `masonic`, for example, constructs a ResizeObserver,
 * which does not exist in Node. Wrapping those in ClientOnly keeps them out of
 * the server pass while still letting the route's loader fetch data on the
 * server.
 *
 * useSyncExternalStore is used rather than a useEffect flag because its
 * separate server snapshot makes the server and first client render agree,
 * which avoids a hydration mismatch.
 */
export function ClientOnly({
  children,
  fallback = null,
}: {
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const isHydrated = useSyncExternalStore(
    emptySubscribe,
    () => true, // client
    () => false, // server
  );

  return <>{isHydrated ? children : fallback}</>;
}
