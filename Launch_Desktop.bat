@echo off
title iRacing Telemetry Analytics - Desktop Launcher
echo Starting iRacing Telemetry Analytics (Professional Desktop Edition)...
echo.

:: Go to electron directory
cd electron

:: Run npm start which triggers both the Python backend and Electron frontend
npm start

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Could not start Electron. 
    echo Make sure you have Node.js installed and ran 'npm install' in the electron folder.
    pause
)
