"use client";

import { useEffect } from "react";

import { ensureSessionId } from "@/lib/session";

/**
 * Tiny client component that fires once on mount to make sure the
 * browser has a session id stashed in localStorage. Mounted on the
 * root layout so every page is covered, even if the user lands deep
 * on /incidents/<id> from a shared link.
 *
 * Renders nothing. Idempotent: if a session id already exists, the
 * call to ensureSessionId just touches the server-side last_seen and
 * returns the cached value.
 */
export function SessionBootstrap(): null {
  useEffect(() => {
    void ensureSessionId();
  }, []);
  return null;
}
