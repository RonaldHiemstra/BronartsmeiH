@echo off
if not "%1"=="" set BRONARTSMEIH_IP=%1
if not defined BRONARTSMEIH_IP (
  echo Specify BronartsmeiH IP-address as argument to this script, or define env:BRONARTSMEIH_IP
  pause
  exit /b 1
)

if not exist webrepl_cfg.py (
  echo webrepl_cfg.py is missing.
  echo Trying to download it from the controller...
  set /P webrepl_pw=Enter webrepl password:
  pushd %~dp0
  @python ../github/webrepl/webrepl_cli.py -p %webrepl_pw% %BRONARTSMEIH_IP%:webrepl_cfg.py webrepl_cfg.py >nul
  popd
)

for /F "delims=', tokens=2" %%p in (webrepl_cfg.py) do call :UPLOAD_FILES %%p
if errorlevel 1 (
  echo Oeps... something went wrong
  echo Possible reason:
  echo   Missing or corrupt file "webrepl_cfg.py"
  echo   this file should contain:
  echo PASS = '^<repl_password^>'
  pause
) else (
  echo Reboot the device to activate the changes!
  echo Ctrl-c -^> Ctrl-d in the micropython shell
)
exit /b

:UPLOAD_FILES
rem password: ^%1
call :UPLOAD_FILE %1 "%~dp0src\system_config.json"
pushd src
for /R %%f in (*.py) do call :UPLOAD_FILE %1 "%%f"
popd
for /R %%f in (..\picoweb\picoweb\*.py) do call :UPLOAD_FILE %1 "%%f" picoweb
exit /b 0

:UPLOAD_FILE
rem password: ^%1
rem filepath: %2
rem target folder: %3 [optional]
fc %2 "%~dp0\uploaded\%BRONARTSMEIH_IP%\%3\%~nx2" >nul 2>&1
if %errorlevel%==0 (
  echo Up to date; skipping: %2
  exit /b
)
rem WORKAROUND: webrepl_cli.py does not support : in source and target...
rem Convert the absolute filepath including drive-letter to a absolute filepath without drive-letter
set _LOCAL_FILE=%~2
set _LOCAL_FILE=%_LOCAL_FILE:~2%
echo %cd%^>python "%~dp0../github/webrepl/webrepl_cli.py" -p ^<password^> "%_LOCAL_FILE%" %BRONARTSMEIH_IP%:%3/%~nx2
@python "%~dp0../github/webrepl/webrepl_cli.py" -p %1 "%_LOCAL_FILE%" %BRONARTSMEIH_IP%:%3/%~nx2 >nul
if errorlevel 1 (
  echo Oeps... something went wrong
  if not "%3"=="" echo If %3 is not a folder, please create the folder on the device uos.mkdir^('%3'^) and try again
  pause
) else (
  xcopy /y "%2" "%~dp0\uploaded\%BRONARTSMEIH_IP%\%3\" >nul
)
exit /b
