/**
 * Firebase Auth wrapper (Google sign-in).
 *
 * Reads its config from NEXT_PUBLIC_FIREBASE_* env vars baked into the
 * Next.js build. Lazy-loads the firebase SDK on first call so the
 * ~200KB chunk only hits the network when a visitor actually clicks
 * "Sign in with Google" - the bundled landing-page payload stays light.
 *
 * Flow:
 *   1. Initialize the Firebase app + auth on first call.
 *   2. Trigger Google sign-in popup; user picks their Google account.
 *   3. Read the ID token from the resulting credential.
 *   4. POST it to /api/v1/auth/firebase on our backend, which verifies
 *      the token with Firebase Admin and returns the canonical
 *      user_id (fb:<uid>) + display name + avatar.
 *   5. Stash the profile in localStorage just like the other sign-in
 *      paths, so the rest of the app treats it the same.
 */

import { initializeApp, type FirebaseApp } from "firebase/app";
import {
  GoogleAuthProvider,
  getAuth,
  signInWithPopup,
  type Auth,
} from "firebase/auth";

import { API_BASE } from "./api-base";
import { setUser, type UserProfile } from "./auth";

let cachedApp: FirebaseApp | null = null;
let cachedAuth: Auth | null = null;
let cachedProvider: GoogleAuthProvider | null = null;

function firebaseConfig(): Record<string, string> {
  const cfg = {
    apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY ?? "",
    authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN ?? "",
    projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID ?? "",
    appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID ?? "",
  };
  if (!cfg.apiKey || !cfg.authDomain || !cfg.projectId || !cfg.appId) {
    throw new Error(
      "Firebase not configured. Set NEXT_PUBLIC_FIREBASE_API_KEY / AUTH_DOMAIN / PROJECT_ID / APP_ID on Vercel.",
    );
  }
  return cfg;
}

function ensureFirebase(): { auth: Auth; provider: GoogleAuthProvider } {
  if (!cachedApp) {
    cachedApp = initializeApp(firebaseConfig());
    cachedAuth = getAuth(cachedApp);
    cachedProvider = new GoogleAuthProvider();
    // Force the account chooser so users on shared machines don't get
    // silently signed in as the last Google account on the device.
    cachedProvider.setCustomParameters({ prompt: "select_account" });
  }
  return { auth: cachedAuth!, provider: cachedProvider! };
}

export async function signInWithGoogle(): Promise<UserProfile> {
  const { auth, provider } = ensureFirebase();
  const result = await signInWithPopup(auth, provider);
  const idToken = await result.user.getIdToken();

  // Hand the ID token to our backend, which verifies it via Firebase
  // Admin and returns the canonical user_id (fb:<uid>) + profile bits.
  const res = await fetch(`${API_BASE}/api/v1/auth/firebase`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({ id_token: idToken }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(
      `Firebase token exchange failed (${res.status}): ${text.slice(0, 200)}`,
    );
  }
  const body = (await res.json()) as {
    user_id: string;
    display_name?: string;
    avatar_url?: string;
  };

  const profile: UserProfile = {
    id: body.user_id,
    kind: "firebase",
    displayName: body.display_name ?? result.user.displayName ?? "Google user",
    avatarUrl: body.avatar_url ?? result.user.photoURL ?? undefined,
  };
  setUser(profile);
  return profile;
}
