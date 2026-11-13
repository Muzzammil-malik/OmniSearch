/**
 * Electron Preload Script for OmniSearch.
 *
 * Implements strict security best practices:
 * - Context isolation enabled (contextIsolation: true)
 * - Node integration disabled (nodeIntegration: false)
 * - Strongly scoped bridge exposing safe folder-picker, file actions, and explorer integration
 * - No require() or arbitrary filesystem access exposed to renderer
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('omnisearch', {
  selectFolder: () => ipcRenderer.invoke('omnisearch:selectFolder'),
  openFile: (filePath) => ipcRenderer.invoke('omnisearch:openFile', filePath),
  revealFile: (filePath) => ipcRenderer.invoke('omnisearch:revealFile', filePath),
  getBackendUrl: () => ipcRenderer.sendSync('omnisearch:getBackendUrlSync'),
  getAppInfo: () => ipcRenderer.invoke('omnisearch:getAppInfo'),
  isContextMenuRegistered: () => ipcRenderer.invoke('omnisearch:isContextMenuRegistered'),
  setContextMenu: (enable) => ipcRenderer.invoke('omnisearch:setContextMenu', enable),
  getInitialFolderPath: () => ipcRenderer.invoke('omnisearch:getInitialFolderPath'),
  onOpenFolderPath: (callback) => {
    const handler = (_event, folderPath) => {
      if (typeof callback === 'function') {
        callback(folderPath);
      }
    };
    ipcRenderer.on('omnisearch:openFolderPath', handler);
    return () => ipcRenderer.removeListener('omnisearch:openFolderPath', handler);
  },
  platform: process.platform,
});
