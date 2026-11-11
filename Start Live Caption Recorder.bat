@echo off
rem Launch Live Caption Recorder from a source checkout.
cd /d "%~dp0"
start "" pythonw run.pyw %*
