@echo off
rem Tok2Tube installer: makes a private Python environment in this folder, installs what it needs,
rem and puts a Tok2Tube shortcut on your desktop. Run it again any time to update.
setlocal
cd /d "%~dp0"

set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
  echo Python 3.10 or newer is needed. Get it from https://www.python.org/downloads/ ^(tick "Add to PATH"^),
  echo then run install.bat again.
  pause
  exit /b 1
)

if not exist .venv (
  echo Creating the environment...
  %PY% -m venv .venv || goto :fail
)
echo Installing packages...
.venv\Scripts\python.exe -m ensurepip --upgrade >nul 2>nul
.venv\Scripts\python.exe -m pip install --upgrade pip >nul
.venv\Scripts\python.exe -m pip install --upgrade -r requirements.txt || goto :fail

echo Making the desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Tok2Tube.lnk'));" ^
  "$s.TargetPath='%CD%\.venv\Scripts\pythonw.exe'; $s.Arguments='\"%CD%\Tok2Tube.pyw\"'; $s.WorkingDirectory='%CD%';" ^
  "$s.IconLocation='%CD%\tok2tube\icon.ico'; $s.Description='TikTok posts to YouTube Shorts'; $s.Save()" || goto :fail

echo.
echo Done. Open Tok2Tube from your desktop.
pause
exit /b 0

:fail
echo.
echo Something went wrong above. Copy the error into a GitHub issue if you need help.
pause
exit /b 1
