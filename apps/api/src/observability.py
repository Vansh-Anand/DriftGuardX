import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from fastapi import FastAPI
import sys

def setup_observability(app: FastAPI):
    # Set up basic tracing
    provider = TracerProvider()
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    
    # We would normally use FastAPIInstrumentor here, but depending on the environment
    # we don't want to crash if the package isn't installed. We'll do a safe import.
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logging.info("OpenTelemetry FastAPI Instrumentation enabled.")
    except ImportError:
        logging.warning("opentelemetry-instrumentation-fastapi not found. Tracing disabled.")

    # Similarly for SQLAlchemy
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        # In a real app we would pass the sqlalchemy engine here, 
        # but the instrumentor hooks globally into sqlalchemy events
        SQLAlchemyInstrumentor().instrument()
        logging.info("OpenTelemetry SQLAlchemy Instrumentation enabled.")
    except ImportError:
        logging.warning("opentelemetry-instrumentation-sqlalchemy not found.")
