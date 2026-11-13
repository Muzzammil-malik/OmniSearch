/**
 * Windows Explorer Context Menu Integration Service for OmniSearch Desktop.
 *
 * Responsibilities:
 * - Register/Unregister "Search with OmniSearch" in Windows Explorer context menu
 * - Support Directory (folder in file pane), Folder (desktop/nav pane), and Directory\Background (folder canvas)
 * - Safe per-user registration in HKCU\Software\Classes (no administrator rights needed)
 * - Support both Packaged (.exe) and Development mode with valid Win32 executable targets and icons
 * - Refresh Windows Explorer shell cache via SHChangeNotify(SHCNE_ASSOCCHANGED)
 * - Robust folder path extraction from process.argv and second-instance command line
 */

const { app } = require('electron');
const path = require('path');
const fs = require('fs');
const { execFile } = require('child_process');

const MENU_TEXT = 'Search with OmniSearch';
const REG_KEYS = [
  'HKCU\\Software\\Classes\\Directory\\shell\\OmniSearch',
  'HKCU\\Software\\Classes\\Directory\\Background\\shell\\OmniSearch',
  'HKCU\\Software\\Classes\\Folder\\shell\\OmniSearch',
];

class ExplorerIntegrationService {
  constructor() {
    this.menuText = MENU_TEXT;
  }

  isWindows() {
    return process.platform === 'win32';
  }

  /**
   * Resolves the actual Electron executable for development or packaged mode.
   * Never falls back to node.exe since node.exe cannot run Electron's main process.
   */
  getExecutablePath() {
    // 1. Packaged production executable: e.g. "C:\Program Files\OmniSearch\OmniSearch.exe"
    if (app && app.isPackaged) {
      return process.execPath;
    }

    // 2. If already running inside Electron runtime
    if (process.versions && process.versions.electron && process.execPath && !process.execPath.toLowerCase().endsWith('node.exe')) {
      return process.execPath;
    }

    // 3. Resolve project's local electron executable
    const localDistExe = path.resolve(__dirname, '..', 'node_modules', 'electron', 'dist', 'electron.exe');
    if (fs.existsSync(localDistExe)) {
      return localDistExe;
    }

    // 4. Try electron npm module export
    try {
      const electronPath = require('electron');
      if (typeof electronPath === 'string' && fs.existsSync(electronPath)) {
        return electronPath;
      }
    } catch {
      // Ignore require error
    }

    return process.execPath;
  }

  /**
   * Generates the command string to be executed when the context menu item is clicked.
   */
  getCommand() {
    const exePath = this.getExecutablePath();
    if (app && app.isPackaged) {
      return `"${exePath}" --open-folder "%V"`;
    }

    // Development mode: pass main.js entry point explicitly
    const mainScript = path.resolve(__dirname, 'main.js');
    return `"${exePath}" "${mainScript}" --open-folder "%V"`;
  }

  /**
   * Generates a valid Win32 icon reference for the context menu.
   * Note: Windows Shell requires an .exe, .dll, or .ico file; .png is NOT supported.
   */
  getIconPath() {
    const exePath = this.getExecutablePath();
    if (fs.existsSync(exePath)) {
      return exePath;
    }
    return '';
  }

  /**
   * Helper to execute reg.exe asynchronously.
   */
  runReg(args) {
    return new Promise((resolve) => {
      execFile('reg.exe', args, (error, stdout, stderr) => {
        if (error) {
          resolve({ success: false, code: error.code, stdout, stderr });
        } else {
          resolve({ success: true, code: 0, stdout, stderr });
        }
      });
    });
  }

  /**
   * Invalidate Windows Explorer shell icon and association caches without killing explorer.exe.
   * Sends SHCNE_ASSOCCHANGED (0x08000000).
   */
  notifyShell() {
    if (!this.isWindows()) return;
    const psCmd =
      'Add-Type -TypeDefinition "using System; using System.Runtime.InteropServices; public class S { [DllImport(\\\"shell32.dll\\\")] public static extern void SHChangeNotify(int e, int f, IntPtr a, IntPtr b); }"; [S]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)';
    execFile('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', psCmd], () => {});
  }

  /**
   * Check if OmniSearch context menu is currently registered in Windows Explorer.
   */
  async isRegistered() {
    if (!this.isWindows()) return false;

    try {
      const res = await this.runReg(['query', REG_KEYS[0], '/ve']);
      if (!res.success) return false;
      return typeof res.stdout === 'string' && res.stdout.includes(this.menuText);
    } catch (err) {
      console.error('[ExplorerService] Error querying registry:', err);
      return false;
    }
  }

  /**
   * Register "Search with OmniSearch" in the Windows Explorer folder context menu.
   */
  async register() {
    if (!this.isWindows()) {
      return { success: false, error: 'Context menu integration is only supported on Windows.' };
    }

    const commandStr = this.getCommand();
    const iconPath = this.getIconPath();

    try {
      for (const baseKey of REG_KEYS) {
        // 1. Set Menu item text: (Default) = "Search with OmniSearch"
        const r1 = await this.runReg(['add', baseKey, '/ve', '/d', this.menuText, '/f']);
        if (!r1.success) {
          return { success: false, error: r1.stderr || `Failed to create registry key ${baseKey}` };
        }

        // 2. Set Icon (if available and valid Win32 executable/icon)
        if (iconPath) {
          await this.runReg(['add', baseKey, '/v', 'Icon', '/d', iconPath, '/f']);
        }

        // 3. Set command: (Default) = "<executable>" [main.js] --open-folder "%V"
        const cmdKey = `${baseKey}\\command`;
        const r2 = await this.runReg(['add', cmdKey, '/ve', '/d', commandStr, '/f']);
        if (!r2.success) {
          return { success: false, error: r2.stderr || `Failed to set command key ${cmdKey}` };
        }
      }

      // Notify Windows Explorer to refresh its context-menu cache
      this.notifyShell();

      console.log('[ExplorerService] Context menu successfully registered across Directory, Background, and Folder.');
      return { success: true };
    } catch (err) {
      console.error('[ExplorerService] Error registering context menu:', err);
      return { success: false, error: err.message || String(err) };
    }
  }

  /**
   * Unregister "Search with OmniSearch" from the Windows Explorer folder context menu.
   */
  async unregister() {
    if (!this.isWindows()) {
      return { success: true };
    }

    try {
      for (const baseKey of REG_KEYS) {
        await this.runReg(['delete', baseKey, '/f']);
      }

      // Invalidate Explorer cache
      this.notifyShell();

      console.log('[ExplorerService] Context menu successfully removed.');
      return { success: true };
    } catch (err) {
      console.error('[ExplorerService] Error unregistering context menu:', err);
      return { success: false, error: err.message || String(err) };
    }
  }

  /**
   * Extract and validate a folder path from process arguments or second-instance command line.
   *
   * @param {string[]} args Command-line arguments array.
   * @returns {string | null} Normalized, validated folder path if valid, or null.
   */
  extractFolderPath(args) {
    if (!Array.isArray(args) || args.length === 0) return null;

    let candidatePath = null;

    // 1. Check for explicit --open-folder <path> or --open-folder=<path>
    for (let i = 0; i < args.length; i++) {
      const arg = args[i];
      if (arg === '--open-folder' && i + 1 < args.length) {
        candidatePath = args[i + 1];
        break;
      }
      if (typeof arg === 'string' && arg.startsWith('--open-folder=')) {
        candidatePath = arg.substring('--open-folder='.length);
        break;
      }
    }

    // 2. Fallback: Check trailing positional arguments that are directories
    if (!candidatePath) {
      for (let i = args.length - 1; i >= 0; i--) {
        const item = args[i];
        if (
          typeof item === 'string' &&
          item.trim() &&
          !item.startsWith('-') &&
          !item.toLowerCase().endsWith('.js') &&
          !item.toLowerCase().endsWith('electron.exe')
        ) {
          try {
            const resolved = path.resolve(item.trim());
            if (fs.existsSync(resolved) && fs.statSync(resolved).isDirectory()) {
              candidatePath = resolved;
              break;
            }
          } catch {
            // Ignore stat failures
          }
        }
      }
    }

    if (!candidatePath || typeof candidatePath !== 'string') {
      return null;
    }

    // 3. Normalize & validate filesystem directory
    try {
      const trimmed = candidatePath.trim().replace(/^["']|["']$/g, '');
      const resolved = path.resolve(trimmed);
      if (fs.existsSync(resolved) && fs.statSync(resolved).isDirectory()) {
        return resolved;
      }
    } catch (err) {
      console.warn('[ExplorerService] Invalid directory path candidate:', candidatePath, err);
    }

    return null;
  }
}

module.exports = {
  ExplorerIntegrationService,
};
