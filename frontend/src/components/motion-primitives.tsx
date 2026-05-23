"use client";

/**
 * Motion primitives — the tiny set of wrappers IncidentIQ uses for animation.
 *
 * Keep this file small. Every component here should be:
 *   - Tied to a token from lib/motion.ts (no ad-hoc durations / easings)
 *   - Composable (work the same in any context)
 *   - Honest about what it does (no magical hidden behaviour)
 */

import { AnimatePresence, motion, useInView, type Variants } from "framer-motion";
import {
  forwardRef,
  useEffect,
  useRef,
  useState,
  type ComponentPropsWithoutRef,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";
import { EASE, transitions, variants } from "@/lib/motion";

// ── FadeIn: the default entrance for almost everything ────────────────────

export function FadeIn({
  children,
  delay = 0,
  className,
  variant = "fadeRise",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  variant?: keyof typeof variants;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="visible"
      variants={variants[variant]}
      transition={{ ...transitions.base, delay }}
    >
      {children}
    </motion.div>
  );
}

// ── Stagger: orchestrates children. Children must use FadeItem. ────────────

export function StaggerList({
  children,
  className,
  variant = "stagger",
}: {
  children: ReactNode;
  className?: string;
  variant?: "stagger" | "staggerCards";
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="visible"
      variants={variants[variant]}
    >
      {children}
    </motion.div>
  );
}

export function FadeItem({
  children,
  className,
  variant = "fadeRiseFast",
}: {
  children: ReactNode;
  className?: string;
  variant?: "fadeRise" | "fadeRiseFast" | "cardRise";
}) {
  return (
    <motion.div className={className} variants={variants[variant]}>
      {children}
    </motion.div>
  );
}

// ── HoverCard: subtle lift on hover, disciplined ──────────────────────────

type DivProps = ComponentPropsWithoutRef<"div">;

export const HoverCard = forwardRef<HTMLDivElement, DivProps & { lift?: number }>(
  function HoverCard({ className, children, lift = 1.5, ...props }, ref) {
    return (
      <motion.div
        ref={ref}
        className={className}
        whileHover={{ y: -lift }}
        transition={transitions.fast}
        {...(props as object)}
      >
        {children}
      </motion.div>
    );
  },
);

// ── PresenceList: animates items in/out for streamed content ──────────────

export function PresenceList({ children }: { children: ReactNode }) {
  return <AnimatePresence initial={false}>{children}</AnimatePresence>;
}

export function PresenceItem({
  children,
  layoutId,
  className,
}: {
  children: ReactNode;
  layoutId?: string;
  className?: string;
}) {
  return (
    <motion.div
      layoutId={layoutId}
      className={className}
      initial={{ opacity: 0, x: -8, scale: 0.98 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 4 }}
      transition={transitions.base}
    >
      {children}
    </motion.div>
  );
}

// ── CountUp: animated number counter for stats ────────────────────────────

export function CountUp({
  to,
  duration = 1.1,
  format,
  className,
}: {
  to: number;
  duration?: number;
  format?: (value: number) => string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement | null>(null);
  const inView = useInView(ref, { once: true, margin: "-30% 0px" });
  const [displayed, setDisplayed] = useState(0);

  useEffect(() => {
    if (!inView) return;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / (duration * 1000));
      // ease-out-expo for the count itself so it decelerates
      const eased = 1 - Math.pow(2, -10 * t);
      setDisplayed(Math.round(to * eased));
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        setDisplayed(to);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, to, duration]);

  return (
    <span ref={ref} className={cn("tabular-nums", className)}>
      {format ? format(displayed) : displayed.toLocaleString()}
    </span>
  );
}

// ── BannerReveal: dramatic entrance — Deep Trace banner moment ─────────────

export function BannerReveal({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="visible"
      exit={{ opacity: 0, y: -8, transition: transitions.fast }}
      variants={variants.banner as Variants}
    >
      {children}
    </motion.div>
  );
}

// ── PulseDot: refined infinite pulse for live indicators ──────────────────

export function PulseDot({ className }: { className?: string }) {
  return (
    <span className={cn("relative inline-flex size-2.5", className)}>
      <motion.span
        className="absolute inset-0 rounded-full bg-current opacity-50"
        animate={{ scale: [1, 2.2, 1], opacity: [0.5, 0, 0.5] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: EASE }}
      />
      <span className="relative inline-block size-2.5 rounded-full bg-current" />
    </span>
  );
}
