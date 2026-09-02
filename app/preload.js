// preload.js — мост между Electron main и renderer (изолированный контекст)
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('hermes', {
  sendChat: (text) => ipcRenderer.invoke('chat:send', text),
  getCommands: () => ipcRenderer.invoke('chat:commands'),
  getAppInfo: () => ipcRenderer.invoke('app:info'),
  reloadDashboard: () => ipcRenderer.invoke('window:reload-dashboard'),
});
