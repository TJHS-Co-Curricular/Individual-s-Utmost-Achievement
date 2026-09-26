@echo off
setlocal
rem ============================================================
rem  Start the site with LAN sharing.
rem  Colleagues on the same network can open  http://<this-PC-IP>:5000
rem  (the exact address is printed in the window below).
rem  They can view / search / download; only this PC can change
rem  the manual "count / don't count" adjustments.
rem ============================================================
pushd "%~dp0.."
if exist "Achievement-Award-Viewer.exe" (
    "Achievement-Award-Viewer.exe" --lan
) else (
    python app.py --lan
)
popd
pause
