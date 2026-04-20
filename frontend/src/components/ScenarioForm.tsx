import { ChangeEvent, FormEvent, useState } from "react";
import type { ScenarioRequest, ServiceOverride } from "../api/client";

type Props = {
  onRun: (scenario: ScenarioRequest) => Promise<void>;
  serviceNames: string[];
  componentOverrides: Record<string, ServiceOverride>;
};

export default function ScenarioForm({ onRun, serviceNames, componentOverrides }: Props) {
  const [trafficMultiplier, setTrafficMultiplier] = useState(2);
  const [durationSeconds, setDurationSeconds] = useState(120);
  const [seed, setSeed] = useState(42);
  const [environmentProfile, setEnvironmentProfile] = useState<"baseline" | "stressed" | "degraded">("baseline");
  const [running, setRunning] = useState(false);

  function parseNumber(event: ChangeEvent<HTMLInputElement>): number {
    return Number(event.target.value);
  }

  function buildServiceOverrides(): Record<string, ServiceOverride> {
    const serviceOverrides: Record<string, ServiceOverride> = {};

    const envLatencyMultiplier =
      environmentProfile === "stressed" ? 1.25 : environmentProfile === "degraded" ? 1.8 : 1.0;
    const envErrorAdd =
      environmentProfile === "stressed" ? 0.01 : environmentProfile === "degraded" ? 0.04 : 0.0;
    const envConcurrencyFactor = environmentProfile === "degraded" ? 0.75 : 1.0;

    for (const serviceName of serviceNames) {
      if (environmentProfile === "baseline") {
        continue;
      }
      serviceOverrides[serviceName] = {
        latency_multiplier: envLatencyMultiplier,
        error_rate_override: envErrorAdd,
        concurrency_limit_override: Math.max(1, Math.floor(4 * envConcurrencyFactor)),
      };
    }

    for (const [serviceName, override] of Object.entries(componentOverrides)) {
      serviceOverrides[serviceName] = {
        ...(serviceOverrides[serviceName] ?? {}),
        ...override,
      };
    }

    return serviceOverrides;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setRunning(true);
    try {
      await onRun({
        traffic_multiplier: trafficMultiplier,
        duration_seconds: durationSeconds,
        seed,
        service_overrides: buildServiceOverrides(),
        edge_overrides: {},
      });
    } finally {
      setRunning(false);
    }
  }

  return (
    <form className="scenario-toolbar" onSubmit={handleSubmit}>
      <label>
        Traffic
        <input
          type="number"
          min={0.1}
          step={0.1}
          value={trafficMultiplier}
          onChange={(e) => setTrafficMultiplier(parseNumber(e))}
        />
      </label>
      <label>
        Duration
        <input
          type="number"
          min={1}
          value={durationSeconds}
          onChange={(e) => setDurationSeconds(parseNumber(e))}
        />
      </label>
      <label>
        Seed
        <input
          type="number"
          value={seed}
          onChange={(e) => setSeed(parseNumber(e))}
        />
      </label>

      <label>
        Environment
        <select value={environmentProfile} onChange={(e) => setEnvironmentProfile(e.target.value as "baseline" | "stressed" | "degraded")}>
          <option value="baseline">baseline</option>
          <option value="stressed">stressed</option>
          <option value="degraded">degraded</option>
        </select>
      </label>
      <button type="submit" disabled={running}>
        {running ? "Running..." : "Run Simulation"}
      </button>
    </form>
  );
}
