export type ServiceOverride = {
  latency_multiplier?: number;
  error_rate_override?: number;
  concurrency_limit_override?: number;
};

export type TelemetryDatasource = {
  kind: "prometheus" | "loki" | "jaeger";
  url: string;
  label?: string | null;
  enabled?: boolean;
};

export type MetricsSummary = {
  avg_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  failure_rate: number;
  completed_requests: number;
};

export type SimulationResult = {
  run_id: string;
  baseline_summary: MetricsSummary;
  simulated_summary: MetricsSummary;
  bottlenecks: string[];
  per_service_metrics: Record<string, unknown>;
  per_edge_metrics: Record<string, unknown>;
  timeline: Array<{
    second: number;
    queue_depth_by_service: Record<string, number>;
  }>;
};

export type SimulationRunSummary = {
  run_id: string;
  baseline_summary: MetricsSummary;
  simulated_summary: MetricsSummary;
  bottlenecks: string[];
};

export type TelemetryLogRecord = {
  service_name: string;
  deployment_environment?: string | null;
  timestamp_unix_nano: number;
  severity_text: "TRACE" | "DEBUG" | "INFO" | "WARN" | "ERROR" | "FATAL";
  body: string;
  attributes: Record<string, unknown>;
  trace_id?: string | null;
  span_id?: string | null;
};

export type TelemetryLogsResponse = {
  count: number;
  logs: TelemetryLogRecord[];
};

export type TelemetryLiveMetricsResponse = {
  window_seconds: number;
  services: Record<string, Record<string, number>>;
};

export type TelemetryStatusResponse = {
  source_mode: "none" | "direct" | "external";
  counts: {
    spans: number;
    logs: number;
    metrics: number;
  };
  ingest: {
    last_ingested_at: number | null;
    totals: {
      spans: number;
      logs: number;
      metrics: number;
    };
  };
  sync: Record<string, unknown>;
  datasources?: TelemetryDatasource[];
};

export type TelemetryDatasourceResponse = {
  datasources: TelemetryDatasource[];
  source_mode: "none" | "direct" | "external";
  uses_defaults: boolean;
};

export type EdgeActivityItem = {
  source_service: string;
  target_service: string;
  call_type: string;
  activity_count: number;
  activity_rps: number;
};

export type EdgeActivityResponse = {
  generated_at_unix_nano: number;
  window_seconds: number;
  top_n: number;
  edges: EdgeActivityItem[];
};

export type ScenarioRequest = {
  traffic_multiplier: number;
  duration_seconds: number;
  seed?: number;
  telemetry_influence_strength?: "none" | "low" | "medium" | "high";
  service_overrides: Record<string, ServiceOverride>;
  edge_overrides: Record<string, unknown>;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8010";

export async function getModel() {
  const res = await fetch(`${API_BASE}/model`);
  if (!res.ok) {
    throw new Error("Model is not available yet");
  }
  return res.json();
}

export async function buildModel() {
  const res = await fetch(`${API_BASE}/model/build`, {
    method: "POST",
  });
  if (!res.ok) {
    const message = await res.text();
    throw new Error(message || "Failed to build model");
  }
  return res.json();
}

export async function runSimulation(payload: ScenarioRequest) {
  const res = await fetch(`${API_BASE}/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const message = await res.text();
    throw new Error(message || "Failed to run simulation");
  }
  return res.json();
}

export async function getSimulationRuns(limit = 20): Promise<SimulationRunSummary[]> {
  const res = await fetch(`${API_BASE}/simulate?limit=${limit}`);
  if (!res.ok) {
    throw new Error("Failed to load simulation history");
  }
  const body = await res.json();
  return body.runs ?? [];
}

export async function getSimulationRun(runId: string): Promise<SimulationResult> {
  const res = await fetch(`${API_BASE}/simulate/${runId}`);
  if (!res.ok) {
    throw new Error("Failed to load simulation run");
  }
  return res.json();
}

export async function getEdgeActivity(windowSeconds = 1, topN = 12): Promise<EdgeActivityResponse> {
  const res = await fetch(`${API_BASE}/activity/edges?window_seconds=${windowSeconds}&top_n=${topN}`);
  if (!res.ok) {
    throw new Error("Failed to load edge activity");
  }
  return res.json();
}

export async function getTelemetryLogs(limit = 60, serviceName?: string): Promise<TelemetryLogsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (serviceName) {
    params.set("service_name", serviceName);
  }
  const res = await fetch(`${API_BASE}/telemetry/logs?${params.toString()}`);
  if (!res.ok) {
    throw new Error("Failed to load telemetry logs");
  }
  return res.json();
}

export async function getTelemetryLiveMetrics(windowSeconds = 30): Promise<TelemetryLiveMetricsResponse> {
  const res = await fetch(`${API_BASE}/telemetry/metrics/live?window_seconds=${windowSeconds}`);
  if (!res.ok) {
    throw new Error("Failed to load telemetry metrics");
  }
  return res.json();
}

export async function getTelemetryStatus(): Promise<TelemetryStatusResponse> {
  const res = await fetch(`${API_BASE}/telemetry/status`);
  if (!res.ok) {
    throw new Error("Failed to load telemetry status");
  }
  return res.json();
}

export async function getTelemetryDatasources(): Promise<TelemetryDatasourceResponse> {
  const res = await fetch(`${API_BASE}/telemetry/datasources`);
  if (!res.ok) {
    throw new Error("Failed to load datasources");
  }
  return res.json();
}

export async function saveTelemetryDatasources(datasources: TelemetryDatasource[]) {
  const res = await fetch(`${API_BASE}/telemetry/datasources`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ datasources }),
  });
  if (!res.ok) {
    const message = await res.text();
    throw new Error(message || "Failed to save datasources");
  }
  return res.json();
}
