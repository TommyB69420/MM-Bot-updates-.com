@echo off
setlocal

:: ====== Configuration ======
set "REPO_URL=https://github.com/TommyB69420/MM-Bot-.com.git"

echo.
echo ==========================================
echo     MafiaMatrix Bot Safe Self-Updater
echo ==========================================
echo.

:: Step 1: Check if Git is installed
where git >nul 2>&1
if %errorlevel%==0 (
    echo Git is already installed.
) else (
    echo Git not found. Installing Git...

    set "gitInstaller=Git-Installer.exe"
    set "gitUrl=https://github.com/git-for-windows/git/releases/latest/download/Git-2.45.1-64-bit.exe"

    powershell -Command "Invoke-WebRequest -Uri \"%gitUrl%\" -OutFile \"%gitInstaller%\"" >nul 2>&1

    if not exist "%gitInstaller%" (
        echo Failed to download Git installer. Aborting.
        pause
        exit /b
    )

    "%gitInstaller%" /VERYSILENT /NORESTART /SUPPRESSMSGBOXES
    set "PATH=%ProgramFiles%\Git\cmd;%PATH%"
    del "%gitInstaller%"

    echo Git installed successfully.
)

:: Step 2: Confirm this folder is a Git repo or clone fresh
cd /d %~dp0
if not exist ".git" (
    echo Initializing Git and pulling fresh files...
    git init
    git remote add origin %REPO_URL%
)

:: Step 3: Fetch updates
echo Fetching updates from GitHub...
git fetch origin

:: Step 4: Checkout latest changes WITHOUT overwriting settings.ini or game_data
echo Updating repository while preserving settings.ini and game_data...
git checkout origin/main -- . 2>nul

:: Explicitly remove settings.ini and game_data from staging to avoid overwriting
git restore --staged settings.ini 2>nul
git restore --staged game_data/* 2>nul

:: Pull and overwrite all except ignored files
git reset --hard origin/main

:: Restore preserved files
if exist settings.ini (
    echo Preserving local settings.ini
) else (
    echo No local settings.ini found.
)

if exist game_data (
    echo Preserving local game_data directory
) else (
    echo No local game_data folder found.
)

echo.
echo Update complete! settings.ini and game_data preserved.
pause
exit /b
