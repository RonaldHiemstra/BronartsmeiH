@echo off
if not "%1"=="" set BRONARTSMEIH_IP=%1
if not defined BRONARTSMEIH_IP (
  echo Specify brewery IP-address or COM port as argument to this script, or define env:BRONARTSMEIH_IP
  pause
  exit /b 1
)

if not exist webrepl_cfg.py (
  echo webrepl_cfg.py is missing.
  echo Trying to download it from the controller...
  set /P webrepl_pw=Enter webrepl password:
  pushd %~dp0
  call :DOWNLOAD_FILE %webrepl_pw% webrepl_cfg.py
  popd
)

if not exist "%~dp0src\system_config.json" (
  echo Creating a default "%~dp0src\system_config.json".
  echo Please specify the following required information:
  set /P ssid=network ssid:
  set /P password=network password:
  set /P project_name=project name:
  set /P utc_offset=UTC offset:
)
rem environment variables are late evaluated...
if not exist "%~dp0src\system_config.json" (
  echo {"ssid": "%ssid%", "utc_offset": %utc_offset%, "__password": "%password%", "project_name": "%project_name%"}>"%~dp0src\system_config.json"
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
  echo [92mReboot the device to activate the changes![0m
  echo [93mimport machine; machine.reset^(^)[0m
  echo [92mor Ctrl-d in the micropython shell.[0m
)
exit /b

:UPLOAD_FILES
rem password: ^%1
call :UPLOAD_FILE %1 "%~dp0src\system_config.json"
call :UPLOAD_FILE %1 "%~dp0src\hardware_config.json"
pushd src
for /R %%f in (*.py) do call :UPLOAD_FILE %1 "%%f"
popd
for /R %%f in (..\picoweb\picoweb\*.py) do call :UPLOAD_FILE %1 "%%f" picoweb
for /R %%f in (..\github\ads1x15\*.py) do call :UPLOAD_FILE %1 "%%f"
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
if (%BRONARTSMEIH_IP:~0,3%)==COM (
  pushd %~dp2
  mpfshell -n -c "open %BRONARTSMEIH_IP%; put %3/%~nx2"
  popd
) else (
  echo [92m%cd%^>python "%~dp0../github/webrepl/webrepl_cli.py" -p ^<password^> "%_LOCAL_FILE%" %BRONARTSMEIH_IP%:%3/%~nx2[0m
  @python "%~dp0../github/webrepl/webrepl_cli.py" -p %1 "%_LOCAL_FILE%" %BRONARTSMEIH_IP%:%3/%~nx2 >nul
)
if errorlevel 1 (
  echo [91mOeps... something went wrong[0m
  if not "%3"=="" (
    echo [92mIf the folder %3 does not exist on the device, please create it[0m
    echo [93m^>^>^> uos.mkdir^('%3'^)[0m
    echo [92mand try again...[0m
  )
  pause
) else (
  xcopy /y "%2" "%~dp0\uploaded\%BRONARTSMEIH_IP%\%3\" >nul
)
exit /b

:DOWNLOAD_FILE
rem password: ^%1
rem filepath: %2
rem target folder: %3 [optional]
rem WORKAROUND: webrepl_cli.py does not support : in source and target...
rem Convert the absolute filepath including drive-letter to a absolute filepath without drive-letter
set _LOCAL_FILE=%~2
set _LOCAL_FILE=%_LOCAL_FILE:~2%
if (%BRONARTSMEIH_IP:~0,3%)==COM (
  pushd %~dp2
  mpfshell -n -c "open %BRONARTSMEIH_IP%; get %3/%~nx2"
  popd
) else (
  echo [92m%cd%^>python "%~dp0../github/webrepl/webrepl_cli.py" -p ^<password^> %BRONARTSMEIH_IP%:%3/%~nx2 "%_LOCAL_FILE%"[0m
  @python "%~dp0../github/webrepl/webrepl_cli.py" -p %1 %BRONARTSMEIH_IP%:%3/%~nx2 "%_LOCAL_FILE%" >nul
)
if errorlevel 1 (
  echo [91mOeps... something went wrong[0m
  pause
) else (
  rem source and target are in sync now; update the uploaded folder
  xcopy /y "%2" "%~dp0\uploaded\%BRONARTSMEIH_IP%\%3\" >nul
)
exit /b
