@echo off
chcp 65001 >nul
title 校园票务系统 - 启动中
rem 切换到本脚本所在目录（%~dp0 带结尾反斜杠）：
rem 应用配置中的 Python 脚本路径为相对路径，工作目录必须是项目根目录
cd /d "%~dp0"
echo ============================================
echo   校园票务系统正在后台启动...
echo   看到 "Started CampusTicketApplication" 即为成功
echo   启动后请勿关闭本窗口，关闭即停止服务
echo   访问地址: http://localhost:8080
echo ============================================
java -jar target\campus-ticket-0.1.0.jar
pause