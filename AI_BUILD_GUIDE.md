# 🤖 AI Build Guide (32-bit Architecture)

> [!IMPORTANT]
> **This project MUST be built using 32-bit Python.**
> Kiwoom OpenAPI+ is an ActiveX control that only supports 32-bit environments. Building with 64-bit Python/PyInstaller will result in `DLL load failed`.

## 🛠 Required Environment

- **Python**: 3.12 (32-bit)
- **Path**: `C:\Users\a\AppData\Local\Programs\Python\Python312-32\python.exe`
- **Architecture Check**:
  ```powershell
  & "C:\Users\a\AppData\Local\Programs\Python\Python312-32\python.exe" -c "import platform; print(platform.architecture())"
  # Must output: ('32bit', 'WindowsPE')
  ```

## 📦 Build Instructions for AI

When asked to build this project, follow these exact steps:

### 1. Initialize 32-bit Build Tools

Ensure `pyinstaller` and `pywin32` are installed in the 32-bit environment:

```powershell
& "C:\Users\a\AppData\Local\Programs\Python\Python312-32\python.exe" -m pip install pyinstaller pywin32 PyQt5
```

### 2. Run PyInstaller

Always use the Python module runner (`-m PyInstaller`) from the 32-bit path to ensure the correct architecture is used:

```powershell
& "C:\Users\a\AppData\Local\Programs\Python\Python312-32\python.exe" -m PyInstaller build.spec --clean
```

### 3. Troubleshooting

- **"%1 is not a valid Win32 application"**: This means a 64-bit tool was used. Re-run Step 2 ensuring the path points to `Python312-32`.
- **"Qt plugin directory does not exist"**: This happens if the environment is not properly isolated. Using the global 32-bit path usually resolves this.

## 📄 Build Configuration

The project uses `build.spec`. Do not modify the `console=False` or `hiddenimports` unless necessary for new dependencies.
