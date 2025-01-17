# -*- coding: utf-8 -*-
from uuid import uuid4
from typing import List, Optional
from os import getenv
from typing_extensions import Annotated

from fastapi import Depends, FastAPI
from starlette.responses import RedirectResponse
from .backends import Backend, RedisBackend, MemoryBackend, GCSBackend
from .model import Note, CreateNoteRequest

import os
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.trace import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.metrics import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


# Setup Resource with custom attributes (e.g., service instance ID)
resource = Resource.create(attributes={
    "service.instance.id": f"worker-{os.getpid()}",  # Unique service instance ID based on the worker process ID
})

# Set up TracerProvider with the resource
traceProvider = TracerProvider(resource=resource)

# Set up the BatchSpanProcessor with the OTLP exporter
processor = BatchSpanProcessor(OTLPSpanExporter())
traceProvider.add_span_processor(processor)

# Set the TracerProvider to OpenTelemetry's global trace provider
trace.set_tracer_provider(traceProvider)

# Set up the PeriodicExportingMetricReader for metrics with OTLP exporter
reader = PeriodicExportingMetricReader(OTLPMetricExporter())
meterProvider = MeterProvider(metric_readers=[reader], resource=resource)

# Set the MeterProvider for metrics collection
metrics.set_meter_provider(meterProvider)


app = FastAPI()

my_backend: Optional[Backend] = None

# Instrument the FastAPI app for tracing
FastAPIInstrumentor.instrument_app(app)

def get_backend() -> Backend:
    global my_backend  # pylint: disable=global-statement
    if my_backend is None:
        backend_type = getenv('BACKEND', 'memory')
        print(backend_type)
        if backend_type == 'redis':
            my_backend = RedisBackend()
        elif backend_type == 'gcs':
            my_backend = GCSBackend()
        else:
            my_backend = MemoryBackend()
    return my_backend


@app.get('/')
def redirect_to_notes() -> None:
    return RedirectResponse(url='/notes')


@app.get('/notes')
def get_notes(backend: Annotated[Backend, Depends(get_backend)]) -> List[Note]:
    keys = backend.keys()

    Notes = []
    for key in keys:
        Notes.append(backend.get(key))
    return Notes


@app.get('/notes/{note_id}')
def get_note(note_id: str,
             backend: Annotated[Backend, Depends(get_backend)]) -> Note:
    return backend.get(note_id)


@app.put('/notes/{note_id}')
def update_note(note_id: str,
                request: CreateNoteRequest,
                backend: Annotated[Backend, Depends(get_backend)]) -> None:
    backend.set(note_id, request)


@app.post('/notes')
def create_note(request: CreateNoteRequest,
                backend: Annotated[Backend, Depends(get_backend)]) -> str:
    note_id = str(uuid4())
    backend.set(note_id, request)
    return note_id