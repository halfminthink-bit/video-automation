@echo off
echo Closing existing Chrome processes...
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 >nul

echo Starting Chrome in debug mode...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\hyokaimen\AppData\Local\Google\Chrome\User Data"

echo Chrome started on port 9222
echo You can now run your TikTok upload script.
pause


