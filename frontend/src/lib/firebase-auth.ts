/**
 * Firebase Auth wrapper (Google sign-in).
 *
 * Stub for now — gets fleshed out once the user creates a Firebase
 * project and provides the NEXT_PUBLIC_FIREBASE_* env vars. The
 * sign-in page disables the Google button when those vars are
 * missing, so this module is never imported in unconfigured builds.
 *
 * To enable after Firebase setup:
 *   1. cd frontend && npm install firebase
 *   2. Set NEXT_PUBLIC_FIREBASE_API_KEY / AUTH_DOMAIN / PROJECT_ID /
 *      APP_ID in Vercel env vars (and locally in .env.local)
 *   3. Replace the body of signInWithGoogle() with the real
 *      initializeApp + signInWithPopup flow + POST to
 *      /api/v1/auth/firebase
 */

import type { UserProfile } from "./auth";

export async function signInWithGoogle(): Promise<UserProfile> {
  throw new Error(
    "Google sign-in is not configured yet. Install firebase (npm i firebase), " +
      "set NEXT_PUBLIC_FIREBASE_API_KEY / AUTH_DOMAIN / PROJECT_ID / APP_ID in " +
      "Vercel env vars, and replace lib/firebase-auth.ts with the real wiring.",
  );
}
