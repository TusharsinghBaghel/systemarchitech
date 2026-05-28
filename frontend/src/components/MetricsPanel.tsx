import type { SimulationResult } from "../api/client";

type LiveSummary = {
  services: number;
  edges: number;
  avgLatencyMs: number;
  avgErrorRate: number;
  avgThroughputRps: number;
};

type Props = {
  result: SimulationResult | null;
  liveSummary: LiveSummary;
  liveTelemetryMetrics: Record<string, Record<string, number>>;
  panelType: "live" | "simulation";
};

function metricCard(label: string, value: string) {
  return (
    <div className="metric-card" key={label}>
      <span className="metric-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function MetricsPanel({ result, liveSummary, liveTelemetryMetrics, panelType }: Props) {
  const liveCards = [
    metricCard("Modeled Services", String(liveSummary.services)),
    metricCard("Edges", String(liveSummary.edges)),
    metricCard("Avg Latency", `${liveSummary.avgLatencyMs.toFixed(1)} ms`),
    metricCard("Avg Error", `${(liveSummary.avgErrorRate * 100).toFixed(2)}%`),
    metricCard("Avg Throughput", `${liveSummary.avgThroughputRps.toFixed(1)} rps`),
  ];

  const simCards =
    result === null
      ? []
      : [
          metricCard("Avg Latency", `${result.simulated_summary.avg_latency_ms.toFixed(1)} ms`),
          metricCard("P95 Latency", `${result.simulated_summary.p95_latency_ms.toFixed(1)} ms`),
          metricCard("P99 Latency", `${result.simulated_summary.p99_latency_ms.toFixed(1)} ms`),
          metricCard("Failure Rate", `${(result.simulated_summary.failure_rate * 100).toFixed(2)}%`),
          metricCard("Completed", String(result.simulated_summary.completed_requests)),
        ];

  const telemetryServiceCount = Object.keys(liveTelemetryMetrics).length;
  const telemetryCards =
    telemetryServiceCount === 0
      ? []
      : [
          metricCard("Metric-Active Services", String(telemetryServiceCount)),
          metricCard("Avg CPU", `${avgMetric(liveTelemetryMetrics, "cpu.utilization").toFixed(2)}`),
          metricCard("Avg Memory", `${avgMetric(liveTelemetryMetrics, "memory.utilization").toFixed(2)}`),
          metricCard("Avg Queue", `${avgMetric(liveTelemetryMetrics, "queue.depth").toFixed(1)}`),
        ];

  return (
    <section className="panel">
      {panelType === "live" && (
        <>
          <h2>Live Monitoring</h2>
          <h3>Live System</h3>
          <div className="metrics-grid">{liveCards}</div>

          <h3>Live Telemetry Signals</h3>
          {telemetryCards.length === 0 && <p>No live telemetry metrics available yet.</p>}
          {telemetryCards.length > 0 && <div className="metrics-grid">{telemetryCards}</div>}
        </>
      )}

      {panelType === "simulation" && (
        <>
          <h2>Simulation Monitoring</h2>
          <h3>Simulation Result</h3>
          {result === null && <p>No simulation run selected yet.</p>}
          {result !== null && <div className="metrics-grid">{simCards}</div>}
        </>
      )}
    </section>
  );
}

function avgMetric(services: Record<string, Record<string, number>>, metricName: string): number {
  const values = Object.values(services)
    .map((serviceMetrics) => serviceMetrics[metricName])
    .filter((value): value is number => typeof value === "number");

  if (values.length === 0) {
    return 0;
  }
  return values.reduce((acc, value) => acc + value, 0) / values.length;
}
