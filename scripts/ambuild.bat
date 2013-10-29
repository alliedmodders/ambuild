@echo off

REM WTFFFFFFFFFFF Python doesn't add itself to PATH!

setlocal

IF EXIST "%~dp0..\python.exe" (
  set PYTHON_EXE="%~dp0..\python"
ELSE
  set PYTHON_EXE=python

%PYTHON_EXE% "%~dp0ambuild" %*

exit /b %ERRORLEVEL%
