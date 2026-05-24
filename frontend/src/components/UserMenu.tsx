"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ChevronDown,
  Github,
  LogOut,
  UserCircle2,
} from "lucide-react";

import { getUserProfile, signOut, type UserProfile } from "@/lib/auth";

/**
 * Header chip + dropdown showing who's signed in. Reads from the same
 * localStorage as the rest of the auth stack. When the user is a
 * guest, shows "Guest · abc1…xyz" (preview of the token). When
 * GitHub, shows their avatar + login. When Firebase, shows their
 * display name + avatar.
 *
 * Sign out clears localStorage and bounces to /sign-in.
 */
export function UserMenu() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setProfile(getUserProfile());
    // Re-poll on focus so a sign-in in another tab (rare) is reflected.
    const onFocus = () => setProfile(getUserProfile());
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const onSignOut = async () => {
    setOpen(false);
    await signOut();
    setProfile(null);
    router.replace("/sign-in");
  };

  if (!profile) {
    return null;
  }

  const label = labelFor(profile);
  const Avatar = avatarFor(profile);

  return (
    <div ref={wrapperRef} className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.07] bg-white/[0.03] hover:bg-white/[0.06] px-1.5 sm:px-2 py-1 transition"
      >
        <Avatar />
        <span className="hidden sm:inline text-[12px] font-medium text-ink-100 max-w-[110px] truncate">
          {label}
        </span>
        <ChevronDown className="size-3 text-ink-400" />
      </button>

      {open ? (
        <div className="absolute right-0 top-full mt-1.5 min-w-[200px] rounded-lg border border-white/[0.10] bg-ink-900/95 backdrop-blur-md shadow-glow z-50 overflow-hidden">
          <div className="px-3 py-2.5 border-b border-white/[0.06]">
            <div className="text-[10.5px] uppercase tracking-wider text-ink-500 font-semibold">
              Signed in as
            </div>
            <div className="mt-0.5 text-[12.5px] text-ink-100 font-medium truncate">
              {label}
            </div>
            <div className="text-[10.5px] text-ink-500 font-mono mt-0.5 truncate">
              {profile.id}
            </div>
          </div>
          <button
            type="button"
            onClick={onSignOut}
            className="w-full flex items-center gap-2 px-3 py-2 text-[12.5px] text-ink-200 hover:bg-white/[0.05] hover:text-red-200 transition"
          >
            <LogOut className="size-3.5" /> Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}

function labelFor(p: UserProfile): string {
  if (p.kind === "github") return `@${p.displayName ?? p.id.slice(3)}`;
  if (p.kind === "firebase") return p.displayName ?? "Google user";
  // Guest: short preview of the token so two guests on the same machine
  // can still tell themselves apart (e.g. switching identities locally).
  const tail = p.id.slice(-4);
  return `Guest · ${tail}`;
}

function avatarFor(p: UserProfile) {
  if (p.avatarUrl) {
    const url = p.avatarUrl;
    return function Avatar() {
      // eslint-disable-next-line @next/next/no-img-element
      return (
        <img
          src={url}
          alt=""
          className="size-5 rounded-full"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
        />
      );
    };
  }
  if (p.kind === "github") {
    return function Avatar() {
      return <Github className="size-3.5 text-ink-300" />;
    };
  }
  return function Avatar() {
    return <UserCircle2 className="size-4 text-ink-400" />;
  };
}
