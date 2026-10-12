@echo off
rem Creates .venv-win next to this script and installs the dependencies of busytag.py.
rem Separate from .venv (created by setup-venv.sh under WSL/Linux) so both can coexist.
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)

%PY% -m venv .venv-win || goto :error
.venv-win\Scripts\python -m pip install --upgrade pip || goto :error
rem Pillow >= 10.1 is required for ImageFont.load_default(size=...)
.venv-win\Scripts\python -m pip install pyserial "pillow>=10.1" || goto :error

echo Done. Activate with: .venv-win\Scripts\activate
exit /b 0

:error
echo Setup failed.
exit /b 1
