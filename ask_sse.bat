@echo off
setlocal EnableExtensions
chcp 65001 >nul

rem ===== Defaults =====
set "API_URL=http://localhost:8000/api/chat"
set "K=5"
set "SESSION=demo"
rem ====================

if "%~1"=="" (
  echo Uso: %~n0 "pergunta..." [--sources] [--raw] [--no-aggressive]
  echo   --sources        Mostra 'event: sources' ao final
  echo   --raw            Desliga o pos-processamento de texto
  echo   --no-aggressive  Desliga a heuristica de juncao de micro-fragmentos
  exit /b 1
)

set "QUESTION=%~1"
set "SHOW_SOURCES=0"
set "RAW=0"
set "AGGRESSIVE=1"

:parse_args
shift
if "%~1"=="" goto run
if /I "%~1"=="--sources"       set "SHOW_SOURCES=1" & goto parse_args
if /I "%~1"=="--raw"           set "RAW=1"          & goto parse_args
if /I "%~1"=="--no-aggressive" set "AGGRESSIVE=0"   & goto parse_args
echo [ignorado] argumento desconhecido: %~1
goto parse_args

:run
set "PSFLAGS="
if "%SHOW_SOURCES%"=="1" set PSFLAGS=%PSFLAGS% -ShowSources
if "%RAW%"=="1"         set PSFLAGS=%PSFLAGS% -Raw
if "%AGGRESSIVE%"=="0"  set PSFLAGS=%PSFLAGS% -NoAggressive

where curl >nul 2>nul
if errorlevel 1 (
  echo ERRO: 'curl' nao encontrado no PATH. Instale ou adicione ao PATH.
  exit /b 2
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0ask_sse.ps1" ^
  -Question "%QUESTION%" -Url "%API_URL%" -K %K% -Session "%SESSION%" %PSFLAGS%

endlocal
