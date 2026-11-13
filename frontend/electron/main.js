/**
 * Electron Main Process for OmniSearch Desktop Application.
 *
 * Responsibilities:
 * - Application window lifecycle management
 * - Single-instance enforcement
 * - Secure context isolation and sandboxed web preferences
 * - Safe navigation policy (external links opened in default OS browser)
 * - Managed backend lifecycle integration
 * - Native desktop IPC integration (Folder picker, Open File, Reveal in Explorer)
 * - Windows Explorer context-menu integration ("Search with OmniSearch")
 * - Single-instance folder path handoff (startup and second-instance activation)
 */

if (process.env.ELECTRON_RUN_AS_NODE) {
  delete process.env.ELECTRON_RUN_AS_NODE;
}

const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { BackendManager } = require('./backend-manager');
const { ExplorerIntegrationService } = require('./explorer-service');

const rootDir = path.resolve(__dirname, '..', '..');

const explorerService = new ExplorerIntegrationService();
let pendingInitialFolderPath = explorerService.extractFolderPath(process.argv);

// Enforce single application instance
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  console.log('[OmniSearch] Another instance is already running. Exiting.');
  app.quit();
}

let mainWindow = null;
const backendManager = new BackendManager({
  port: process.env.BACKEND_PORT ? parseInt(process.env.BACKEND_PORT, 10) : 8000,
  host: process.env.BACKEND_HOST || '127.0.0.1',
});

function createWindow() {
  const iconPath = path.join(__dirname, '..', 'public', 'assets', 'OmniSearch_Logo.png');

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 840,
    minWidth: 900,
    minHeight: 600,
    title: 'OmniSearch',
    backgroundColor: '#06141B',
    autoHideMenuBar: true,
    icon: fs.existsSync(iconPath) ? iconPath : undefined,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // Secure navigation: external HTTP(S) links open in system default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http:') || url.startsWith('https:')) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  const startUrl = process.env.ELECTRON_START_URL || 'http://localhost:3000';
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith(startUrl)) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  // When frontend finishes loading, push initial folder path if one was provided at startup
  mainWindow.webContents.on('did-finish-load', () => {
    if (pendingInitialFolderPath) {
      const folderToDeliver = pendingInitialFolderPath;
      setTimeout(() => {
        if (mainWindow && !mainWindow.isDestroyed()) {
          console.log('[OmniSearch] Delivering startup folder path to renderer:', folderToDeliver);
          mainWindow.webContents.send('omnisearch:openFolderPath', folderToDeliver);
        }
      }, 600);
    }
  });

  mainWindow.loadURL(startUrl);

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// ----------------------------------------------------------------------------
// IPC Handlers
// ----------------------------------------------------------------------------

// Native folder picker
ipcMain.handle('omnisearch:selectFolder', async () => {
  if (!mainWindow) return null;

  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Select Folder for OmniSearch Library',
    buttonLabel: 'Select Folder',
    properties: ['openDirectory', 'createDirectory'],
  });

  if (result.canceled || !result.filePaths || result.filePaths.length === 0) {
    return null;
  }

  return result.filePaths[0];
});

// Safe Open File with host OS default application
ipcMain.handle('omnisearch:openFile', async (_event, filePath) => {
  if (typeof filePath !== 'string' || !filePath.trim()) {
    return { success: false, error: 'Invalid file path' };
  }

  const resolved = path.resolve(filePath.trim());
  if (!fs.existsSync(resolved)) {
    return { success: false, error: 'File no longer exists at this location.' };
  }

  try {
    const err = await shell.openPath(resolved);
    if (err) {
      return { success: false, error: err };
    }
    return { success: true };
  } catch (exc) {
    return { success: false, error: exc.message || String(exc) };
  }
});

// Safe Reveal in Windows File Explorer
ipcMain.handle('omnisearch:revealFile', async (_event, filePath) => {
  if (typeof filePath !== 'string' || !filePath.trim()) {
    return { success: false, error: 'Invalid file path' };
  }

  const resolved = path.resolve(filePath.trim());
  if (!fs.existsSync(resolved)) {
    return { success: false, error: 'File no longer exists at this location.' };
  }

  try {
    shell.showItemInFolder(resolved);
    return { success: true };
  } catch (exc) {
    return { success: false, error: exc.message || String(exc) };
  }
});

// Windows Explorer context menu registration status
ipcMain.handle('omnisearch:isContextMenuRegistered', async () => {
  return await explorerService.isRegistered();
});

// Windows Explorer context menu enable/disable
ipcMain.handle('omnisearch:setContextMenu', async (_event, enable) => {
  if (enable) {
    return await explorerService.register();
  } else {
    return await explorerService.unregister();
  }
});

// Deliver startup folder path when renderer queries on mount
ipcMain.handle('omnisearch:getInitialFolderPath', () => {
  const current = pendingInitialFolderPath;
  pendingInitialFolderPath = null;
  return current;
});

// Backend URL synchronous resolver for renderer API client
ipcMain.on('omnisearch:getBackendUrlSync', (event) => {
  event.returnValue = backendManager.backendUrl;
});

// Basic application metadata
ipcMain.handle('omnisearch:getAppInfo', () => {
  return {
    name: app.getName(),
    version: app.getVersion(),
    platform: process.platform,
  };
});

// ----------------------------------------------------------------------------
// App Lifecycle
// ----------------------------------------------------------------------------

app.on('second-instance', (_event, commandLine) => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();

    const folderPath = explorerService.extractFolderPath(commandLine);
    if (folderPath) {
      console.log('[OmniSearch] Second instance requested folder search:', folderPath);
      mainWindow.webContents.send('omnisearch:openFolderPath', folderPath);
    }
  }
});

app.whenReady().then(async () => {
  // Optional in-process backend management (can also be handled by dev runner)
  if (process.env.ELECTRON_MANAGE_BACKEND === '1') {
    await backendManager.ensureBackend(rootDir);
  }
  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

app.on('will-quit', () => {
  backendManager.stop();
});
