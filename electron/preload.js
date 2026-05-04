const { contextBridge, ipcRenderer } = require('electron');

// Expose safe APIs to the renderer (Dash window)
contextBridge.exposeInMainWorld('electronAPI', {
  openFileDialog: () => ipcRenderer.invoke('open-file-dialog'),
  openFolderDialog: () => ipcRenderer.invoke('open-folder-dialog'),
  getDefaultTelemetryPath: () => ipcRenderer.invoke('get-telemetry-path')
});

// We can also inject scripts once DOM is ready if needed, 
// but Dash handles its own DOM. We'll use clientside callbacks in Dash instead.
