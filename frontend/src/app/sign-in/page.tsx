"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Github, Loader2, UserCircle2 } from "lucide-react";

import {
  signInAsGuest,
  startGitHubSignIn,
} from "@/lib/auth";

/**
 * Sign-in landing. Three paths in, one outcome: a user_id in localStorage.
 *
 *   - GitHub:   navigates to /api/v1/auth/github/login -> GitHub OAuth
 *                consent -> backend callback redirects to /dashboard
 *                with the login in the URL fragment.
 *   - Guest:    POSTs to /api/v1/auth/guest, stashes the returned
 *                token in localStorage, navigates to the original
 *                destination (or /dashboard).
 *   - Google:   Firebase Auth client SDK is wired once the
 *                NEXT_PUBLIC_FIREBASE_* env vars are set. Until then
 *                the button shows a disabled state with a hint.
 */
export default function SignInPage() {
  return (
    <section className="mx-auto max-w-md px-5 sm:px-6 py-12 sm:py-20">
      <Suspense fallback={null}>
        <SignInForm />
      </Suspense>
    </section>
  );
}

function SignInForm() {
  const router = useRouter();
  const params = useSearchParams();
  const from = params.get("from") || "/dashboard";

  const [busyPath, setBusyPath] = useState<"github" | "guest" | "google" | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  const googleEnabled = Boolean(
    process.env.NEXT_PUBLIC_FIREBASE_API_KEY &&
      process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  );

  const onGitHub = () => {
    setError(null);
    setBusyPath("github");
    // Full-page navigate to the backend OAuth endpoint. No client state
    // to preserve; AuthBootstrap picks up the resulting login on
    // /dashboard.
    startGitHubSignIn();
  };

  const onGuest = async () => {
    setError(null);
    setBusyPath("guest");
    try {
      await signInAsGuest();
      router.replace(from);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusyPath(null);
    }
  };

  const onGoogle = async () => {
    if (!googleEnabled) return;
    setError(null);
    setBusyPath("google");
    try {
      // Dynamic import keeps the firebase bundle out of the initial
      // page load (it's ~200KB minified). Only fires when the user
      // actually clicks Google sign-in.
      const { signInWithGoogle } = await import("@/lib/firebase-auth");
      await signInWithGoogle();
      router.replace(from);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusyPath(null);
    }
  };

  return (
    <>
      <div className="mb-8 text-center">
        <Link
          href="/"
          className="inline-block text-[15px] font-semibold tracking-tight text-ink-50 hover:text-white transition"
        >
          IncidentIQ<span className="text-ink-400 font-normal">.</span>
        </Link>
        <h1 className="mt-6 text-2xl sm:text-3xl font-semibold tracking-tight text-ink-50">
          Welcome
        </h1>
        <p className="mt-2 text-[13px] sm:text-[14px] text-ink-400 leading-relaxed">
          Sign in so your incidents, pasted credentials, and code-fix
          history stay yours — separate from everyone else trying out the
          public demo.
        </p>
      </div>

      <div className="space-y-2.5">
        <AuthButton
          onClick={onGitHub}
          busy={busyPath === "github"}
          icon={<Github className="size-4" />}
          label="Sign in with GitHub"
          subtle="Recommended — reuses the GitHub repo connection for code-aware fix."
        />

        <AuthButton
          onClick={onGoogle}
          disabled={!googleEnabled}
          busy={busyPath === "google"}
          icon={<GoogleMark />}
          label="Sign in with Google"
          subtle={
            googleEnabled
              ? "Via Firebase Auth."
              : "Configure NEXT_PUBLIC_FIREBASE_* env vars to enable."
          }
        />

        <div className="my-3 flex items-center gap-3 text-[10.5px] uppercase tracking-[0.18em] text-ink-500 font-semibold">
          <span className="flex-1 h-px bg-white/[0.06]" />
          or
          <span className="flex-1 h-px bg-white/[0.06]" />
        </div>

        <AuthButton
          onClick={onGuest}
          busy={busyPath === "guest"}
          icon={<UserCircle2 className="size-4" />}
          label="Continue as guest"
          subtle="No account needed. Per-browser isolation — clear localStorage to reset."
          variant="ghost"
        />
      </div>

      {error ? (
        <div className="mt-4 rounded-md border border-red-500/30 bg-red-500/10 text-red-200 px-3 py-2 text-[12.5px]">
          {error}
        </div>
      ) : null}

      <div className="mt-8 text-center text-[11.5px] text-ink-500 leading-relaxed">
        Whatever you pick, your incidents and pasted Datadog / Grafana /
        New Relic keys live only under your identity — nobody else on this
        deployment can see them.
      </div>
    </>
  );
}

function AuthButton({
  onClick,
  label,
  subtle,
  icon,
  busy,
  disabled,
  variant = "primary",
}: {
  onClick: () => void;
  label: string;
  subtle: string;
  icon: React.ReactNode;
  busy?: boolean;
  disabled?: boolean;
  variant?: "primary" | "ghost";
}) {
  const isDisabled = busy || disabled;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isDisabled}
      className={
        variant === "primary"
          ? "group w-full flex items-center gap-3 rounded-lg border border-white/[0.10] bg-white/[0.04] px-4 py-3 text-left transition hover:bg-white/[0.08] disabled:opacity-50 disabled:cursor-not-allowed"
          : "group w-full flex items-center gap-3 rounded-lg border border-white/[0.06] bg-transparent px-4 py-3 text-left transition hover:bg-white/[0.04] disabled:opacity-50 disabled:cursor-not-allowed"
      }
    >
      <span className="shrink-0 size-9 grid place-items-center rounded-md bg-ink-950/60 border border-white/[0.07] text-ink-200">
        {busy ? <Loader2 className="size-4 animate-spin" /> : icon}
      </span>
      <span className="flex-1 min-w-0">
        <span className="block text-[13.5px] font-medium text-ink-50">
          {label}
        </span>
        <span className="block text-[11.5px] text-ink-500 mt-0.5">
          {subtle}
        </span>
      </span>
      <ArrowRight className="size-4 text-ink-500 group-hover:text-ink-200 transition" />
    </button>
  );
}

function GoogleMark() {
  // Minimal G mark, matching button monochrome treatment.
  return (
    <svg viewBox="0 0 24 24" className="size-4" aria-hidden>
      <path
        fill="currentColor"
        d="M21.35 11.1H12v3.2h5.35c-.5 2.3-2.4 3.9-5.35 3.9-3.2 0-5.8-2.6-5.8-5.8s2.6-5.8 5.8-5.8c1.5 0 2.85.55 3.9 1.45l2.4-2.4C16.5 3.95 14.4 3 12 3 7 3 3 7 3 12s4 9 9 9c5.2 0 8.7-3.65 8.7-8.8 0-.6-.05-1.05-.15-1.5z"
      />
    </svg>
  );
}
