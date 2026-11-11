@echo off
rem Launch Linger from a source checkout.
cd /d "%~dp0"
start "" pythonw run.pyw %*
