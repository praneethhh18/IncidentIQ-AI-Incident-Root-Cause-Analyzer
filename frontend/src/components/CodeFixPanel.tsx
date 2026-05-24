"use client";

import { useState } from "react";
import {
  Boxes,
  Check,
  ClipboardCopy,
  FileCode2,
  Github,
  Loader2,
  ShieldCheck,
  ShieldAlert,
  Sparkles,
  Terminal,
  X,
} from "lucide-react";

import { api } from "@/lib/api";
import type { AnalyzeResponse, CodeFix, CodeFixSubStep } from "@/lib/types";
import { cn } from "@/lib/utils";
import { FadeItem } from "./motion-primitives";

const DEFAULT_REPO = "https://github.com/praneethhh18/FashionAura.git";

const SUB_STEP_ICON: Record<string, typeof Sparkles> = {
  clone: Github,
  locate: Boxes,
  diagnose: FileCode2,
  patch: Terminal,
  verify: ShieldCheck,
};

export function CodeFixPanel({
  analysis,
  onUpdated,
}: {
  analysis: AnalyzeResponse;
  onUpdated: (next: AnalyzeResponse) => void;
}) {
  const existing = analysis.code_fix ?? null;
  const [repoUrl, setRepoUrl] = useState<string>(existing?.repo_url ?? DEFAULT_REPO);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    if (!repoUrl.trim()) {
      setError("Paste a Git URL first.");
      return;
    }
    setRunning(true);
    setError(null);
    try {
      const updated = await api.codeFix(analysis.incident_id, repoUrl.trim());
      onUpdated(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="card-pad">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="size-4 text-brand-300" />
        <h3 className="section-title">Code-aware fix</h3>
        {existing ? (
          <span
            className={cn(
              "ml-auto chip text-[11px]",
              existing.verify_passed
                ? "bg-emerald-500/10 text-emerald-200 border-emerald-500/30"
                : "bg-amber-500/10 text-amber-200 border-amber-500/30",
            )}
          >
            {existing.verify_passed ? (
              <>
                <ShieldCheck className="size-3" /> verified
              </>
            ) : (
              <>
                <ShieldAlert className="size-3" /> patch needs review
              </>
            )}
          </span>
        ) : null}
      </div>

      <p className="text-[12.5px] text-ink-400 mb-3">
        Point the agent at your repo. It locates the suspect file, generates
        a unified diff, and lints the patched code. The output is a real
        <span className="text-ink-200"> git apply</span>-ready diff.
      </p>

      <div className="flex flex-wrap gap-2 mb-3">
        <div className="flex items-center gap-2 flex-1 min-w-[260px]">
          <Github className="size-4 text-ink-400" />
          <input
            type="url"
            spellCheck={false}
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/owner/repo.git"
            className="flex-1 bg-ink-900/60 border border-white/[0.07] rounded-md px-2.5 py-1.5 text-[12.5px] text-ink-100 font-mono focus:outline-none focus:border-brand-500/40"
          />
        </div>
        <button
          onClick={run}
          disabled={running}
          className="btn-primary px-3 py-1.5 text-[12.5px] disabled:opacity-60"
        >
          {running ? (
            <>
              <Loader2 className="size-3.5 animate-spin" /> Running pipeline…
            </>
          ) : existing ? (
            <>
              <Sparkles className="size-3.5" /> Regenerate
            </>
          ) : (
            <>
              <Sparkles className="size-3.5" /> Generate code fix
            </>
          )}
        </button>
      </div>

      {error ? (
        <div className="mb-3 rounded-md border border-red-500/30 bg-red-500/10 text-red-200 px-2.5 py-2 text-[12.5px]">
          <X className="inline size-3.5 mr-1 align-text-bottom" />
          {error}
        </div>
      ) : null}

      {existing ? <CodeFixResult fix={existing} /> : null}
    </div>
  );
}

function CodeFixResult({ fix }: { fix: CodeFix }) {
  return (
    <FadeItem>
      <div className="space-y-4 mt-2">
        <div className="rounded-md border border-white/[0.07] bg-ink-900/40 p-3">
          <div className="flex items-center gap-2 flex-wrap mb-2">
            <span className="chip">
              <FileCode2 className="size-3" /> {fix.file_path}
            </span>
            <span className="chip">
              confidence {Math.round(fix.confidence * 100)}%
            </span>
            <span className="chip">
              {Math.max(1, Math.round(fix.duration_ms / 100) / 10).toFixed(1)}s
            </span>
            <span className="ml-auto text-[11px] text-ink-500 font-mono truncate max-w-[220px]">
              {fix.repo_url}
            </span>
          </div>
          <p className="text-[13px] text-ink-300 leading-relaxed">
            {fix.rationale}
          </p>
        </div>

        <SubStepStrip steps={fix.sub_steps} />

        <DiffBlock diff={fix.diff} />

        <VerifyBlock
          passed={fix.verify_passed}
          output={fix.verify_output}
        />
      </div>
    </FadeItem>
  );
}

function SubStepStrip({ steps }: { steps: CodeFixSubStep[] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
      {steps.map((step, i) => {
        const Icon = SUB_STEP_ICON[step.name] ?? Sparkles;
        return (
          <div
            key={`${step.name}-${i}`}
            className="rounded-md border border-white/[0.06] bg-ink-900/40 px-2.5 py-2"
          >
            <div className="flex items-center gap-1.5 text-[10.5px] uppercase tracking-wider text-ink-400 font-semibold">
              <Icon className="size-3" /> {step.name}
            </div>
            <div className="mt-1 text-[12px] text-ink-200 leading-snug">
              {step.summary}
            </div>
            <div className="mt-1 text-[10.5px] text-ink-500 font-mono">
              {step.duration_ms}ms
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DiffBlock({ diff }: { diff: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(diff);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  };

  const lines = diff.split("\n");

  return (
    <div className="rounded-md border border-white/[0.07] bg-ink-950/70 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-white/[0.05] bg-ink-900/60">
        <span className="text-[10.5px] uppercase tracking-wider text-ink-400 font-semibold">
          Unified diff
        </span>
        <button
          onClick={copy}
          className="inline-flex items-center gap-1.5 text-[11px] text-ink-300 hover:text-ink-50 transition"
        >
          {copied ? (
            <>
              <Check className="size-3" /> copied
            </>
          ) : (
            <>
              <ClipboardCopy className="size-3" /> copy
            </>
          )}
        </button>
      </div>
      <pre className="text-[12px] leading-[1.55] font-mono overflow-x-auto max-h-[420px] p-3">
        {lines.map((line, i) => {
          const cls = line.startsWith("+++") || line.startsWith("---")
            ? "text-ink-300"
            : line.startsWith("+")
              ? "text-emerald-300"
              : line.startsWith("-")
                ? "text-red-300"
                : line.startsWith("@@")
                  ? "text-brand-300"
                  : "text-ink-400";
          return (
            <span key={i} className={cn("block whitespace-pre", cls)}>
              {line || " "}
            </span>
          );
        })}
      </pre>
    </div>
  );
}

function VerifyBlock({ passed, output }: { passed: boolean; output: string }) {
  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2 text-[12px]",
        passed
          ? "border-emerald-500/30 bg-emerald-500/[0.06] text-emerald-100"
          : "border-amber-500/30 bg-amber-500/[0.06] text-amber-100",
      )}
    >
      <div className="flex items-center gap-1.5 font-semibold mb-1">
        {passed ? (
          <>
            <ShieldCheck className="size-3.5" /> Verify sub-agent: passed
          </>
        ) : (
          <>
            <ShieldAlert className="size-3.5" /> Verify sub-agent: needs review
          </>
        )}
      </div>
      <pre className="font-mono text-[11.5px] text-ink-300 whitespace-pre-wrap break-words max-h-32 overflow-auto">
        {output || "(no output)"}
      </pre>
    </div>
  );
}
