import type { TelemetryLogRecord } from "../api/client";

type Props = {
  logs: TelemetryLogRecord[];
  loading: boolean;
  selectedService: string | null;
};

function formatTimestamp(nanos: number): string {
  const ms = Math.floor(nanos / 1_000_000);
  return new Date(ms).toLocaleTimeString();
}

export default function LogsPanel({ logs, loading, selectedService }: Props) {
  return (
    <section className="panel">
      <div className="run-history-header">
        <h2 className="split-title"><span>Recent</span> Logs</h2>
        <span className="hint">{selectedService ? `service: ${selectedService}` : "all services"}</span>
      </div>
      {loading && <p className="hint">Loading logs...</p>}
      {!loading && logs.length === 0 && <p className="hint">No logs available yet.</p>}
      <ul className="logs-list">
        {logs.map((entry, idx) => (
          <li key={`${entry.service_name}-${entry.timestamp_unix_nano}-${idx}`} className="log-item">
            <div className="log-item-head">
              <strong>{entry.service_name}</strong>
              <span className={`log-level ${entry.severity_text.toLowerCase()}`}>{entry.severity_text}</span>
            </div>
            <div className="log-item-body">{entry.body}</div>
            <div className="log-item-meta">{formatTimestamp(entry.timestamp_unix_nano)}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}
