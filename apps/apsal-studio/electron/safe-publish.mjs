export function publishToWindow(targetWindow, channel, value, { quitting = false } = {}) {
  if (quitting || !targetWindow) return false
  try {
    if (targetWindow.isDestroyed()) return false
    const contents = targetWindow.webContents
    if (!contents || contents.isDestroyed()) return false
    contents.send(channel, value)
    return true
  } catch {
    // BrowserWindow and WebContents can be destroyed between the guards and send during shutdown.
    return false
  }
}
