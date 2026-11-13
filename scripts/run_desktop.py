"""Cross-platform launcher for OmniSearch desktop development environment.

Conceptually equivalent to:
    npm run electron:dev

Launches or connects to FastAPI backend, starts Next.js dev server,
and opens Electron desktop window.
"""

import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")

BACKEND_HEALTH_URL = "http://127.0.0.1:8000/api/v1/health"
FRONTEND_DEV_URL = "http://localhost:3000"


def is_http_ready(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status < 500
    except (urllib.error.URLError, TimeoutError, ConnectionRefusedError, OSError):
        return False


def wait_for_http(url: str, name: str, timeout_sec: int = 30, interval_sec: float = 0.5) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        if is_http_ready(url):
            return True
        time.sleep(interval_sec)
    return False


def main():
    print("=" * 60)
    print("         OmniSearch Desktop Development Launcher           ")
    print("=" * 60)

    backend_proc = None
    frontend_proc = None

    try:
        # Step 1: FastAPI Backend
        print("[Step 1/3] Checking FastAPI Backend readiness...")
        if is_http_ready(BACKEND_HEALTH_URL):
            print(f"[Launcher] Pre-existing FastAPI detected at {BACKEND_HEALTH_URL}. Reusing.")
        else:
            print("[Launcher] Starting FastAPI backend on http://127.0.0.1:8000...")
            python_bin = sys.executable
            backend_proc = subprocess.Popen(
                [python_bin, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=BACKEND_DIR,
                env=os.environ.copy(),
            )
            print("[Launcher] Waiting for FastAPI to become ready...")
            if not wait_for_http(BACKEND_HEALTH_URL, "FastAPI", timeout_sec=30):
                print("[Launcher] ERROR: FastAPI backend did not start within timeout.")
                sys.exit(1)
            print("[Launcher] FastAPI backend is ready.")

        # Step 2: Next.js Frontend
        print("[Step 2/3] Checking Next.js dev server readiness...")
        if is_http_ready(FRONTEND_DEV_URL):
            print(f"[Launcher] Pre-existing Next.js dev server detected at {FRONTEND_DEV_URL}. Reusing.")
        else:
            print("[Launcher] Starting Next.js dev server on http://localhost:3000...")
            npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
            frontend_proc = subprocess.Popen(
                [npm_cmd, "run", "dev"],
                cwd=FRONTEND_DIR,
                env=os.environ.copy(),
                shell=(sys.platform == "win32"),
            )
            print("[Launcher] Waiting for Next.js to compile and become ready...")
            if not wait_for_http(FRONTEND_DEV_URL, "Next.js", timeout_sec=45):
                print("[Launcher] ERROR: Next.js dev server did not respond within timeout.")
                sys.exit(1)
            print("[Launcher] Next.js dev server is ready.")

        # Step 3: Electron
        print("[Step 3/3] Launching Electron desktop window...")
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        electron_env = os.environ.copy()
        electron_env["ELECTRON_START_URL"] = FRONTEND_DEV_URL
        electron_env["BACKEND_URL"] = "http://127.0.0.1:8000"

        electron_proc = subprocess.run(
            [npm_cmd, "run", "electron"],
            cwd=FRONTEND_DIR,
            env=electron_env,
            shell=(sys.platform == "win32"),
        )
        print(f"[Launcher] Electron closed with returncode: {electron_proc.returncode}")

    except KeyboardInterrupt:
        print("\n[Launcher] KeyboardInterrupt detected.")
    finally:
        print("[Launcher] Cleaning up child processes started by launcher...")
        if frontend_proc and frontend_proc.poll() is None:
            print(f"[Launcher] Stopping Next.js (PID: {frontend_proc.pid})...")
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/pid", str(frontend_proc.pid), "/T", "/F"], capture_output=True)
            else:
                frontend_proc.terminate()

        if backend_proc and backend_proc.poll() is None:
            print(f"[Launcher] Stopping FastAPI (PID: {backend_proc.pid})...")
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/pid", str(backend_proc.pid), "/T", "/F"], capture_output=True)
            else:
                backend_proc.terminate()

        print("[Launcher] Shutdown complete.")


if __name__ == "__main__":
    main()

