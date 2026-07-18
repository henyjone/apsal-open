const { contextBridge, ipcRenderer } = require('electron')

function subscription(channel, listener) {
  const wrapped = (_event, value) => listener(value)
  ipcRenderer.on(channel, wrapped)
  return () => ipcRenderer.removeListener(channel, wrapped)
}

contextBridge.exposeInMainWorld('apsalProtocol', {
  getStatus: () => ipcRenderer.invoke('apsal-protocol:status'),
  chooseProject: (mode) => ipcRenderer.invoke('apsal-protocol:choose-project', mode),
  call: (method, params) => ipcRenderer.invoke('apsal-protocol:call', { method, params }),
  getLinkStatus: () => ipcRenderer.invoke('apsal-link:status'),
  onStatus: (listener) => subscription('apsal-protocol:status', listener),
  onSnapshot: (listener) => subscription('apsal-protocol:snapshot', listener),
  onChange: (listener) => subscription('apsal-protocol:change', listener),
  onFocus: (listener) => subscription('apsal-protocol:focus', listener),
  onLinkStatus: (listener) => subscription('apsal-link:status', listener),
})
