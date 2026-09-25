@echo off
setlocal
rem ============================================================
rem  Allow colleagues on the same network to reach the site
rem  (Windows Firewall rule for TCP ports 5000-5019, Private and
rem  Domain networks only). Needs "Run as administrator".
rem  Only needed if you pressed "Cancel" on the Windows Firewall
rem  pop-up the first time you started with LAN sharing.
rem ============================================================
net session >nul 2>&1
if errorlevel 1 (
    echo [!] Please right-click this file and choose "Run as administrator".
    pause
    exit /b 1
)
netsh advfirewall firewall delete rule name="Utmost Achievement Calculator (LAN)" >nul 2>&1
netsh advfirewall firewall add rule name="Utmost Achievement Calculator (LAN)" dir=in action=allow protocol=TCP localport=5000-5019 profile=private,domain
if errorlevel 1 (
    echo [ERROR] Could not add the firewall rule.
    pause
    exit /b 1
)
echo.
echo Done. Colleagues on the same network can now open http://^<this-PC-IP^>:5000
echo If it still does not work, open Windows Settings - Network and make sure
echo this network is set to "Private" (not "Public").
echo To remove the rule later:
echo   netsh advfirewall firewall delete rule name="Utmost Achievement Calculator (LAN)"
pause
