import type { SimulationRunSummary } from "../api/client";

type Props = {
  runs: SimulationRunSummary[];
  loading: boolean;
  selectedRunId: string | null;
  onRefresh: () => void;
  onSelectRun: (runId: string) => void;
};

export default function RunHistoryPanel({
  runs,
  loading,
  selectedRunId,
  onRefresh,
  onSelectRun,
}: Props) {
  return (
    <section className="panel">
      <div className="run-history-header">
        <h2>Run History</h2>
        <button type="button" className="secondary" onClick={onRefresh}>
          Refresh Runs
        </button>
      </div>

      {loading && <p>Loading run history...</p>}
      {!loading && runs.length === 0 && <p>No persisted runs found yet.</p>}

      {!loading && runs.length > 0 && (
        <ul className="run-history-list">
          {runs.map((run) => {
            const selected = run.run_id === selectedRunId;
            return (
              <li key={run.run_id} className={selected ? "run-item selected" : "run-item"}>
                <button type="button" className="run-select" onClick={() => onSelectRun(run.run_id)}>
                  <strong>{run.run_id.slice(0, 8)}</strong>
                  <span>
                    Baseline avg: {run.baseline_summary.avg_latency_ms.toFixed(2)} ms | Sim avg: {run.simulated_summary.avg_latency_ms.toFixed(2)} ms
                  </span>
                  <span>
                    Fail rate: {(run.simulated_summary.failure_rate * 100).toFixed(1)}% | Bottlenecks: {run.bottlenecks.length}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
