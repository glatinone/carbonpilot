export function StatCard({
  label,
  value,
  sub,
  accent = "text-white",
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}) {
  return (
    <div className="card card-pad">
      <p className="label">{label}</p>
      <p className={`metric mt-2 text-2xl font-semibold tracking-tight ${accent}`}>{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="card card-pad py-12 text-center">
      <p className="text-sm font-medium text-slate-300">{title}</p>
      <p className="mt-1 text-xs text-slate-500">{hint}</p>
    </div>
  );
}

export function Skeleton({ className = "h-24" }: { className?: string }) {
  return <div className={`animate-pulse rounded-xl bg-ink-900/70 ${className}`} />;
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="card border-signal-rose/40 bg-signal-rose/5 p-4">
      <p className="text-sm font-medium text-signal-rose">Could not reach the API</p>
      <p className="mt-1 text-xs text-slate-400">{message}</p>
      <p className="mt-2 text-xs text-slate-500">
        Start the backend with{" "}
        <code className="rounded bg-ink-950 px-1.5 py-0.5 font-mono text-[11px] text-slate-300">
          python -m uvicorn app.main:app --port 8008
        </code>
      </p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-ghost mt-3">
          Retry
        </button>
      )}
    </div>
  );
}
