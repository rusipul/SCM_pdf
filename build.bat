@echo off
setlocal
pip install -r requirements-dev.txt
rem charset-normalizer's mypyc-compiled extension (.pyd) is incompatible with
rem PyInstaller onefile builds (confirmed by an actual build test). Force a
rem reinstall of the pure-Python variant to work around it.
pip install --no-binary charset-normalizer --force-reinstall --no-deps charset-normalizer
pyinstaller --onefile --windowed --name FedExInvoiceConverter gui.py
echo.
echo Build complete: dist\FedExInvoiceConverter.exe
pause
