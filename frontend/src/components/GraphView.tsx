import { type MouseEvent as ReactMouseEvent, type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import type { ServiceOverride, TelemetryLogRecord, TelemetryMetricSample, TelemetryStatusResponse } from "../api/client";
import ReactFlow, {
  BaseEdge,
  Background,
  BackgroundVariant,
  Controls,
  Edge,
  EdgeProps,
  MarkerType,
  MiniMap,
  Node,
  getBezierPath,
  useEdgesState,
  useNodesState,
} from "reactflow";
import "reactflow/dist/style.css";

type Model = {
  services?: Array<{
    service_name: string;
    latency_distribution: { mean: number; p95: number };
    error_rate: number;
    throughput_rps: number;
  }>;
  edges?: Array<{
    source_service: string;
    target_service: string;
    call_probability: number;
    error_rate?: number;
    call_type?: "http" | "db" | "rpc" | "kafka" | "other";
  }>;
};

type SimulationResult = {
  per_service_metrics?: Record<string, unknown>;
};

const SPAN_COLOR_BY_TYPE: Record<string, string> = {
  http: "#62c281",
  db: "#6ea8d9",
  rpc: "#d3b45f",
  kafka: "#9aa4ad",
  other: "#737f8b",
};

function spanColor(callType?: string): string {
  if (!callType) {
    return SPAN_COLOR_BY_TYPE.other;
  }
  return SPAN_COLOR_BY_TYPE[callType] ?? SPAN_COLOR_BY_TYPE.other;
}

function SpanTravelEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  label,
  data,
}: EdgeProps<{ callType?: string; animate?: boolean }>) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const callType = data?.callType ?? "other";
  const stroke = spanColor(callType);
  const animate = Boolean(data?.animate);
  const pathId = `span-path-${id.replace(/[^a-zA-Z0-9_-]/g, "_")}`;

  return (
    <g>
      <path id={pathId} d={edgePath} fill="none" stroke="transparent" strokeWidth={1} />
      <BaseEdge path={edgePath} markerEnd={markerEnd} style={{ stroke, strokeWidth: 2 }} />
      {typeof label === "string" && (
        <text x={labelX} y={labelY} className="edge-flow-label">
          {label}
        </text>
      )}
      {animate && (
        <>
          <circle r="3.6" fill={stroke} opacity="0.95">
            <animateMotion dur="2.2s" repeatCount="indefinite" rotate="auto">
              <mpath href={`#${pathId}`} />
            </animateMotion>
          </circle>
          <circle r="2.8" fill={stroke} opacity="0.7">
            <animateMotion dur="2.2s" begin="1.1s" repeatCount="indefinite" rotate="auto">
              <mpath href={`#${pathId}`} />
            </animateMotion>
          </circle>
        </>
      )}
    </g>
  );
}

type Props = {
  model: Model | null;
  mode: "live" | "simulation";
  telemetryStatus: TelemetryStatusResponse | null;
  latestLogsByService: Record<string, TelemetryLogRecord>;
  liveTelemetryMetrics: Record<string, Record<string, number>>;
  liveTelemetryHistory: Record<string, TelemetryMetricSample[]>;
  simulationResult: SimulationResult | null;
  selectedService: string | null;
  componentOverrides: Record<string, ServiceOverride>;
  onComponentOverrideChange?: (serviceName: string, patch: ServiceOverride) => void;
  onSelectService?: (serviceName: string) => void;
  onClearSelection?: () => void;
  headerControls?: ReactNode;
};

export default function GraphView({
  model,
  mode,
  telemetryStatus,
  latestLogsByService,
  liveTelemetryMetrics,
  liveTelemetryHistory,
  simulationResult,
  selectedService,
  componentOverrides,
  onComponentOverrideChange,
  onSelectService,
  onClearSelection,
  headerControls,
}: Props) {
  const services = useMemo(() => model?.services ?? [], [model]);
  const modelEdges = useMemo(() => model?.edges ?? [], [model]);
  const simulatedMetrics = useMemo(() => simulationResult?.per_service_metrics, [simulationResult]);
  const isTelemetryActive = Boolean(
    telemetryStatus?.ingest.last_ingested_at && Date.now() / 1000 - telemetryStatus.ingest.last_ingested_at <= 15
  );

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const edgeTypes = useMemo(() => ({ spanTravel: SpanTravelEdge }), []);
  const [popoverPosition, setPopoverPosition] = useState<{ x: number; y: number } | null>(null);
  const [popoverPinned, setPopoverPinned] = useState(false);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const selectedServiceMetrics = selectedService ? liveTelemetryMetrics[selectedService] : undefined;

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedService) ?? null,
    [nodes, selectedService]
  );
  const selectedServiceHistory = selectedService ? liveTelemetryHistory[selectedService] ?? [] : [];
  const latestHistoryMetrics = selectedServiceHistory[selectedServiceHistory.length - 1]?.metrics;

  function hasActiveOverride(serviceName: string): boolean {
    const override = componentOverrides[serviceName];
    if (!override) {
      return false;
    }
    return (
      override.latency_multiplier !== undefined ||
      override.error_rate_override !== undefined ||
      override.concurrency_limit_override !== undefined
    );
  }

  function shortLog(message: string): string {
    return message.length > 52 ? `${message.slice(0, 52)}...` : message;
  }

  useEffect(() => {
    setNodes((prevNodes) => {
      const prevPositions = new Map(prevNodes.map((node) => [node.id, node.position]));
      const nextNodes: Node[] = services.map((svc, index) => ({
        id: svc.service_name,
        data: {
          label: (
            <div className="node-card">
              <div className="node-title">{svc.service_name}</div>
              {mode === "simulation" && hasActiveOverride(svc.service_name) && (
                <span className="node-override-badge">edited</span>
              )}
              <div className="node-metric">lat: {svc.latency_distribution.mean.toFixed(1)} ms</div>
              <div className="node-metric">p95: {svc.latency_distribution.p95.toFixed(1)} ms</div>
              <div className="node-metric">err: {(svc.error_rate * 100).toFixed(1)}%</div>
              <div className="node-metric">rps: {svc.throughput_rps.toFixed(1)}</div>
              {mode === "live" && latestLogsByService[svc.service_name] && (
                <div
                  className={`node-log-chip node-log-${latestLogsByService[svc.service_name].severity_text.toLowerCase()}`}
                  title={latestLogsByService[svc.service_name].body}
                >
                  {latestLogsByService[svc.service_name].severity_text}: {shortLog(latestLogsByService[svc.service_name].body)}
                </div>
              )}
              {mode === "simulation" && Boolean(simulatedMetrics?.[svc.service_name]) && (
                <div className="node-sim">
                  sim done: {(simulatedMetrics?.[svc.service_name] as { completed?: number } | undefined)?.completed ?? 0} | queue: {(simulatedMetrics?.[svc.service_name] as { queue_depth?: number } | undefined)?.queue_depth ?? 0}
                </div>
              )}
            </div>
          ),
        },
        position: prevPositions.get(svc.service_name) ?? {
          x: 100 + (index % 4) * 270,
          y: 80 + Math.floor(index / 4) * 210,
        },
        style: {
          borderRadius: 2,
          border:
            selectedService === svc.service_name
              ? "2px solid #62c281"
              : mode === "simulation"
                ? "2px solid #3d464f"
                : "2px solid #3d464f",
          padding: 12,
          background: "#15181c",
          color: "#f4f6f8",
          minWidth: 236,
          boxShadow: "none",
        },
      }));
      return nextNodes;
    });
  }, [services, mode, selectedService, simulatedMetrics, latestLogsByService, setNodes]);

  useEffect(() => {
    const nextEdges: Edge[] = modelEdges.map((edge, index) => ({
      id: `${edge.source_service}-${edge.target_service}-${index}`,
      source: edge.source_service,
      target: edge.target_service,
      type: "spanTravel",
      label: `${(edge.call_probability * 100).toFixed(0)}% flow`,
      data: {
        callType: edge.call_type ?? "other",
        animate: (isTelemetryActive || mode === "simulation") && edge.call_probability > 0,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: spanColor(edge.call_type ?? "other"),
      },
    }));
    setEdges(nextEdges);
  }, [isTelemetryActive, mode, modelEdges, setEdges]);

  useEffect(() => {
    if (!selectedNode) {
      setPopoverPosition(null);
      setPopoverPinned(false);
      return;
    }

    if (!popoverPinned) {
      setPopoverPosition({
        x: selectedNode.position.x + 18,
        y: Math.max(10, selectedNode.position.y - 150),
      });
    }
  }, [selectedNode, popoverPinned]);

  useEffect(() => {
    function onDocumentPointerDown(event: MouseEvent) {
      if (!selectedService) {
        return;
      }

      const target = event.target as HTMLElement;
      const clickedPopover = popoverRef.current?.contains(target) ?? false;
      const clickedNode = Boolean(target.closest(".react-flow__node"));
      if (clickedPopover || clickedNode) {
        return;
      }

      onClearSelection?.();
      setPopoverPinned(false);
      setPopoverPosition(null);
    }

    document.addEventListener("mousedown", onDocumentPointerDown);
    return () => {
      document.removeEventListener("mousedown", onDocumentPointerDown);
    };
  }, [onClearSelection, selectedService]);

  function beginPopoverDrag(event: ReactMouseEvent<HTMLDivElement>) {
    if (!popoverPinned || !popoverPosition) {
      return;
    }
    event.preventDefault();
    const startX = event.clientX;
    const startY = event.clientY;
    const initial = { ...popoverPosition };

    function onMouseMove(moveEvent: MouseEvent) {
      const deltaX = moveEvent.clientX - startX;
      const deltaY = moveEvent.clientY - startY;
      setPopoverPosition({
        x: Math.max(8, initial.x + deltaX),
        y: Math.max(8, initial.y + deltaY),
      });
    }

    function onMouseUp() {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    }

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }

  return (
    <section className="graph-stage">
      <div className="graph-header">
        <div>
          <h2 className="split-title">
            <span>{mode === "live" ? "Live" : "Simulation"}</span> Topology
          </h2>
          <p>
            {telemetryStatus
              ? `Source ${telemetryStatus.source_mode} • spans ${telemetryStatus.counts.spans} • logs ${telemetryStatus.counts.logs} • metrics ${telemetryStatus.counts.metrics}`
              : "Waiting for telemetry status..."}
          </p>
            <div className="span-legend" aria-label="span type legend">
              <span><i style={{ background: SPAN_COLOR_BY_TYPE.http }} />http</span>
              <span><i style={{ background: SPAN_COLOR_BY_TYPE.rpc }} />rpc</span>
              <span><i style={{ background: SPAN_COLOR_BY_TYPE.db }} />db</span>
              <span><i style={{ background: SPAN_COLOR_BY_TYPE.kafka }} />kafka</span>
              <span><i style={{ background: SPAN_COLOR_BY_TYPE.other }} />other</span>
            </div>
        </div>
        {headerControls && <div className="graph-header-controls">{headerControls}</div>}
      </div>
      {!model && <p>Start the sample stream, then build model with "build now"</p>}
      {model && (
        <div className="graph-canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={(_, node) => onSelectService?.(node.id)}
            onPaneClick={() => {
              onClearSelection?.();
              setPopoverPinned(false);
              setPopoverPosition(null);
            }}
            edgeTypes={edgeTypes}
            fitView
          >
            <Background variant={BackgroundVariant.Dots} gap={28} size={0} color="transparent" />
            <MiniMap pannable zoomable />
            <Controls />
          </ReactFlow>

          {selectedNode && popoverPosition && (
            <div
              className="node-override-popover"
              ref={popoverRef}
              style={{
                left: popoverPosition.x,
                top: popoverPosition.y,
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="node-override-header" onMouseDown={mode === "simulation" ? beginPopoverDrag : undefined}>
                <h4 className="split-title"><span>{selectedNode.id}</span></h4>
                {mode === "simulation" && (
                  <button
                    type="button"
                    className={popoverPinned ? "secondary popover-pin active" : "secondary popover-pin"}
                    onClick={() => setPopoverPinned((prev) => !prev)}
                  >
                    {popoverPinned ? "Unpin" : "Pin"}
                  </button>
                )}
              </div>
              {mode === "live" && (
                <div className="popover-metrics-section">
                  <div className="metric-history-panel">
                    <div className="metric-history-title split-title"><span>Recent</span> trend</div>
                    <MetricHistoryChart label="CPU" unit="%" samples={selectedServiceHistory} metricName="cpu.utilization" />
                    <MetricHistoryChart label="Memory" unit="MB" samples={selectedServiceHistory} metricName="memory.utilization" />
                    <MetricHistoryChart label="Queue" unit="items" samples={selectedServiceHistory} metricName="queue.depth" />
                  </div>
                </div>
              )}
              {mode === "simulation" && (
                <>
                  <label>
                    Latency x
                    <input
                      type="number"
                      min={0.1}
                      step={0.1}
                      value={componentOverrides[selectedNode.id]?.latency_multiplier ?? ""}
                      placeholder="1.0"
                      onChange={(e) => {
                        const raw = e.target.value;
                        onComponentOverrideChange?.(selectedNode.id, {
                          ...componentOverrides[selectedNode.id],
                          latency_multiplier: raw === "" ? undefined : Math.max(0.1, Number(raw)),
                        });
                      }}
                    />
                  </label>
                  <label>
                    Error rate
                    <input
                      type="number"
                      min={0}
                      max={1}
                      step={0.01}
                      value={componentOverrides[selectedNode.id]?.error_rate_override ?? ""}
                      placeholder="0.0"
                      onChange={(e) => {
                        const raw = e.target.value;
                        onComponentOverrideChange?.(selectedNode.id, {
                          ...componentOverrides[selectedNode.id],
                          error_rate_override: raw === "" ? undefined : Math.max(0, Math.min(1, Number(raw))),
                        });
                      }}
                    />
                  </label>
                  <label>
                    Concurrency
                    <input
                      type="number"
                      min={1}
                      step={1}
                      value={componentOverrides[selectedNode.id]?.concurrency_limit_override ?? ""}
                      placeholder="4"
                      onChange={(e) => {
                        const raw = e.target.value;
                        onComponentOverrideChange?.(selectedNode.id, {
                          ...componentOverrides[selectedNode.id],
                          concurrency_limit_override: raw === "" ? undefined : Math.max(1, Math.floor(Number(raw))),
                        });
                      }}
                    />
                  </label>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function metricCard(label: string, value: string) {
  return (
    <div className="metric-card" key={label}>
      <span className="metric-label">{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatMetricValue(
  value: number | undefined,
  keepDecimals: boolean,
  fractionDigits: number,
  unitSuffix = ""
): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }

  const formatted = keepDecimals ? value.toFixed(fractionDigits) : value.toFixed(fractionDigits);
  return `${formatted}${unitSuffix}`;
}

function scaleMetricValue(metricName: string, value: number | undefined): number | undefined {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return undefined;
  }

  if (metricName === "cpu.utilization") {
    return value * 100;
  }

  if (metricName === "memory.utilization") {
    return value / (1024 * 1024);
  }

  return value;
}

function MetricHistoryChart({
  label,
  unit,
  samples,
  metricName,
}: {
  label: string;
  unit: string;
  samples: TelemetryMetricSample[];
  metricName: string;
}) {
  const values = samples
    .map((sample) => scaleMetricValue(metricName, sample.metrics[metricName]))
    .filter((value): value is number => typeof value === "number" && !Number.isNaN(value));

  const latest = values.length > 0 ? values[values.length - 1] : undefined;
  const pathData = buildSparklinePath(values);

  return (
    <div className="metric-history-row">
      <div className="metric-history-row-header">
        <span>{label}</span>
        <strong>{formatMetricValue(latest, true, metricName === "queue.depth" ? 1 : 2, ` ${unit}`)}</strong>
      </div>
      <svg className="metric-history-chart" viewBox="0 0 120 28" preserveAspectRatio="none" role="img" aria-label={`${label} trend`}>
        <path d={pathData} />
      </svg>
    </div>
  );
}

function buildSparklinePath(values: number[]): string {
  if (values.length === 0) {
    return "";
  }

  if (values.length === 1) {
    return "M 0 14 L 120 14";
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = 120 / (values.length - 1);

  return values
    .map((value, index) => {
      const x = index * step;
      const normalized = (value - min) / range;
      const y = 26 - normalized * 22;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}
