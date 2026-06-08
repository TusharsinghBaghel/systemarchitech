import { ChangeEvent, useEffect, useMemo, useState } from "react";
import type { TelemetryDatasource } from "../api/client";

type Props = {
  datasources: TelemetryDatasource[];
  sourceMode: "none" | "direct" | "external";
  usesDefaults: boolean;
  onLoad?: () => Promise<void>;
  onSave: (datasources: TelemetryDatasource[]) => Promise<void>;
  onClose: () => void;
};

type Row = TelemetryDatasource & { id: string };

function makeRow(partial?: Partial<Row>): Row {
  return {
    id: partial?.id ?? crypto.randomUUID(),
    kind: partial?.kind ?? "prometheus",
    url: partial?.url ?? "http://127.0.0.1:9090",
    label: partial?.label ?? "",
    enabled: partial?.enabled ?? true,
  };
}

export default function DatasourcePanel({ datasources, sourceMode, usesDefaults, onLoad, onSave, onClose }: Props) {
  const [rows, setRows] = useState<Row[]>([]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const nextRows = datasources.length > 0 ? datasources.map((datasource) => makeRow(datasource as Row)) : [];
    setRows(nextRows);
  }, [datasources]);

  const hasRows = rows.length > 0;

  const helperText = useMemo(() => {
    if (sourceMode !== "external") {
      return "External datasource mode is inactive right now.";
    }
    return usesDefaults
      ? "Using the built-in external defaults until you click Done with custom links."
      : "Custom external datasource links are active.";
  }, [sourceMode, usesDefaults]);

  function updateRow(id: string, patch: Partial<Row>) {
    setRows((prev) => prev.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  }

  function addRow() {
    setRows((prev) => [...prev, makeRow()]);
  }

  function removeRow(id: string) {
    setRows((prev) => prev.filter((row) => row.id !== id));
  }

  async function handleDone() {
    setSaving(true);
    setMessage(null);
    try {
      await onSave(
        rows
          .filter((row) => row.enabled)
          .map(({ kind, url, label, enabled }) => ({
            kind,
            url,
            label: label?.trim() || null,
            enabled,
          }))
      );
      await onLoad?.();
      setMessage("Saved and synced external datasources.");
      onClose();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save datasources");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="modal-backdrop" role="presentation" onClick={onClose}>
      <section
        className="panel datasource-panel datasource-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="datasource-dialog-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="override-header">
          <div>
            <h3 id="datasource-dialog-title">External Datasources</h3>
            <p className="hint datasource-hint">{helperText}</p>
          </div>
          <div className="datasource-dialog-actions">
            <button type="button" className="secondary" onClick={addRow}>
              Add link
            </button>
            <button type="button" className="secondary" onClick={onClose}>
              Close
            </button>
          </div>
        </div>

      {hasRows ? (
        <div className="datasource-list">
          {rows.map((row) => (
            <div className="datasource-row" key={row.id}>
              <label>
                Type
                <select value={row.kind} onChange={(event) => updateRow(row.id, { kind: event.target.value as Row["kind"] })}>
                  <option value="prometheus">prometheus</option>
                  <option value="loki">loki</option>
                  <option value="jaeger">jaeger</option>
                </select>
              </label>
              <label>
                Label
                <input value={row.label ?? ""} placeholder="optional label" onChange={(event: ChangeEvent<HTMLInputElement>) => updateRow(row.id, { label: event.target.value })} />
              </label>
              <label>
                URL
                <input value={row.url} placeholder="http://127.0.0.1:18080/loki" onChange={(event) => updateRow(row.id, { url: event.target.value })} />
              </label>
              <div className="datasource-row-actions">
                <label className="datasource-toggle">
                  <input type="checkbox" checked={row.enabled ?? true} onChange={(event) => updateRow(row.id, { enabled: event.target.checked })} />
                  Enabled
                </label>
                <button type="button" className="danger" onClick={() => removeRow(row.id)}>
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="hint">No custom links yet. Click Add link to point the app at your Prometheus, Loki, or Jaeger endpoint.</p>
      )}

        <div className="datasource-footer">
          <button type="button" onClick={handleDone} disabled={saving}>
            {saving ? "Saving..." : "Done"}
          </button>
          {message && <span className="datasource-message">{message}</span>}
        </div>
      </section>
    </section>
  );
}