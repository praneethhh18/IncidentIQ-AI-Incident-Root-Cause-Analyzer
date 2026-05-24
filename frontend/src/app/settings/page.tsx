"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Check,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  Loader2,
  Lock,
  Plug,
  Plus,
  Trash2,
  X,
} from "lucide-react";

import { api } from "@/lib/api";
import { ensureSessionId } from "@/lib/session";
import { cn } from "@/lib/utils";

/**
 * Settings page - lets a visitor at the public IncidentIQ deployment
 * paste their own Datadog / Grafana / New Relic credentials. Everything
 * stored server-side keyed by a per-browser session id (no shared
 * state between visitors). The backend integrations check the session
 * credential store first and fall back to .env only when nothing's
 * configured for the current browser.
 *
 * Reads as a normal SaaS "Integrations" page - any team can plug their
 * own stack in without us touching the deploy.
 */

type ProviderId = "datadog" | "grafana" | "newrelic";

interface SessionStatus {
  datadog: boolean;
  grafana: boolean;
  newrelic: boolean;
}

export default function SettingsPage() {
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [openModal, setOpenModal] = useState<ProviderId | null>(null);
  const [busy, setBusy] = useState<ProviderId | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await ensureSessionId();
      try {
        const res = await api.sessionStatus();
        if (!cancelled) setStatus(res.status);
      } catch {
        if (!cancelled)
          setStatus({ datadog: false, grafana: false, newrelic: false });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshStatus = async () => {
    const res = await api.sessionStatus();
    setStatus(res.status);
  };

  const disconnect = async (provider: ProviderId) => {
    setBusy(provider);
    try {
      if (provider === "datadog") await api.clearDatadogCreds();
      if (provider === "grafana") await api.clearGrafanaCreds();
      if (provider === "newrelic") await api.clearNewRelicCreds();
      await refreshStatus();
    } finally {
      setBusy(null);
    }
  };

  return (
    <section className="mx-auto max-w-5xl px-4 sm:px-6 py-6 sm:py-10">
      <header className="mb-6 sm:mb-8">
        <nav className="flex items-center gap-1.5 text-[11.5px] text-ink-400 font-medium">
          <Link href="/" className="hover:text-ink-50 transition">
            IncidentIQ
          </Link>
          <span className="text-ink-700">/</span>
          <span className="text-ink-200">Settings</span>
        </nav>
        <h1 className="mt-3 text-2xl sm:text-3xl font-semibold tracking-tight text-ink-50">
          Connect your stack
        </h1>
        <p className="mt-2 text-[13.5px] sm:text-base text-ink-300 max-w-2xl">
          Paste your monitoring keys once and IncidentIQ will pull logs straight
          from your account. Credentials are stored per browser session
          (server-side, never echoed back), so you don&apos;t share keys with
          anyone else on this deployment.
        </p>
      </header>

      <div className="space-y-3">
        <ProviderCard
          provider="datadog"
          name="Datadog"
          icon="🐶"
          purpose="Pulls live error logs via the Logs Search API. Powers the Datadog tab on the dashboard and Watch Mode auto-detection."
          docsHref="https://docs.datadoghq.com/account_management/api-app-keys/"
          docsLabel="Create API + App keys"
          connected={status?.datadog ?? false}
          busy={busy === "datadog"}
          onConnect={() => setOpenModal("datadog")}
          onDisconnect={() => disconnect("datadog")}
        />
        <ProviderCard
          provider="grafana"
          name="Grafana / Loki"
          icon="📊"
          purpose="Pulls live error logs via the Loki HTTP query API. Point Grafana URL at the Loki API base."
          docsHref="https://grafana.com/docs/grafana-cloud/account-management/cloud-access-policies/"
          docsLabel="Create an access policy"
          connected={status?.grafana ?? false}
          busy={busy === "grafana"}
          onConnect={() => setOpenModal("grafana")}
          onDisconnect={() => disconnect("grafana")}
        />
        <ProviderCard
          provider="newrelic"
          name="New Relic"
          icon="🟢"
          purpose="Pulls live error logs via the NRQL HTTP API (NerdGraph)."
          docsHref="https://docs.newrelic.com/docs/apis/intro-apis/new-relic-api-keys/"
          docsLabel="Create a User key"
          connected={status?.newrelic ?? false}
          busy={busy === "newrelic"}
          onConnect={() => setOpenModal("newrelic")}
          onDisconnect={() => disconnect("newrelic")}
        />
      </div>

      <div className="mt-8 rounded-lg border border-white/[0.06] bg-white/[0.02] p-4 text-[12.5px] text-ink-400 leading-relaxed">
        <div className="flex items-center gap-2 mb-1.5 text-ink-200 font-medium">
          <Lock className="size-3.5" /> How credentials are handled
        </div>
        Stored in-memory on the backend, keyed by your per-browser session
        id. Sessions TTL out after 24h without activity. The status endpoint
        returns booleans only — your raw keys are never sent back to the
        browser after you paste them. Self-hosting? Drop the same values
        into <code className="font-mono text-[11.5px] text-ink-300">backend/.env</code>{" "}
        as a fallback for server-to-server flows.
      </div>

      {openModal === "datadog" ? (
        <DatadogConnectModal
          onClose={() => setOpenModal(null)}
          onSaved={async () => {
            await refreshStatus();
            setOpenModal(null);
          }}
        />
      ) : null}
      {openModal === "grafana" ? (
        <GrafanaConnectModal
          onClose={() => setOpenModal(null)}
          onSaved={async () => {
            await refreshStatus();
            setOpenModal(null);
          }}
        />
      ) : null}
      {openModal === "newrelic" ? (
        <NewRelicConnectModal
          onClose={() => setOpenModal(null)}
          onSaved={async () => {
            await refreshStatus();
            setOpenModal(null);
          }}
        />
      ) : null}
    </section>
  );
}

function ProviderCard({
  provider,
  name,
  icon,
  purpose,
  docsHref,
  docsLabel,
  connected,
  busy,
  onConnect,
  onDisconnect,
}: {
  provider: ProviderId;
  name: string;
  icon: string;
  purpose: string;
  docsHref: string;
  docsLabel: string;
  connected: boolean;
  busy: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border px-4 sm:px-5 py-3.5 sm:py-4 flex items-center justify-between gap-4 flex-wrap transition",
        connected
          ? "border-emerald-500/30 bg-emerald-500/[0.04]"
          : "border-white/[0.08] bg-white/[0.02]",
      )}
    >
      <div className="flex items-start gap-3 min-w-0">
        <div className="shrink-0 size-10 rounded-lg grid place-items-center text-lg bg-white/[0.05] border border-white/[0.06]">
          {icon}
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[14px] sm:text-[15px] font-semibold text-ink-50">
            {name}
            {connected ? (
              <span className="inline-flex items-center gap-1 chip text-[10.5px] bg-emerald-500/15 text-emerald-200 border-emerald-500/30">
                <CheckCircle2 className="size-3" /> connected
              </span>
            ) : null}
          </div>
          <div className="text-[12px] text-ink-400 mt-0.5 leading-snug">
            {purpose}
          </div>
          <a
            href={docsHref}
            target="_blank"
            rel="noreferrer"
            className="mt-1 inline-flex items-center gap-1 text-[11.5px] text-brand-300 hover:text-brand-200 transition"
          >
            {docsLabel} <ExternalLink className="size-3" />
          </a>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {connected ? (
          <button
            onClick={onDisconnect}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium bg-white/[0.04] text-ink-200 border border-white/[0.10] hover:bg-red-500/10 hover:text-red-200 hover:border-red-500/30 disabled:opacity-60 transition"
          >
            {busy ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <Trash2 className="size-3" />
            )}
            Disconnect
          </button>
        ) : (
          <button
            onClick={onConnect}
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] font-medium bg-brand-500/15 text-brand-100 border border-brand-500/40 hover:bg-brand-500/25 transition"
          >
            <Plus className="size-3.5" />
            Connect
            <ChevronRight className="size-3.5 -mr-1" />
          </button>
        )}
      </div>
    </div>
  );
}

// ── Modals ────────────────────────────────────────────────────────────

function Modal({
  title,
  subtitle,
  onClose,
  children,
}: {
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-ink-950/80 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-white/[0.10] bg-ink-900 shadow-glow"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 px-5 py-4 border-b border-white/[0.06]">
          <div>
            <div className="text-[15px] font-semibold text-ink-50">{title}</div>
            {subtitle ? (
              <div className="text-[12px] text-ink-400 mt-0.5">{subtitle}</div>
            ) : null}
          </div>
          <button
            onClick={onClose}
            className="size-7 grid place-items-center rounded-md text-ink-400 hover:text-ink-100 hover:bg-white/[0.06] transition"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

function DatadogConnectModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [apiKey, setApiKey] = useState("");
  const [appKey, setAppKey] = useState("");
  const [site, setSite] = useState("datadoghq.com");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await ensureSessionId();
      await api.setDatadogCreds({
        api_key: apiKey.trim(),
        app_key: appKey.trim(),
        site: site.trim() || "datadoghq.com",
      });
      await onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="Connect Datadog"
      subtitle="Paste an API key and App key from your Datadog org."
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-3">
        <Field
          label="API Key"
          hint="Organization Settings → API Keys"
          value={apiKey}
          onChange={setApiKey}
          placeholder="abc123…"
          autoFocus
        />
        <Field
          label="Application Key"
          hint="Organization Settings → Application Keys"
          value={appKey}
          onChange={setAppKey}
          placeholder="ddapp_…"
        />
        <Field
          label="Datadog site"
          hint="datadoghq.com (US1), us5.datadoghq.com, datadoghq.eu, etc."
          value={site}
          onChange={setSite}
          placeholder="datadoghq.com"
        />
        <SubmitRow
          submitting={submitting}
          error={error}
          submitLabel="Save & connect"
        />
      </form>
    </Modal>
  );
}

function GrafanaConnectModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [url, setUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await ensureSessionId();
      await api.setGrafanaCreds({
        url: url.trim().replace(/\/$/, ""),
        api_key: apiKey.trim(),
      });
      await onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="Connect Grafana / Loki"
      subtitle="Point at your Loki query URL (the part before /loki/api/v1)."
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-3">
        <Field
          label="Loki URL"
          hint="e.g. https://logs-prod-006.grafana.net"
          value={url}
          onChange={setUrl}
          placeholder="https://logs-prod-XXX.grafana.net"
          autoFocus
        />
        <Field
          label="Access token"
          hint="Grafana Cloud Access Policy token with logs:read scope"
          value={apiKey}
          onChange={setApiKey}
          placeholder="glsa_…"
        />
        <SubmitRow
          submitting={submitting}
          error={error}
          submitLabel="Save & connect"
        />
      </form>
    </Modal>
  );
}

function NewRelicConnectModal({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [userKey, setUserKey] = useState("");
  const [accountId, setAccountId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await ensureSessionId();
      await api.setNewRelicCreds({
        user_key: userKey.trim(),
        account_id: accountId.trim(),
      });
      await onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="Connect New Relic"
      subtitle="User key powers NerdGraph queries against your account."
      onClose={onClose}
    >
      <form onSubmit={submit} className="space-y-3">
        <Field
          label="User Key"
          hint="API keys → User key (NRAK-…)"
          value={userKey}
          onChange={setUserKey}
          placeholder="NRAK-…"
          autoFocus
        />
        <Field
          label="Account ID"
          hint="Numeric account id from the URL bar"
          value={accountId}
          onChange={setAccountId}
          placeholder="1234567"
        />
        <SubmitRow
          submitting={submitting}
          error={error}
          submitLabel="Save & connect"
        />
      </form>
    </Modal>
  );
}

function Field({
  label,
  hint,
  value,
  onChange,
  placeholder,
  autoFocus,
}: {
  label: string;
  hint: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
}) {
  return (
    <div>
      <label className="block text-[11.5px] uppercase tracking-wider text-ink-400 font-medium mb-1.5">
        {label}
      </label>
      <input
        type="text"
        spellCheck={false}
        autoFocus={autoFocus}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-ink-950/60 border border-white/[0.10] rounded-md px-2.5 py-2 text-[12.5px] text-ink-100 font-mono focus:outline-none focus:border-brand-500/50"
      />
      <div className="mt-1 text-[10.5px] text-ink-500">{hint}</div>
    </div>
  );
}

function SubmitRow({
  submitting,
  error,
  submitLabel,
}: {
  submitting: boolean;
  error: string | null;
  submitLabel: string;
}) {
  return (
    <div className="pt-1">
      {error ? (
        <div className="mb-2 text-[11.5px] text-red-300">{error}</div>
      ) : null}
      <button
        type="submit"
        disabled={submitting}
        className="w-full inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium bg-brand-500/20 text-brand-100 border border-brand-500/40 hover:bg-brand-500/30 disabled:opacity-60 transition"
      >
        {submitting ? (
          <Loader2 className="size-3.5 animate-spin" />
        ) : (
          <Check className="size-3.5" />
        )}
        {submitLabel}
      </button>
    </div>
  );
}
