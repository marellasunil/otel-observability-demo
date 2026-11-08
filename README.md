# OTel Observability Demo

A small, vendor-neutral, OpenTelemetry-instrumented FastAPI workload for learning Grafana OSS, Mimir, Loki, Tempo, and AI observability.

## Implemented in v0.1
- FastAPI: `/health`, `/checkout`, `/error`, `/ai/chat`
- OTLP/gRPC trace and metric export to the existing OTel Gateway
- JSON stdout logs with active `trace_id` and `span_id`, collected by the existing Kubernetes filelog agent
- Simulated GenAI span attributes and token metrics; no external model or API key required
- Kubernetes Deployment/Service and basic CI

**Not yet implemented:** PostgreSQL, Redis, workers, Pyroscope instrumentation, Langfuse, production SLOs, Helm packaging, or real LLM calls. These are planned phases, not features of v0.1.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 uvicorn app.main:app --reload
```

Ensure a local OTLP/gRPC Collector is available, or expect exporter connection warnings.

## Build and deploy to the homelab

```bash
docker build -t otel-observability-demo:dev .
# Transfer image to the Kubernetes worker's container runtime, or push to an accessible registry.
# The worker must be able to resolve image otel-observability-demo:dev.
kubectl apply -f deployments/kubernetes/demo.yaml
kubectl -n demo-apps rollout status deploy/otel-observability-demo
kubectl -n demo-apps port-forward svc/otel-observability-demo 8000:8000
```

Then from another terminal:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/checkout
curl http://localhost:8000/error
curl 'http://localhost:8000/ai/chat?prompt=hello'
```

**Image note:** The deployment references a local image tag. On a kubeadm worker using containerd, a Docker Desktop image on the laptop is **not** automatically available. Push to a registry and update the image reference, or import into the worker's containerd before deployment.

## Explore

- **Tempo**: search service `otel-observability-demo`; check `checkout.process` and `chat mock-model` spans.
- **Loki**: query `{k8s_namespace_name="demo-apps"}` if Kubernetes metadata is extracted by the filelog receiver. JSON `trace_id` is in the log body; use `| json` to extract it for correlation.
- **Mimir**: find metric names derived from `demo.requests` and `demo.gen_ai.tokens` after the first metric export.

For trace-to-logs in Grafana, ensure Tempo's Trace-to-logs query uses a Loki selector matching the demo workload. The standard generated query might assume a `trace_id` indexed label; our JSON log contains `trace_id` in the body. Use a custom query or derived field to correlate without indexing high-cardinality trace IDs.

## Security and resource notes

The AI endpoint is a **simulation**. It does not send prompts externally or record prompt content in spans/logs. This is an educational workload; do not expose it publicly without authentication, rate limits, and additional security controls. The `/error` endpoint intentionally returns HTTP 500 for incident drills.
