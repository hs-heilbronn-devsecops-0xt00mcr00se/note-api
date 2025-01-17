# -*- coding: utf-8 -*-
from uuid import uuid4
from typing import List, Optional
from os import getenv
from typing_extensions import Annotated

from fastapi import Depends, FastAPI
from starlette.responses import RedirectResponse
from .backends import Backend, RedisBackend, MemoryBackend, GCSBackend
# from note_api.backends import Backend, RedisBackend, MemoryBackend, GCSBackend  # for testing locally
from .model import Note, CreateNoteRequest

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

app = FastAPI()

my_backend: Optional[Backend] = None


# Set up OpenTelemetry tracing
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Adding a ConsoleSpanExporter to output traces to the console for debugging purpose
trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(ConsoleSpanExporter())
)

# Instrumenting FastAPI for automatic tracing
FastAPIInstrumentor().instrument_app(app)


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


# @app.get('/')
# def redirect_to_notes() -> None:
#     return RedirectResponse(url='/notes')


@app.get('/')
def redirect_to_notes() -> None:
    # Start a custom span to track the redirection
    with tracer.start_as_current_span("redirect_to_notes_span") as span:
        # Optionally, you can set some attributes or events
        span.set_attribute("custom.redirect", "redirect_to_notes called")
        span.add_event("Redirecting to /notes")

        # Perform the redirection
        response = RedirectResponse(url='/notes')

        # Add an event after the redirect is prepared
        span.add_event("Redirect response prepared")

        # Return the response (this will trigger the redirect)
        return response


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