"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";
import { UserMenu } from "./UserMenu";

/**
 * Top nav for IncidentIQ. Renders the brand mark on the left and a
 * row of routed links on the right. Active-route gets a subtle white
 * pill behind it so a glance at the chrome tells you where you are -
 * the previous version was flat text and felt unstyled.
 */

interface NavItem {
  href: string;
  label: string;
  matchPrefix?: string;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", matchPrefix: "/dashboard" },
  { href: "/incidents", label: "History", matchPrefix: "/incidents" },
  { href: "/settings", label: "Settings", matchPrefix: "/settings" },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-white/[0.08] bg-ink-950/85 backdrop-blur-xl">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 h-14 flex items-center justify-between gap-3">
        <Link
          href="/"
          className="font-semibold tracking-tight text-ink-50 text-[15px] hover:text-white transition shrink-0"
        >
          IncidentIQ
          <span className="text-ink-400 font-normal">.</span>
        </Link>

        <nav className="flex items-center gap-1 sm:gap-1.5">
          {NAV_ITEMS.map((item) => {
            const active =
              pathname === item.href ||
              (item.matchPrefix !== undefined &&
                pathname?.startsWith(item.matchPrefix));
            const isHiddenOnMobile = item.href === "/settings";
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "relative rounded-md px-2.5 sm:px-3 py-1.5 text-[12.5px] sm:text-[13px] font-medium transition",
                  active
                    ? "text-ink-50 bg-white/[0.08]"
                    : "text-ink-300 hover:text-ink-50 hover:bg-white/[0.04]",
                  isHiddenOnMobile && "hidden sm:inline-flex",
                )}
              >
                {item.label}
                {active ? (
                  <span className="absolute inset-x-3 -bottom-px h-[2px] bg-brand-300/80 rounded-full" />
                ) : null}
              </Link>
            );
          })}
          <Link
            href="/dashboard"
            className="ml-1 sm:ml-2 inline-flex items-center rounded-md bg-brand-500/15 text-brand-100 border border-brand-500/40 hover:bg-brand-500/25 px-3 sm:px-3.5 py-1.5 text-[12.5px] sm:text-[13px] font-medium transition"
          >
            Analyze
          </Link>
          <UserMenu />
        </nav>
      </div>
    </header>
  );
}
