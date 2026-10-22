@echo off
chcp 65001 >nul
title 校园票务系统 - 一键打包
rem 切换到本脚本所在目录（%~dp0 带结尾反斜杠），使脚本可放在任意路径下运行
cd /d "%~dp0"

echo ============================================
echo   [1/4] 停止占用 8080 的旧进程...
echo ============================================
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080 " ^| findstr "LISTENING"') do (
    echo   杀掉旧进程 PID=%%a
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 2 /nobreak >nul

echo.
echo ============================================
echo   [2/4] 构建前端 (npm run build)...
echo ============================================
cd frontend
call npm run build
if errorlevel 1 (
    echo [错误] 前端构建失败！
    pause
    exit /b 1
)
cd ..

echo.
echo ============================================
echo   [3/4] 同步 dist 到后端 static...
echo ============================================
if exist "src\main\resources\static" rmdir /s /q "src\main\resources\static"
xcopy "frontend\dist" "src\main\resources\static\" /E /I /Y >nul
echo   已同步

echo.
echo ============================================
echo   [4/4] Maven 打 jar...
echo ============================================
call mvnw.cmd package -DskipTests
if errorlevel 1 (
    echo [错误] Maven 打包失败！
    pause
    exit /b 1
)

echo.
echo ============================================
echo   打包完成！
echo   现在双击 启动系统.bat 即可
echo ============================================
pause
