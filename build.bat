@echo off
echo Installing PyInstaller...
pip install pyinstaller --quiet

echo Building Fabled.exe...
pyinstaller --onefile --windowed --name "Fabled" --distpath "." main.py

echo.
if exist "Fabled.exe" (
    echo Build successful! Executable is at: Fabled.exe
) else (
    echo Build failed. Check the output above for errors.
)
pause
