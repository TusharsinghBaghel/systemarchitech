from app.model_builder.graph_builder import build_model
from app.schemas.otel import SpanRecord


def test_build_model_extracts_services_and_edges() -> None:
    spans = [
        SpanRecord(
            trace_id="t1",
            span_id="s1",
            parent_span_id=None,
            service_name="api",
            span_name="GET /login",
            kind="SERVER",
            start_time=0,
            end_time=2_000_000,
            duration_ms=2.0,
            attributes={"http.method": "GET"},
            status_code="OK",
        ),
        SpanRecord(
            trace_id="t1",
            span_id="s2",
            parent_span_id="s1",
            service_name="auth",
            span_name="validate",
            kind="SERVER",
            start_time=2_100_000,
            end_time=6_000_000,
            duration_ms=3.9,
            attributes={"rpc.system": "grpc"},
            status_code="OK",
        ),
    ]

    model = build_model(spans)

    assert len(model.services) == 2
    assert len(model.edges) == 1
    edge = model.edges[0]
    assert edge.source_service == "api"
    assert edge.target_service == "auth"
