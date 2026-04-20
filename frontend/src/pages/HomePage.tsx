import { useEffect, useState } from "react";
import {
  getModel,
  getTelemetryLiveMetrics,
  getTelemetryLogs,
  getSimulationRun,
  getSimulationRuns,
  runSimulation,
  type ScenarioRequest,
  type ServiceOverride,
  type TelemetryLogRecord,
  type SimulationResult,
  type SimulationRunSummary,
} from "../api/client";
import GraphView from "../components/GraphView";
import LogsPanel from "../components/LogsPanel";
import MetricsPanel from "../components/MetricsPanel";
import RunHistoryPanel from "../components/RunHistoryPanel";
import ScenarioForm from "../components/ScenarioForm";

export default function HomePage() {
  const [mode, setMode] = useState<"live" | "simulation">("live");
  const [model, setModel] = useState<any | null>(null);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [runs, setRuns] = useState<SimulationRunSummary[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [componentOverrides, setComponentOverrides] = useState<Record<string, ServiceOverride>>({});
  const [telemetryLogs, setTelemetryLogs] = useState<TelemetryLogRecord[]>([]);
  const [telemetryLoading, setTelemetryLoading] = useState(false);
  const [liveTelemetryMetrics, setLiveTelemetryMetrics] = useState<Record<string, Record<string, number>>>({});
  const [error, setError] = useState<string | null>(null);
  const serviceCount = model?.services?.length ?? 0;
  const architectureReady = serviceCount === 10;

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
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      if (mode === "live") {
        loadModel();
      }
      // Keep telemetry views fresh in both live and simulation modes.
      loadTelemetry();
    }, 3000);
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

  async function loadTelemetry() {
    setTelemetryLoading(true);
    try {
      const [logsResponse, metricsResponse] = await Promise.all([
        getTelemetryLogs(40, selectedService ?? undefined),
        getTelemetryLiveMetrics(30),
      ]);
      setTelemetryLogs(logsResponse.logs);
      setLiveTelemetryMetrics(metricsResponse.services);
    } catch {
      // Keep old telemetry values on transient failures.
    } finally {
      setTelemetryLoading(false);
    }
  }

  return (
    <main className="workspace-shell">
      <aside className="left-panel">
        <section className="panel">
          <h1 className="title">OTel Twin Console</h1>
          <p className="hint">Switch between live monitoring and what-if simulation on the same 10-service topology.</p>
          <p className={`architecture-note ${architectureReady ? "ok" : "warn"}`}>
            Architecture target: 10 services | currently loaded: {serviceCount}
          </p>
          <div className="hero-actions">
            <button
              type="button"
              className={mode === "live" ? "" : "secondary"}
              onClick={() => {
                setMode("live");
                setSelectedService(null);
                setComponentOverrides({});
              }}
            >
              Live Mode
            </button>
            <button
              type="button"
              className={mode === "simulation" ? "" : "secondary"}
              onClick={() => setMode("simulation")}
            >
              Simulation Mode
            </button>
          </div>
          <div className="hero-actions">
            <button type="button" className="secondary" onClick={loadModel}>
              Fetch Existing Model
            </button>
          </div>
        </section>
      </aside>

      <section className="center-panel">
        {error && <p className="error">{error}</p>}
        <GraphView
          model={model}
          mode={mode}
          streamStatus={null}
          simulationResult={result}
          selectedService={selectedService}
          componentOverrides={componentOverrides}
          onComponentOverrideChange={(serviceName, patch) => {
            setComponentOverrides((prev) => ({
              ...prev,
              [serviceName]: patch,
            }));
          }}
          onSelectService={(serviceName) => {
            if (mode === "simulation") {
              setSelectedService(serviceName);
            }
          }}
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

      <aside className="right-panel">
        <MetricsPanel
          result={result}
          mode={mode}
          liveTelemetryMetrics={liveTelemetryMetrics}
          liveSummary={{
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
          }}
        />
        <LogsPanel logs={telemetryLogs} loading={telemetryLoading} selectedService={selectedService} />
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
