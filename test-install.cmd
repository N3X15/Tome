@echo off
set TOME_ROOT=%~dp0
cd %TOME_ROOT%
call python tome.py install
pause