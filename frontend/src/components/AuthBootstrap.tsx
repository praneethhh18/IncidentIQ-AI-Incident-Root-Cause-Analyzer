"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import { completeGitHubSignIn, getUserId, isSignedIn } from "@/lib/auth";

/**
 * Mounted on the root layout. Two jobs:
 *
 *   1. Pick up the post-GitHub-OAuth fragment on /dashboard. The
 *      callback redirects to
 *      /dashboard#github=connected&login=<their_login>; we read
 *      the login, promote the user from guest -> gh:<login>, and
 *      clear the fragment so refreshes don't re-trigger.
 *
 *   2. Gate every non-public route behind sign-in. If no user id is
 *      in localStorage and we're not already on /sign-in or /, bounce
 *      to /sign-in. Public surfaces (landing page, sign-in itself)
 *      always render.
 *
 * Renders nothing.
 */

const PUBLIC_PATHS = new Set<string>(["/", "/sign-in"]);

export function AuthBootstrap(): null {
  const router = useRouter();
  const pathname = usePathname() ?? "/";

  useEffect(() => {
    // GitHub OAuth callback hand-off. The callback page itself is the
    // backend's redirect target (which lands on /dashboard with the
    // hash payload), so this effect runs on the dashboard mount.
    if (typeof window === "undefined") return;
    const hash = window.location.hash;
    if (hash.includes("github=connected")) {
      const params = new URLSearchParams(hash.replace(/^#/, ""));
      const login = params.get("login");
      if (login) {
        completeGitHubSignIn(login);
      }
      // Clear the fragment so refreshes don't re-process.
      history.replaceState(
        null,
        "",
        window.location.pathname + window.location.search,
      );
    }
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (PUBLIC_PATHS.has(pathname)) return;
    // After GitHub OAuth we're on /dashboard with the hash; the other
    // effect promotes the user synchronously before this effect runs.
    // But Next's router may render this twice during hydration, so we
    // re-check after a microtask to avoid a flash redirect.
    if (!isSignedIn()) {
      router.replace(`/sign-in?from=${encodeURIComponent(pathname)}`);
    }
  }, [pathname, router]);

  return null;
}
