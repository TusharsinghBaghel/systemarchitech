import { useEffect, useMemo, useState } from "react";
import {
  buildModel,
  getTelemetryDatasources,
  getModel,
  getTelemetryStatus,
  syncTelemetry,
  getTelemetryLiveMetrics,
  getTelemetryLogs,
  getSimulationRun,
  getSimulationRuns,
  runSimulation,
  saveTelemetryDatasources,
  type ScenarioRequest,
  type TelemetryDatasource,
  type ServiceOverride,
  type TelemetryLogRecord,
  type TelemetryStatusResponse,
  type SimulationResult,
  type SimulationRunSummary,
} from "../api/client";
import DatasourcePanel from "../components/DatasourcePanel";
import GraphView from "../components/GraphView";
import LogsPanel from "../components/LogsPanel";
import MetricsPanel from "../components/MetricsPanel";
import RunHistoryPanel from "../components/RunHistoryPanel";
import ScenarioForm from "../components/ScenarioForm";
import type { TelemetryMetricSample } from "../api/client";

export default function HomePage() {
  const [mode, setMode] = useState<"live" | "simulation">("live");
  const [datasourceOpen, setDatasourceOpen] = useState(false);
  const [model, setModel] = useState<any | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [runs, setRuns] = useState<SimulationRunSummary[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [componentOverrides, setComponentOverrides] = useState<Record<string, ServiceOverride>>({});
  const [telemetryLogs, setTelemetryLogs] = useState<TelemetryLogRecord[]>([]);
  const [telemetryStatus, setTelemetryStatus] = useState<TelemetryStatusResponse | null>(null);
  const [datasources, setDatasources] = useState<TelemetryDatasource[]>([]);
  const [datasourceDefaults, setDatasourceDefaults] = useState(true);
  const [telemetryLoading, setTelemetryLoading] = useState(false);
  const [liveTelemetryMetrics, setLiveTelemetryMetrics] = useState<Record<string, Record<string, number>>>({});
  const [liveTelemetryHistory, setLiveTelemetryHistory] = useState<Record<string, TelemetryMetricSample[]>>({});
  const [error, setError] = useState<string | null>(null);
  const serviceCount = model?.services?.length ?? 0;
  const latestLogsByService = useMemo(() => {
    const latest: Record<string, TelemetryLogRecord> = {};
    for (const entry of telemetryLogs) {
      const existing = latest[entry.service_name];
      if (!existing || entry.timestamp_unix_nano > existing.timestamp_unix_nano) {
        latest[entry.service_name] = entry;
      }
    }
    return latest;
  }, [telemetryLogs]);
  const displayedLogs = useMemo(
    () => (selectedService ? telemetryLogs.filter((entry) => entry.service_name === selectedService) : telemetryLogs),
    [telemetryLogs, selectedService]
  );
  const liveSummary = {
    services: model?.services?.length ?? 0,
    edges: model?.edges?.length ?? 0,
    avgLatencyMs:
      model?.services?.length > 0
        ? model.services.reduce((acc: number, svc: any) => acc + svc.latency_distribution.mean, 0) /
          model.services.length
        : 0,
    avgErrorRate:
      model?.services?.length > 0
        ? model.services.reduce((acc: number, svc: any) => acc + svc.error_rate, 0) / model.services.length
        : 0,
    avgThroughputRps:
      model?.services?.length > 0
        ? model.services.reduce((acc: number, svc: any) => acc + svc.throughput_rps, 0) / model.services.length
        : 0,
  };

  async function loadModel() {
    try {
      const nextModel = await getModel();
      setModel(nextModel);
    } catch {
      // Keep last good model to avoid blanking the canvas on transient failures.
    }
  }

  useEffect(() => {
    loadModel();
    loadRuns();
    loadTelemetry();
    loadDatasources();
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      if (mode === "live") {
        loadModel();
      }
      // Keep telemetry views fresh in both live and simulation modes.
      loadTelemetry();
    }, 2000);
    return () => clearInterval(id);
  }, [mode, selectedService]);

  async function loadRuns() {
    setRunsLoading(true);
    try {
      const history = await getSimulationRuns(30);
      setRuns(history);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setRunsLoading(false);
    }
  }

  async function handleSelectRun(runId: string) {
    setError(null);
    try {
      const selected = await getSimulationRun(runId);
      setSelectedRunId(runId);
      setResult(selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  async function handleRun(scenario: ScenarioRequest) {
    setError(null);
    try {
      const simulation = await runSimulation(scenario);
      setResult(simulation);
      setSelectedRunId(simulation.run_id);
      await loadRuns();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  async function handleBuildNow() {
    setError(null);
    try {
      await buildModel();
      await loadModel();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    }
  }

  async function loadTelemetry() {
    setTelemetryLoading(true);
    try {
      await syncTelemetry();
      const [logsResponse, metricsResponse, statusResponse] = await Promise.all([
        getTelemetryLogs(120),
        getTelemetryLiveMetrics(3),
        getTelemetryStatus(),
      ]);
      const sampledAt = Date.now();
      setTelemetryLogs(logsResponse.logs);
      setLiveTelemetryMetrics(metricsResponse.services);
      setLiveTelemetryHistory((prev) => {
        const next = { ...prev };
        for (const [serviceName, metrics] of Object.entries(metricsResponse.services)) {
          const history = next[serviceName] ?? [];
          next[serviceName] = [...history.slice(-19), { timestampMs: sampledAt, metrics }];
        }
        return next;
      });
      setTelemetryStatus(statusResponse);
    } catch {
      // Keep old telemetry values on transient failures.
    } finally {
      setTelemetryLoading(false);
    }
  }

  async function loadDatasources() {
    try {
      const response = await getTelemetryDatasources();
      setDatasources(response.datasources);
      setDatasourceDefaults(response.uses_defaults);
    } catch {
      // Keep existing links if the datasource endpoint is temporarily unavailable.
    }
  }

  async function handleSaveDatasources(nextDatasources: TelemetryDatasource[]) {
    setError(null);
    try {
      const response = await saveTelemetryDatasources(nextDatasources);
      setDatasources(response.datasources ?? nextDatasources);
      setDatasourceDefaults(false);
      await loadTelemetry();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      throw err;
    }
  }

  return (
    <main className="workspace-shell">
      <aside className="left-panel">
        <section className="panel">
          <h1 className="title brand-title">
            <span className="brand-twin">Twin</span><span className="brand-fana">Fana</span>
          </h1>
          <p className="architecture-note">Services loaded: {serviceCount}</p>
          <div className="hero-actions">
            <button type="button" onClick={() => setDatasourceOpen(true)}>
              Datasource
            </button>
            <div className="mode-toggle" role="group" aria-label="Mode">
              <button
                type="button"
                className={mode === "live" ? "is-active" : ""}
                onClick={() => {
                  setMode("live");
                  setSelectedService(null);
                  setComponentOverrides({});
                }}
              >
                Live
              </button>
              <button
                type="button"
                className={mode === "simulation" ? "is-active" : ""}
                onClick={() => setMode("simulation")}
              >
                Simulation
              </button>
            </div>
          </div>
          <div className="hero-actions build-refresh-row">
            <button type="button" onClick={handleBuildNow}>
              Build Now
            </button>
            <button type="button" className="secondary" onClick={loadModel}>
              Refresh
            </button>
          </div>
        </section>
        <MetricsPanel
          result={result}
          panelType="live"
          liveTelemetryMetrics={liveTelemetryMetrics}
          liveSummary={liveSummary}
        />
        <LogsPanel logs={displayedLogs} loading={telemetryLoading} selectedService={selectedService} />
      </aside>

      <section className="center-panel">
        {error && <p className="error">{error}</p>}
        <GraphView
          model={model}
          mode={mode}
          telemetryStatus={telemetryStatus}
          latestLogsByService={latestLogsByService}
          liveTelemetryMetrics={liveTelemetryMetrics}
          liveTelemetryHistory={liveTelemetryHistory}
          simulationResult={result}
          selectedService={selectedService}
          componentOverrides={componentOverrides}
          onComponentOverrideChange={(serviceName, patch) => {
            setComponentOverrides((prev) => ({
              ...prev,
              [serviceName]: patch,
            }));
          }}
          onSelectService={(serviceName) => setSelectedService(serviceName)}
          onClearSelection={() => setSelectedService(null)}
          headerControls={
            mode === "simulation" ? (
              <ScenarioForm
                onRun={handleRun}
                componentOverrides={componentOverrides}
                serviceNames={(model?.services ?? []).map((service: { service_name: string }) => service.service_name)}
              />
            ) : null
          }
        />
      </section>

      {datasourceOpen && (
        <DatasourcePanel
          datasources={datasources}
          sourceMode={telemetryStatus?.source_mode ?? "external"}
          usesDefaults={datasourceDefaults}
          onLoad={loadDatasources}
          onSave={handleSaveDatasources}
          onClose={() => setDatasourceOpen(false)}
        />
      )}

      <aside className="right-panel">
        <MetricsPanel
          result={result}
          panelType="simulation"
          liveTelemetryMetrics={liveTelemetryMetrics}
          liveSummary={liveSummary}
        />
        <RunHistoryPanel
          runs={runs}
          loading={runsLoading}
          selectedRunId={selectedRunId}
          onRefresh={loadRuns}
          onSelectRun={handleSelectRun}
        />
      </aside>
    </main>
  );
}
