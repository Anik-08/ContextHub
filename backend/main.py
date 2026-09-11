"""
main.py — Root entry point for the ContextHub backend.

Run the server with:
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Or using this file directly:
    uv run python main.py

--reload: watch for file changes and restart automatically (development only)
--host 0.0.0.0: listen on all interfaces (needed if running in Docker/VM)
--port 8000: default FastAPI port
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",  # "module_path:app_variable"
        host="0.0.0.0",
        port=8000,
        reload=True,     # auto-restart on code changes (dev mode only)
        log_level="info",
    )
