/**
 * Per-browser identity management.
 *
 * Replaces the old per-session credential token with a proper user
 * identity. Three flavours, one localStorage key, one header.
 *
 *   gh:<github_login>     - signed in via GitHub OAuth
 *   fb:<firebase_uid>     - signed in via Google (Firebase Auth)
 *   guest:<random_token>  - "Continue as guest", per-browser isolated
 *
 * The user_id is sent on every API call as ``X-IIQ-User``. Backend
 * uses it to scope incidents, credentials, watch mode, and code-fix.
 *
 * Sign-out clears localStorage and bounces the user to /sign-in.
 */

import { API_BASE } from "./api-base";

const STORAGE_USER_ID = "iiq.user_id";
const STORAGE_PROFILE = "iiq.user_profile";

export type UserKind = "github" | "firebase" | "guest";

export interface UserProfile {
  id: string;
  kind: UserKind;
  displayName?: string;
  avatarUrl?: string;
}

let cachedUserId: string | null = null;
let cachedProfile: UserProfile | null = null;

// ── Read ────────────────────────────────────────────────────────────

export function getUserId(): string | null {
  if (typeof window === "undefined") return null;
  if (cachedUserId !== null) return cachedUserId;
  cachedUserId = window.localStorage.getItem(STORAGE_USER_ID);
  return cachedUserId;
}

export function getUserProfile(): UserProfile | null {
  if (typeof window === "undefined") return null;
  if (cachedProfile) return cachedProfile;
  const raw = window.localStorage.getItem(STORAGE_PROFILE);
  if (!raw) return null;
  try {
    cachedProfile = JSON.parse(raw) as UserProfile;
    return cachedProfile;
  } catch {
    return null;
  }
}

export function isSignedIn(): boolean {
  return getUserId() !== null;
}

export function userKind(): UserKind | null {
  const id = getUserId();
  if (!id) return null;
  if (id.startsWith("gh:")) return "github";
  if (id.startsWith("fb:")) return "firebase";
  if (id.startsWith("guest:")) return "guest";
  return null;
}

// ── Write ───────────────────────────────────────────────────────────

export function setUser(profile: UserProfile): void {
  if (typeof window === "undefined") return;
  cachedUserId = profile.id;
  cachedProfile = profile;
  window.localStorage.setItem(STORAGE_USER_ID, profile.id);
  window.localStorage.setItem(STORAGE_PROFILE, JSON.stringify(profile));
}

export function clearUser(): void {
  if (typeof window === "undefined") return;
  cachedUserId = null;
  cachedProfile = null;
  window.localStorage.removeItem(STORAGE_USER_ID);
  window.localStorage.removeItem(STORAGE_PROFILE);
}

// ── Auth flows ─────────────────────────────────────────────────────

/**
 * Click "Continue as guest". Backend mints a random opaque token, we
 * stash it in localStorage. From this point on every API call sends
 * the guest id and the backend scopes everything to it.
 */
export async function signInAsGuest(): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/api/v1/auth/guest`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`Guest sign-in failed: ${res.status}`);
  }
  const body = (await res.json()) as { user_id: string };
  const profile: UserProfile = {
    id: body.user_id,
    kind: "guest",
    displayName: "Guest",
  };
  setUser(profile);
  return profile;
}

/**
 * Kicks off GitHub OAuth. The actual flow lives in the backend at
 * /auth/github/login; we just navigate the browser there. After the
 * GitHub authorize page the user lands back on
 * /dashboard#github=connected&login=<their_login>, which the layout
 * bootstrap picks up to stitch the user id into localStorage.
 */
export function startGitHubSignIn(): void {
  window.location.href = `${API_BASE}/api/v1/auth/github/login`;
}

/**
 * Called by the layout bootstrap once we see the post-callback
 * fragment. Promotes "guest" -> "gh:<login>" without losing any
 * intermediate state.
 */
export function completeGitHubSignIn(login: string): UserProfile {
  const profile: UserProfile = {
    id: `gh:${login}`,
    kind: "github",
    displayName: login,
    avatarUrl: `https://github.com/${login}.png?size=80`,
  };
  setUser(profile);
  return profile;
}

/**
 * Best-effort server signal. Server has no token to revoke (stateless)
 * but we still ping it so any future server-side revocation gets a
 * place to live. Always clears local state regardless of the response.
 */
export async function signOut(): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/v1/auth/signout`, {
      method: "POST",
      headers: {
        ...(cachedUserId ? { "X-IIQ-User": cachedUserId } : {}),
      },
    });
  } catch {
    /* ignore - clearing local state is what matters */
  }
  clearUser();
}
