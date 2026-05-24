/**
 * Deprecated shim. Use lib/auth.ts directly going forward.
 *
 * Kept temporarily so existing callers (SessionChip, Settings page,
 * SessionBootstrap) don't break while we migrate the codebase from
 * the old per-session-credential model to the unified user identity
 * model in lib/auth.ts.
 */

import {
  clearUser,
  getUserId,
  setUser,
  signInAsGuest,
} from "./auth";

/** @deprecated use getUserId() from lib/auth.ts */
export function getSessionId(): string | null {
  return getUserId();
}

/** @deprecated use setUser() from lib/auth.ts with a full profile */
export function setSessionId(id: string): void {
  // Best-effort: infer kind from prefix; default to guest for legacy values.
  if (id.startsWith("gh:")) {
    setUser({ id, kind: "github", displayName: id.slice(3) });
  } else if (id.startsWith("fb:")) {
    setUser({ id, kind: "firebase" });
  } else if (id.startsWith("guest:")) {
    setUser({ id, kind: "guest", displayName: "Guest" });
  } else {
    setUser({ id: `guest:${id}`, kind: "guest", displayName: "Guest" });
  }
}

/** @deprecated use signOut() from lib/auth.ts */
export function clearSessionId(): void {
  clearUser();
}

/**
 * @deprecated callers should redirect to /sign-in for unauthenticated
 * users instead of silently minting a guest session. Kept for the
 * Settings page bootstrap during transition.
 */
export async function ensureSessionId(): Promise<string | null> {
  const existing = getUserId();
  if (existing) return existing;
  try {
    const profile = await signInAsGuest();
    return profile.id;
  } catch {
    return null;
  }
}
