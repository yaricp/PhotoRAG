"use strict";
const electron = require("electron");
const path = require("path");
let win = null;
function createWindow() {
  win = new electron.BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  const devUrl = "http://127.0.0.1:5173";
  win.loadURL(devUrl);
  win.webContents.openDevTools();
  win.on("closed", () => {
    win = null;
  });
}
electron.app.whenReady().then(createWindow);
electron.app.on("window-all-closed", () => {
  if (process.platform !== "darwin") electron.app.quit();
});
