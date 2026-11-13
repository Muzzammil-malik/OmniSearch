/**
 * Development Orchestrator for OmniSearch Desktop.
 *
 * Concepts:
 * npm run electron:dev
 * 1. Checks/starts FastAPI backend and verifies readiness via /api/v1/health
 * 2. Checks/starts Next.js development server and verifies readiness
 * 3. Launches Electron directly using the locally installed binary
 * 4. Manages lifecycle and cleans up only the processes started by this runner
 */

const http = require('http');
const path = require('path');
const fs = require('fs');
const { spawn, execSync } = require('child_process');
const { BackendManager } = require('./backend-manager');

const frontendDir = path.resolve(__dirname, '..');
const rootDir = path.resolve(frontendDir, '..');

let nextProcess = null;
let startedNext = false;
let isShuttingDown = false;

const backendManager = new BackendManager({
  port: process.env.BACKEND_PORT ? parseInt(process.env.BACKEND_PORT, 10) : 8000,
  host: process.env.BACKEND_HOST || '127.0.0.1',
});

/**
 * Cross-platform spawn helper for npm package scripts.
 * On Windows, batch files (.cmd/.bat) cannot be directly executed via spawn()
 * without raising EINVAL in Node 22+ (CVE-2024-27980). We invoke cmd.exe explicitly.
 */
function spawnNpm(args, options = {}) {
  const isWin = process.platform === 'win32';
  if (isWin) {
    return spawn('cmd.exe', ['/d', '/s', '/c', `npm.cmd ${args.join(' ')}`], {
      ...options,
      windowsVerbatimArguments: true,
    });
  }
  return spawn('npm', args, options);
}

/**
 * Resolves the path to the local Electron executable installed in the project.
 * Never hardcodes machine-specific paths; resolves dynamically from node_modules.
 *
 * @param {string} targetFrontendDir - Root directory of the frontend project
 * @returns {string} Absolute path to the resolved Electron binary
 */
function resolveElectronExecutable(targetFrontendDir) {
  // Strategy 1: Project's installed electron package export
  try {
    const electronModulePath = require.resolve('electron', { paths: [targetFrontendDir] });
    const electronExport = require(electronModulePath);
    if (typeof electronExport === 'string' && fs.existsSync(electronExport)) {
      return electronExport;
    }
  } catch {
    // Continue to fallback strategies
  }

  // Strategy 2: Inspect electron package directory directly (path.txt)
  const electronPkgDir = path.join(targetFrontendDir, 'node_modules', 'electron');
  const pathTxtPath = path.join(electronPkgDir, 'path.txt');

  if (fs.existsSync(pathTxtPath)) {
    try {
      const relPath = fs.readFileSync(pathTxtPath, 'utf-8').trim();
      const distCandidate = path.join(electronPkgDir, 'dist', relPath);
      if (fs.existsSync(distCandidate)) {
        return distCandidate;
      }
    } catch {
      // Ignore read error
    }
  }

  // Strategy 3: Standard platform-specific binary fallback
  const isWin = process.platform === 'win32';
  const isMac = process.platform === 'darwin';
  let fallbackBinary;

  if (isWin) {
    fallbackBinary = path.join(electronPkgDir, 'dist', 'electron.exe');
  } else if (isMac) {
    fallbackBinary = path.join(electronPkgDir, 'dist', 'Electron.app', 'Contents', 'MacOS', 'Electron');
  } else {
    fallbackBinary = path.join(electronPkgDir, 'dist', 'electron');
  }

  if (fs.existsSync(fallbackBinary)) {
    return fallbackBinary;
  }

  throw new Error(
    `Unable to resolve local Electron executable. Checked paths under ${electronPkgDir} but no binary was found.`
  );
}

/**
 * Check if an HTTP URL responds with a non-5xx status.
 */
function checkUrlReady(url, timeoutMs = 2000) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      resolve(res.statusCode < 500);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

/**
 * Poll an HTTP URL until ready or timeout.
 */
async function waitForHttp(url, maxWaitMs = 30000, intervalMs = 500) {
  const startTime = Date.now();
  while (Date.now() - startTime < maxWaitMs) {
    if (await checkUrlReady(url, 1500)) {
      return true;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return false;
}

/**
 * Ensure Next.js dev server is running.
 */
async function ensureFrontend() {
  const nextUrl = 'http://localhost:3000';
  const isAlreadyRunning = await checkUrlReady(nextUrl, 1000);

  if (isAlreadyRunning) {
    console.log('[DevRunner] Pre-existing Next.js dev server detected at http://localhost:3000. Reusing.');
    return true;
  }

  console.log('[DevRunner] Starting Next.js development server on port 3000...');

  const child = spawnNpm(['run', 'dev'], {
    cwd: frontendDir,
    env: { ...process.env, PORT: '3000' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  nextProcess = child;
  startedNext = true;

  child.stdout.on('data', (data) => {
    const line = data.toString().trim();
    if (line) console.log(`[Next.js] ${line}`);
  });

  child.stderr.on('data', (data) => {
    const line = data.toString().trim();
    if (line) console.error(`[Next.js] ${line}`);
  });

  child.on('exit', (code, signal) => {
    if (!isShuttingDown) {
      console.log(`[DevRunner] Next.js process exited unexpectedly with code ${code}, signal ${signal}`);
    }
    nextProcess = null;
  });

  child.on('error', (err) => {
    console.error('[DevRunner] Error spawning Next.js dev server:', err);
  });

  console.log('[DevRunner] Waiting for Next.js to compile and become ready...');
  const ready = await waitForHttp(nextUrl, 45000, 500);
  if (!ready) {
    console.error('[DevRunner] Next.js failed to become ready in time.');
    return false;
  }

  console.log('[DevRunner] Next.js is ready at http://localhost:3000.');
  return true;
}

/**
 * Clean up child processes started by this runner.
 */
function cleanup() {
  if (isShuttingDown) return;
  isShuttingDown = true;
  console.log('\n[DevRunner] Shutting down OmniSearch development environment...');

  // 1. Stop Next.js if started by us
  if (startedNext && nextProcess) {
    const pid = nextProcess.pid;
    console.log(`[DevRunner] Stopping Next.js dev server (PID: ${pid})...`);
    try {
      if (process.platform === 'win32') {
        execSync(`taskkill /pid ${pid} /T /F`, { stdio: 'ignore' });
      } else {
        nextProcess.kill('SIGTERM');
      }
    } catch {
      // Ignore cleanup error if process already exited
    }
    nextProcess = null;
  }

  // 2. Stop FastAPI if started by us
  backendManager.stop();

  console.log('[DevRunner] Cleanup complete. Exiting.');
}

// Register termination signal handlers
process.on('SIGINT', () => {
  cleanup();
  process.exit(0);
});
process.on('SIGTERM', () => {
  cleanup();
  process.exit(0);
});
process.on('exit', () => {
  cleanup();
});

/**
 * Main development run sequence.
 */
async function main() {
  console.log('====================================================');
  console.log('     OmniSearch Desktop Development Orchestrator    ');
  console.log('====================================================');

  // Step 1: Ensure FastAPI Backend is available & ready
  console.log('[Step 1/3] Checking FastAPI Backend readiness...');
  const backendReady = await backendManager.ensureBackend(rootDir);
  if (!backendReady) {
    console.error('[DevRunner] Aborting: Backend could not be started or reached.');
    cleanup();
    process.exit(1);
  }

  // Step 2: Ensure Next.js Dev Server is available & ready
  console.log('[Step 2/3] Checking Next.js Dev Server readiness...');
  const frontendReady = await ensureFrontend();
  if (!frontendReady) {
    console.error('[DevRunner] Aborting: Frontend could not be started or reached.');
    cleanup();
    process.exit(1);
  }

  // Step 3: Launch Electron directly via resolved executable
  console.log('[Step 3/3] Launching Electron desktop window directly...');

  let electronExecutable;
  try {
    electronExecutable = resolveElectronExecutable(frontendDir);
    console.log(`[DevRunner] Resolved Electron binary: ${electronExecutable}`);
  } catch (err) {
    console.error(`[DevRunner] ${err.message}`);
    cleanup();
    process.exit(1);
  }

  const electronEnv = {
    ...process.env,
    ELECTRON_START_URL: 'http://localhost:3000',
    BACKEND_URL: backendManager.backendUrl,
  };

  const mainScriptPath = path.join(frontendDir, 'electron', 'main.js');
  console.log(`[DevRunner] Spawning Electron executable with entry point: ${mainScriptPath}`);

  let electronProcess;
  try {
    electronProcess = spawn(electronExecutable, [mainScriptPath], {
      cwd: frontendDir,
      env: electronEnv,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: false,
    });
  } catch (err) {
    if (err.code === 'UNKNOWN' && process.platform === 'win32') {
      console.error('\n[DevRunner] ========================================================');
      console.error('[DevRunner] WINDOWS APPLICATION CONTROL POLICY NOTICE');
      console.error('[DevRunner] Windows Code Integrity / Application Control policy blocked the raw');
      console.error('[DevRunner] unsigned development electron.exe binary (Win32 Error 4551 / -4094).');
      console.error(`[DevRunner] Target binary: ${electronExecutable}`);
      console.error('[DevRunner] In enterprise environments, unsigned dev binaries require local');
      console.error('[DevRunner] developer policy exemption, or signing during packaging.');
      console.error('[DevRunner] ========================================================\n');
    } else {
      console.error('[DevRunner] Synchronous error launching Electron executable:', err);
    }
    cleanup();
    process.exit(1);
  }

  electronProcess.stdout.on('data', (data) => {
    const text = data.toString().trim();
    if (text) console.log(`[Electron] ${text}`);
  });

  electronProcess.stderr.on('data', (data) => {
    const text = data.toString().trim();
    if (text) console.error(`[Electron] ${text}`);
  });

  electronProcess.on('error', (err) => {
    if (err.code === 'UNKNOWN' && process.platform === 'win32') {
      console.error('\n[DevRunner] ========================================================');
      console.error('[DevRunner] WINDOWS APPLICATION CONTROL POLICY NOTICE');
      console.error('[DevRunner] Windows Code Integrity / Application Control policy blocked the raw');
      console.error('[DevRunner] unsigned development electron.exe binary (Win32 Error 4551 / -4094).');
      console.error(`[DevRunner] Target binary: ${electronExecutable}`);
      console.error('[DevRunner] ========================================================\n');
    } else {
      console.error('[DevRunner] Error launching Electron executable:', err);
    }
    cleanup();
    process.exit(1);
  });

  electronProcess.on('exit', (code, signal) => {
    console.log(`[DevRunner] Electron process exited with code ${code}, signal ${signal}.`);
    cleanup();
    process.exit(code || 0);
  });
}

main().catch((err) => {
  console.error('[DevRunner] Unexpected error during orchestration:', err);
  cleanup();
  process.exit(1);
});
