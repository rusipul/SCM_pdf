@echo off
setlocal
pip install -r requirements-dev.txt
pyinstaller --onefile --windowed --name "FedEx인보이스변환" gui.py
echo.
echo 빌드 완료: dist\FedEx인보이스변환.exe
pause
