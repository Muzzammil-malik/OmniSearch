/**
 * Electron Preload Script for OmniSearch.
 *
 * Implements strict security best practices:
 * - Context isolation enabled (contextIsolation: true)
 * - Node integration disabled (nodeIntegration: false)
 * - Minimal, strongly scoped bridge exposing ONLY safe folder-picker functionality
 * - No require() or arbitrary filesystem access exposed to renderer
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('omnisearch', {
  selectFolder: () => ipcRenderer.invoke('omnisearch:selectFolder'),
  platform: process.platform,
});

