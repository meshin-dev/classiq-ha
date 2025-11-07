"""Main entry point for the Quantum Circuit Execution API server."""

from fastapi import FastAPI

from app.routes import router
from app.settings import API_HOST, API_PORT

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    load_dotenv = None

app = FastAPI(
    title="Quantum Circuit Execution API",
    description="System for executing Quantum Circuits using QASM3",
    version="0.1.0",
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=API_HOST, port=API_PORT)
