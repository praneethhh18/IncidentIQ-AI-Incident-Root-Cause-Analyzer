"use client";

/**
 * ScrollProgress. Thin fixed line at the very top of the viewport whose
 * scaleX is driven by overall page scroll progress. Disappears entirely
 * when the page isn't scrollable. Pinned to z above the navbar.
 *
 * Visual style intentionally restrained: 2px, soft violet -> white
 * gradient, no glow. Reads as a quiet progress indicator, not a
 * decoration.
 */

import { motion, useScroll, useSpring } from "framer-motion";

export function ScrollProgress() {
  const { scrollYProgress } = useScroll();
  // Smooth the raw scroll value so the bar glides rather than jitters
  // when the user scrolls with a trackpad or wheel.
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 180,
    damping: 30,
    mass: 0.4,
  });

  return (
    <motion.div
      aria-hidden
      style={{ scaleX }}
      className="fixed top-0 left-0 right-0 h-[2px] origin-left z-50 bg-gradient-to-r from-violet-400/80 via-violet-300 to-white pointer-events-none"
    />
  );
}
