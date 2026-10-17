import { useEffect, useState, type AnchorHTMLAttributes, type MouseEvent } from "react";

/** The pages of the interface. The service answers index.html for each path. */
export type Route = "merge" | "split" | "rotate" | "terms" | "not-found";

const PATHS: Readonly<Record<Exclude<Route, "not-found">, string>> = {
  merge: "/",
  split: "/split",
  rotate: "/rotate",
  terms: "/terms",
};

export function pathOf(route: Exclude<Route, "not-found">): string {
  return PATHS[route];
}

export function routeOf(pathname: string): Route {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === "/merge") {
    return "merge";
  }
  const found = (Object.entries(PATHS) as [Exclude<Route, "not-found">, string][]).find(([, p]) => p === path);
  return found?.[0] ?? "not-found";
}

const listeners = new Set<() => void>();

export function navigate(route: Exclude<Route, "not-found">): void {
  if (window.location.pathname !== pathOf(route)) {
    window.history.pushState(null, "", pathOf(route));
    for (const listener of listeners) {
      listener();
    }
  }
  window.scrollTo({ top: 0 });
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => routeOf(window.location.pathname));
  useEffect(() => {
    const update = () => setRoute(routeOf(window.location.pathname));
    listeners.add(update);
    window.addEventListener("popstate", update);
    return () => {
      listeners.delete(update);
      window.removeEventListener("popstate", update);
    };
  }, []);
  return route;
}

interface LinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  readonly to: Exclude<Route, "not-found">;
}

/** A link to a page of the interface: changes page without reloading, unless opened elsewhere. */
export function Link({ to, onClick, target, ...props }: LinkProps) {
  const handle = (event: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(event);
    const elsewhere = target === "_blank" || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0;
    if (!event.defaultPrevented && !elsewhere) {
      event.preventDefault();
      navigate(to);
    }
  };
  return (
    <a
      href={pathOf(to)}
      onClick={handle}
      target={target}
      rel={target === "_blank" ? "noopener" : undefined}
      {...props}
    />
  );
}
