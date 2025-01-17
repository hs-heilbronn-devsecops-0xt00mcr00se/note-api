# -*- coding: utf-8 -*-
from uuid import uuid4
from typing import List, Optional
from os import getenv
from typing_extensions import Annotated

from fastapi import Depends, FastAPI
from starlette.responses import RedirectResponse
from .backends import Backend, RedisBackend, MemoryBackend, GCSBackend
from .model import Note, CreateNoteRequest

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# from opentelemetry.trace import SpanContext, NonRecordingSpan
# from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
# from opentelemetry.sdk.trace import TracerProvider
# from opentelemetry.sdk.trace.export import BatchSpanProcessor

# from opentelemetry.propagate import set_global_textmap, inject, extract
# from opentelemetry.propagators.cloud_trace_propagator import (
#     CloudTraceFormatPropagator,
# )
# set_global_textmap(CloudTraceFormatPropagator())


# tracer_provider = TracerProvider()
# cloud_trace_exporter = CloudTraceSpanExporter()
# tracer_provider.add_span_processor(
#     BatchSpanProcessor(cloud_trace_exporter)
# )
# trace.set_tracer_provider(tracer_provider)

tracer = trace.get_tracer(__name__)

app = FastAPI()

my_backend: Optional[Backend] = None

# Setup OpenTelemetry Tracing
trace.set_tracer_provider(TracerProvider())
tracer_provider = trace.get_tracer_provider()

# Instrument the FastAPI app
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


# @app.get('/notes')
# def get_notes(backend: Annotated[Backend, Depends(get_backend)]) -> List[Note]:
#     keys = backend.keys()

#     Notes = []
#     for key in keys:
#         Notes.append(backend.get(key))
#     return Notes


@app.get('/notes')
def get_notes(backend: Annotated[Backend, Depends(get_backend)]) -> List[Note]:
    """Fetch all notes from the backend"""
    with tracer.start_as_current_span("get_notes") as span:
        span.set_attribute("backend.type", type(backend).__name__)
        keys = backend.keys()
        notes = []
        for key in keys:
            with tracer.start_as_current_span("fetch_note_from_backend") as sub_span:
                sub_span.set_attribute("note.key", key)
                notes.append(backend.get(key))
        return notes


# @app.get('/notes/{note_id}')
# def get_note(note_id: str,
#              backend: Annotated[Backend, Depends(get_backend)]) -> Note:
#     return backend.get(note_id)


@app.get('/notes/{note_id}')
def get_note(note_id: str,
             backend: Annotated[Backend, Depends(get_backend)]) -> Note:
    """Fetch a single note from the backend"""
    with tracer.start_as_current_span("get_note") as span:
        span.set_attribute("note.id", note_id)
        return backend.get(note_id)


# @app.put('/notes/{note_id}')
# def update_note(note_id: str,
#                 request: CreateNoteRequest,
#                 backend: Annotated[Backend, Depends(get_backend)]) -> None:
#     backend.set(note_id, request)


@app.put('/notes/{note_id}')
def update_note(note_id: str,
                request: CreateNoteRequest,
                backend: Annotated[Backend, Depends(get_backend)]) -> None:
    """Update an existing note"""
    with tracer.start_as_current_span("update_note") as span:
        span.set_attribute("note.id", note_id)
        backend.set(note_id, request)


# @app.post('/notes')
# def create_note(request: CreateNoteRequest,
#                 backend: Annotated[Backend, Depends(get_backend)]) -> str:
#     note_id = str(uuid4())
#     backend.set(note_id, request)
#     return note_id


@app.post('/notes')
def create_note(request: CreateNoteRequest,
                backend: Annotated[Backend, Depends(get_backend)]) -> str:
    """Create a new note"""
    with tracer.start_as_current_span("create_note") as span:
        note_id = str(uuid4())
        span.set_attribute("note.id", note_id)
        backend.set(note_id, request)
        return note_id


@app.get("/custom-span")
async def custom_span():
    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("custom-operation"):
        # Simulated operation
        result = {"message": "Custom span in action!"}
        return result