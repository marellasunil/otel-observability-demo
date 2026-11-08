import json
import logging
import os
import random
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from opentelemetry import metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import Status, StatusCode

SERVICE = os.getenv("OTEL_SERVICE_NAME", "otel-observability-demo")
RESOURCE = Resource.create({
    "service.name": SERVICE,
    "service.namespace": "demo-apps",
    "service.version": os.getenv("APP_VERSION", "0.1.0"),
    "deployment.environment.name": os.getenv("DEPLOYMENT_ENVIRONMENT", "homelab"),
})
endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-gateway.observability.svc.cluster.local:4317")
trace_provider = TracerProvider(resource=RESOURCE)
trace_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=endpoint.startswith("http://"))))
trace.set_tracer_provider(trace_provider)
metric_provider = MeterProvider(resource=RESOURCE, metric_readers=[
    PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=endpoint.startswith("http://")),
        export_interval_millis=10000,
    )
])
metrics.set_meter_provider(metric_provider)
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)
requests = meter.create_counter("demo.requests", description="Demo requests")
ai_tokens = meter.create_counter("demo.gen_ai.tokens", description="Simulated AI tokens")
ai_duration = meter.create_histogram("demo.gen_ai.duration", unit="s", description="Simulated AI latency")

class JsonFormatter(logging.Formatter):
    def format(self, record):
        span = trace.get_current_span()
        ctx = span.get_span_context()
        return json.dumps({
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "severity": record.levelname,
            "message": record.getMessage(),
            "service.name": SERVICE,
            "trace_id": format(ctx.trace_id, "032x") if ctx.is_valid else "",
            "span_id": format(ctx.span_id, "016x") if ctx.is_valid else "",
        })

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("demo")
logger.handlers = [handler]
logger.setLevel(logging.INFO)
logger.propagate = False
LoggingInstrumentor().instrument(set_logging_format=False)

@asynccontextmanager
async def lifespan(app):
    yield
    metric_provider.shutdown()
    trace_provider.shutdown()

app = FastAPI(title="OTel Observability Demo", version="0.1.0", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)

@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE}

@app.get("/checkout")
def checkout():
    with tracer.start_as_current_span("checkout.process") as span:
        requests.add(1, {"route": "/checkout", "outcome": "success"})
        time.sleep(0.05)
        span.set_attribute("demo.order.type", "sample")
        logger.info("Checkout completed")
        return {"order_id": "demo-order", "status": "completed"}

@app.get("/error")
def error():
    with tracer.start_as_current_span("checkout.failure") as span:
        requests.add(1, {"route": "/error", "outcome": "error"})
        logger.error("Simulated checkout failure")
        span.set_status(Status(StatusCode.ERROR, "Simulated failure"))
        raise HTTPException(status_code=500, detail="Simulated failure")

@app.get("/ai/chat")
def ai_chat(prompt: str = "Explain OpenTelemetry"):
    # Simulation only: no external LLM call and no prompt content recorded in telemetry.
    with tracer.start_as_current_span("chat mock-model") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.provider.name", "demo")
        span.set_attribute("gen_ai.request.model", "mock-model")
        start = time.monotonic()
        time.sleep(random.uniform(0.05, 0.15))
        input_tokens = max(1, len(prompt.split()))
        output_tokens = 12
        span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
        ai_tokens.add(input_tokens, {"type": "input", "model": "mock-model"})
        ai_tokens.add(output_tokens, {"type": "output", "model": "mock-model"})
        ai_duration.record(time.monotonic() - start, {"model": "mock-model"})
        logger.info("Simulated AI completion, input_tokens=%d output_tokens=%d", input_tokens, output_tokens)
        return {"model": "mock-model", "answer": "OpenTelemetry is a vendor-neutral observability framework.", "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}, "simulated": True}
