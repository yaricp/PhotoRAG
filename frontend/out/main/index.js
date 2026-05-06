"use strict";
const electron = require("electron");
const path = require("path");
function registerIpcHandlers(backendPort) {
  console.log("[IPC] registering handlers, port =", backendPort);
  electron.ipcMain.handle("select-folder", async () => {
    const result = await electron.dialog.showOpenDialog({
      properties: ["openDirectory"],
      title: "Select Photos Folder"
    });
    return result.canceled ? null : result.filePaths[0];
  });
  console.log("[IPC] registering get-backend-port");
  electron.ipcMain.handle("get-backend-port", () => backendPort);
  console.log("[IPC] done");
}
let mainWindow = null;
async function createWindow() {
  console.log("[main] createWindow");
  const backendPort = 8e3;
  console.log("[MAIN] BEFORE IPC");
  registerIpcHandlers(backendPort);
  console.log("[MAIN] AFTER IPC");
  mainWindow = new electron.BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });
  if (!electron.app.isPackaged) {
    await mainWindow.loadURL("http://localhost:5173");
    mainWindow.webContents.openDevTools();
  } else {
    await mainWindow.loadFile("dist/index.html");
  }
}
electron.app.whenReady().then(createWindow);
