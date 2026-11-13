/**
 * Backend Lifecycle Manager for OmniSearch Electron Desktop Application.
 *
 * Responsibilities:
 * - Detects existing running FastAPI backend (development mode)
 * - Spawns and manages backend process when running standalone
 * - Performs non-blocking health readiness polling against /api/v1/health
 * - Ensures graceful, tracked termination on app exit without orphaned processes
 * - Never terminates unrelated Python processes
 */

const http = require('http');
const path = require('path');
const fs = require('fs');
const { spawn, execSync } = require('child_process');

class BackendManager {
  constructor(options = {}) {
    this.port = options.port || 8000;
    this.host = options.host || '127.0.0.1';
    this.backendUrl = `http://${this.host}:${this.port}`;
    this.healthUrl = `${this.backendUrl}/api/v1/health`;
    this.backendProcess = null;
    this.runningExternally = false;
  }

  /**
   * Check if the backend is currently healthy and responding.
   */
  async checkHealth(timeoutMs = 2000) {
    return new Promise((resolve) => {
      const req = http.get(this.healthUrl, { timeout: timeoutMs }, (res) => {
        let rawData = '';
        res.on('data', (chunk) => {
          rawData += chunk;
        });
        res.on('end', () => {
          if (res.statusCode === 200) {
            try {
              const parsed = JSON.parse(rawData);
              resolve({ ok: parsed.status === 'healthy', data: parsed });
            } catch {
              resolve({ ok: true });
            }
          } else {
            resolve({ ok: false, statusCode: res.statusCode });
          }
        });
      });

      req.on('error', () => resolve({ ok: false }));
      req.on('timeout', () => {
        req.destroy();
        resolve({ ok: false, timeout: true });
      });
    });
  }

  /**
   * Poll health check until ready or until timeout is reached.
   */
  async waitForReady(maxWaitMs = 30000, intervalMs = 400) {
    const startTime = Date.now();
    while (Date.now() - startTime < maxWaitMs) {
      const res = await this.checkHealth(1500);
      if (res.ok) {
        return true;
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    return false;
  }

  /**
   * Find python executable in the repository venv or environment.
   */
  findPythonPath(rootDir) {
    const isWin = process.platform === 'win32';
    const venvPythonWin = path.join(rootDir, 'backend', '.venv', 'Scripts', 'python.exe');
    const venvPythonPosix = path.join(rootDir, 'backend', '.venv', 'bin', 'python');

    if (isWin && fs.existsSync(venvPythonWin)) {
      return venvPythonWin;
    }
    if (!isWin && fs.existsSync(venvPythonPosix)) {
      return venvPythonPosix;
    }

    if (process.env.PYTHON_PATH && fs.existsSync(process.env.PYTHON_PATH)) {
      return process.env.PYTHON_PATH;
    }

    return isWin ? 'python.exe' : 'python3';
  }

  /**
   * Ensure backend is available.
   * If already running, connects cleanly.
   * If not running, launches child process and waits for readiness.
   */
  async ensureBackend(rootDir) {
    // 1. Check if backend is already available
    const initialCheck = await this.checkHealth(1500);
    if (initialCheck.ok) {
      this.runningExternally = true;
      console.log(`[BackendManager] Pre-existing FastAPI backend detected at ${this.backendUrl}. Reusing.`);
      return true;
    }

    // 2. Spawn backend if in development environment
    const backendDir = path.join(rootDir, 'backend');
    if (!fs.existsSync(backendDir)) {
      console.warn(`[BackendManager] Backend directory not found at ${backendDir}`);
      return false;
    }

    const pythonPath = this.findPythonPath(rootDir);
    console.log(`[BackendManager] Launching FastAPI backend using ${pythonPath} at ${this.backendUrl}...`);

    const child = spawn(
      pythonPath,
      ['-m', 'uvicorn', 'app.main:app', '--host', this.host, '--port', String(this.port)],
      {
        cwd: backendDir,
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
        stdio: ['ignore', 'pipe', 'pipe'],
      }
    );

    this.backendProcess = child;
    this.runningExternally = false;

    child.stdout.on('data', (data) => {
      process.stdout.write(`[FastAPI] ${data}`);
    });

    child.stderr.on('data', (data) => {
      process.stderr.write(`[FastAPI] ${data}`);
    });

    child.on('exit', (code, signal) => {
      console.log(`[BackendManager] FastAPI process exited with code ${code}, signal ${signal}`);
      this.backendProcess = null;
    });

    // 3. Wait for readiness
    const isReady = await this.waitForReady(30000);
    if (!isReady) {
      console.error(`[BackendManager] FastAPI backend failed to become ready within timeout.`);
      this.stop();
      return false;
    }

    console.log(`[BackendManager] FastAPI backend is ready and operational.`);
    return true;
  }

  /**
   * Gracefully terminate the spawned backend process.
   */
  stop() {
    if (this.runningExternally || !this.backendProcess) {
      return;
    }

    const pid = this.backendProcess.pid;
    console.log(`[BackendManager] Stopping managed FastAPI backend (PID: ${pid})...`);

    try {
      if (process.platform === 'win32') {
        execSync(`taskkill /pid ${pid} /T /F`, { stdio: 'ignore' });
      } else {
        this.backendProcess.kill('SIGTERM');
      }
    } catch (err) {
      console.warn(`[BackendManager] Notice stopping backend PID ${pid}:`, err.message);
    } finally {
      this.backendProcess = null;
    }
  }
}

module.exports = { BackendManager };

