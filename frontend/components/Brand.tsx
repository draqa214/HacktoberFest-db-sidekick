export default function Brand({ compact = false }: { compact?: boolean }) {
  return <div className="sidekick-brand">
    <span className="sidekick-mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 4 14 4 14 0V6M5 12v6c0 4 14 4 14 0v-6"/></svg></span>
    {!compact && <span>Database <strong>Sidekick</strong><small>Your database, in plain English.</small></span>}
  </div>;
}
