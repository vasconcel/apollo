"""
APOLLO — Unified development & production launcher.

Usage:
    python run.py              # Production: build (if needed) + serve
    python run.py --dev        # Development: uvicorn + vite side-by-side
    python run.py --build      # Force frontend rebuild then serve
    python run.py --port 8080  # Custom port
"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
DIST = FRONTEND / "dist"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"

DEFAULT_PORT = 8000
VITE_PORT = 5173

IS_WIN = sys.platform == "win32"


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _info(msg: str) -> None:
    print(f"  [\033[36mINFO\033[0m] {msg}")


def _warn(msg: str) -> None:
    print(f"  [\033[33mWARN\033[0m] {msg}")


def _ok(msg: str) -> None:
    print(f"  [\033[32m OK \033[0m] {msg}")


def _fail(msg: str) -> None:
    print(f"  [\033[31mFAIL\033[0m] {msg}", file=sys.stderr)


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _npm_cmd(*args: str) -> list[str]:
    if IS_WIN:
        return ["cmd", "/c", "npm"] + list(args)
    return ["npm"] + list(args)


def _npm_run(script: str) -> None:
    subprocess.run(_npm_cmd("run", script), cwd=str(FRONTEND), check=True)


def _npm_install() -> None:
    subprocess.run(_npm_cmd("install"), cwd=str(FRONTEND), check=True)


def _open_browser(url: str) -> None:
    _info(f"Opening {url} …")
    try:
        webbrowser.open(url)
    except Exception:
        _warn("Could not open browser automatically.")


# ═══════════════════════════════════════════════════════════════════════════════
# Environment checks
# ═══════════════════════════════════════════════════════════════════════════════

def _check_environment() -> None:
    if not os.getenv("VIRTUAL_ENV") and not os.getenv("CONDA_PREFIX"):
        _warn("No Python virtual environment detected — consider creating one.")

    if not ENV_FILE.exists():
        if ENV_EXAMPLE.exists():
            shutil.copy(str(ENV_EXAMPLE), str(ENV_FILE))
            _ok("Created .env from .env.example")
        else:
            _warn("No .env or .env.example found — using built-in defaults.")

    if not FRONTEND.is_dir():
        _fail("Frontend directory not found — expected at: frontend/")
        sys.exit(1)


def _ensure_frontend_built() -> None:
    if not DIST.is_dir():
        _info("frontend/dist not found — installing dependencies and building …")
        _npm_install()
        _npm_run("build")
    else:
        _ok("frontend/dist found — skipping build.")

    if not (DIST / "index.html").exists():
        _fail("Build did not produce frontend/dist/index.html — check npm build output.")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# Modes
# ═══════════════════════════════════════════════════════════════════════════════

def run_dev(port: int) -> None:
    """Spawn FastAPI (reload) + Vite dev server as parallel subprocesses."""
    _check_environment()

    if not _port_free(port):
        _fail(f"Port {port} is already in use.")
        sys.exit(1)

    _info(f"Starting development mode on port {port} …\n")

    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.main:app", "--host", "127.0.0.1", "--reload", "--port", str(port)],
        cwd=str(ROOT),
    )

    frontend = subprocess.Popen(
        _npm_cmd("run", "dev"),
        cwd=str(FRONTEND),
    )

    time.sleep(2.5)
    _open_browser(f"http://127.0.0.1:{VITE_PORT}/")

    def _cleanup():
        _info("Shutting down …")
        for proc, name in [(backend, "backend"), (frontend, "frontend")]:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                _info(f"{name} stopped.")

    try:
        backend.wait()
    except KeyboardInterrupt:
        _cleanup()


def run_prod(port: int, force_build: bool = False) -> None:
    """Build frontend if needed, then serve everything from uvicorn."""
    _check_environment()
    _ensure_frontend_built() if force_build or not DIST.is_dir() else None

    if not _port_free(port):
        _fail(f"Port {port} is already in use.")
        sys.exit(1)

    _info(f"Starting production server on port {port} …\n")

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.api.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=str(ROOT),
        )

        time.sleep(1.5)
        _ok(f"Server running at http://127.0.0.1:{port}")
        _open_browser(f"http://127.0.0.1:{port}/")

        proc.wait()
    except KeyboardInterrupt:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        _info("Server stopped.")


# ═══════════════════════════════════════════════════════════════════════════════
# Entrypoint
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        description="APOLLO — Systematic Literature Review Screening Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run.py              # production (build + serve)\n"
            "  python run.py --dev        # development (hot-reload)\n"
            "  python run.py --build      # force rebuild + serve\n"
            "  python run.py --port 8080  # custom port\n"
        ),
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Start in development mode (uvicorn --reload + Vite dev server)",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Force a production frontend build before starting the server",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("APOLLO_PORT", str(DEFAULT_PORT))),
        help=f"Port to run the server on (default: {DEFAULT_PORT})",
    )
    args = parser.parse_args()

    if args.dev:
        run_dev(port=args.port)
    else:
        run_prod(port=args.port, force_build=args.build)


if __name__ == "__main__":
    main()
