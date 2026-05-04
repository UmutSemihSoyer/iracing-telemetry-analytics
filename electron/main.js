const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');

let mainWindow;
let pythonProcess;

const DASH_PORT = 8050;
const DASH_URL = `http://127.0.0.1:${DASH_PORT}`;

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    title: "iRacing Telemetry Analytics",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  mainWindow.loadURL(DASH_URL);

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

function startPythonServer() {
  console.log('Starting Python server...');
  
  // Determine Python path: embedded or system
  // If packaged, look for python_embed folder. Otherwise use system 'python'
  let pythonExecutable = 'python';
  let scriptPath = path.join(__dirname, '../app.py');
  
  if (app.isPackaged) {
    pythonExecutable = path.join(process.resourcesPath, 'python_embed', 'python.exe');
    scriptPath = path.join(process.resourcesPath, 'app.py');
  }

  pythonProcess = spawn(pythonExecutable, [scriptPath, '--electron'], {
    cwd: app.isPackaged ? process.resourcesPath : path.join(__dirname, '..')
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python]: ${data.toString()}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python Error]: ${data.toString()}`);
  });
}

function waitForServer() {
  console.log('Waiting for Dash server...');
  const interval = setInterval(() => {
    http.get(DASH_URL, (res) => {
      if (res.statusCode === 200) {
        clearInterval(interval);
        console.log('Dash server is up. Creating window...');
        createMainWindow();
      }
    }).on('error', (err) => {
      // Still waiting
    });
  }, 500);
}

app.on('ready', () => {
  startPythonServer();
  waitForServer();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('will-quit', () => {
  if (pythonProcess) {
    console.log('Killing Python process...');
    pythonProcess.kill();
  }
});

// IPC Handlers for Native Dialogs
ipcMain.handle('open-file-dialog', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Select iRacing Telemetry File',
    properties: ['openFile', 'multiSelections'],
    filters: [
      { name: 'iRacing Telemetry', extensions: ['ibt'] },
      { name: 'CSV File', extensions: ['csv'] }
    ]
  });
  return result.filePaths;
});

ipcMain.handle('open-folder-dialog', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: 'Select iRacing Telemetry Folder',
    properties: ['openDirectory', 'showHiddenFiles'],
    filters: [
      { name: 'iRacing Telemetry', extensions: ['ibt'] }
    ]
  });
  return result.filePaths;
});

ipcMain.handle('get-telemetry-path', () => {
  const home = app.getPath('documents');
  return path.join(home, 'iRacing', 'telemetry');
});
