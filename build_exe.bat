@echo off
echo Cleaning old builds...
rmdir /s /q build
rmdir /s /q dist

echo Building Executable with PyInstaller...
pyinstaller --clean -y PostPocketPro.spec

echo Build complete! The results are available in: %CD%\dist
pause
