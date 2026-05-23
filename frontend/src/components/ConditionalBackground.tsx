"use client";

/**
 * ConditionalBackground. Renders the full motion-and-shader aurora only
 * on the marketing landing page. App pages (dashboard, incidents) get a
 * minimal, calm background so the working surface stays the focus.
 *
 * This is the standard split used by Linear, Vercel, Resend: marketing
 * = expressive, product = restrained.
 */

import { usePathname } from "next/navigation";

import { SpectraNoise } from "./SpectraNoise";

export function ConditionalBackground() {
  const pathname = usePathname();
  const isLanding = pathname === "/";

  if (isLanding) {
    return (
      <div className="aurora-layer" aria-hidden>
        <div className="aurora-canvas-wrap">
          <SpectraNoise
            hueShift={-25}
            noiseIntensity={0.08}
            scanlineIntensity={0}
            scanlineFrequency={0}
            warpAmount={0.55}
            speed={0.55}
            resolutionScale={0.7}
          />
        </div>
        <div className="aurora-fade" />
      </div>
    );
  }

  // App pages: solid dark + a subtle dot grid for texture, nothing more.
  return <div className="app-bg" aria-hidden />;
}
