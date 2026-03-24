"""
TMOS13 Tracing — OpenTelemetry Integration

Distributed tracing across TMOS13 services and client apps.
Exports traces to Jaeger, Zipkin, or any OTLP-compatible backend.
"""
import logging
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger("tmos13.tracing")

_tracer = None
_initialized = False


def init_tracing(service_name: str = "tmos13",
                 otlp_endpoint: str = "",
                 environment: str = "development"):
    """Initialize OpenTelemetry tracing."""
    global _tracer, _initialized

    if not otlp_endpoint:
        logger.info("OTLP endpoint not configured — tracing disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        resource = Resource.create({
            "service.name": service_name,
            "service.version": "2.1.0",
            "deployment.environment": environment,
        })

        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        _tracer = trace.get_tracer(service_name)
        _initialized = True
        logger.info(f"OpenTelemetry tracing initialized: endpoint={otlp_endpoint}")
    except ImportError:
        logger.warning("opentelemetry packages not installed — tracing disabled")
    except Exception as e:
        logger.error(f"Tracing init failed: {e}")


def instrument_fastapi(app):
    """Instrument a FastAPI application for automatic tracing."""
    if not _initialized:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented for tracing")
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"FastAPI instrumentation failed: {e}")


@contextmanager
def span(name: str, attributes: dict = None):
    """Create a traced span."""
    if _tracer and _initialized:
        with _tracer.start_as_current_span(name) as s:
            if attributes:
                for k, v in attributes.items():
                    s.set_attribute(k, v)
            yield s
    else:
        yield _NoOpSpan()


class _NoOpSpan:
    def set_attribute(self, key, value): pass
    def set_status(self, status): pass
    def add_event(self, name, attributes=None): pass
    def record_exception(self, exc): pass


def trace_claude_call(model: str, tokens: int, latency_ms: float, cartridge: str = None):
    """Record a Claude API call as a span."""
    if _tracer and _initialized:
        with _tracer.start_as_current_span("claude.api_call") as s:
            s.set_attribute("ai.model", model)
            s.set_attribute("ai.tokens", tokens)
            s.set_attribute("ai.latency_ms", latency_ms)
            if cartridge:
                s.set_attribute("tmos13.cartridge", cartridge)


def trace_session(session_id: str, user_id: str):
    """Record session context."""
    if _tracer and _initialized:
        current = trace.get_current_span() if 'trace' in dir() else None
        if current:
            current.set_attribute("tmos13.session_id", session_id)
            current.set_attribute("tmos13.user_id", user_id)


def get_status() -> dict:
    return {
        "enabled": _initialized,
        "backend": "otlp" if _initialized else "none",
    }
