/**
 * Motion design tokens — one source of truth.
 *
 * Every animation in IncidentIQ goes through these constants. Same easing
 * curve, same durations, same stagger rhythm. That's what separates a
 * "designed" feel from a "vibe-coded" one — disciplined repetition.
 *
 * Reference: Linear, Vercel, Stripe all use a similar tight design system
 * around their motion language.
 */

import type { Transition, Variants } from "framer-motion";

// One refined cubic-bezier ("easeOutExpo"-like) — feels confident, not bouncy.
export const EASE = [0.16, 1, 0.3, 1] as const;

// Durations expressed in seconds (framer-motion convention).
export const DURATION = {
  /** Snappy micro-interactions: hover, focus rings, toggles. */
  fast: 0.18,
  /** Default UI transitions: cards entering, content swapping. */
  base: 0.32,
  /** Hero / "dramatic" moments — Deep Trace banner, key reveals. */
  slow: 0.5,
} as const;

// Reusable framer-motion transitions.
export const transitions: Record<string, Transition> = {
  fast: { duration: DURATION.fast, ease: EASE },
  base: { duration: DURATION.base, ease: EASE },
  slow: { duration: DURATION.slow, ease: EASE },
  spring: { type: "spring", stiffness: 260, damping: 28 },
};

// Common variants — import these instead of redefining ad-hoc animations.
export const variants: Record<string, Variants> = {
  // Fade + small upward slide. Use as the default entrance.
  fadeRise: {
    hidden: { opacity: 0, y: 8 },
    visible: { opacity: 1, y: 0, transition: transitions.base },
  },
  // Same as fadeRise but quicker — good for list items in a stagger.
  fadeRiseFast: {
    hidden: { opacity: 0, y: 6 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.22, ease: EASE } },
  },
  // Card entrance with a touch more lift — for hero / key panels.
  cardRise: {
    hidden: { opacity: 0, y: 14 },
    visible: { opacity: 1, y: 0, transition: transitions.slow },
  },
  // Stagger container — orchestrates children that use fadeRise / fadeRiseFast.
  stagger: {
    hidden: {},
    visible: {
      transition: { staggerChildren: 0.07, delayChildren: 0.02 },
    },
  },
  // Heavier stagger for the dramatic result sections.
  staggerCards: {
    hidden: {},
    visible: {
      transition: { staggerChildren: 0.1, delayChildren: 0.05 },
    },
  },
  // Dramatic banner entrance — Deep Trace recommendation moment.
  banner: {
    hidden: { opacity: 0, y: -10, scale: 0.98 },
    visible: {
      opacity: 1,
      y: 0,
      scale: 1,
      transition: { duration: 0.42, ease: EASE },
    },
  },
};

/**
 * Standard hover lift used on interactive cards. A 1.5px rise plus a
 * subtle brightness lift — disciplined, not cartoonish.
 */
export const hoverLift = {
  whileHover: { y: -1.5 },
  transition: transitions.fast,
};

// Helper for components that should respect prefers-reduced-motion.
// framer-motion already does this internally for `transition`, but you
// can also use this prop on individual motion components if you need
// custom logic.
export const respectsReducedMotion = true;
