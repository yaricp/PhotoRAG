# Windows clean reinstall test procedure

Use this procedure when you need to test PhotoRAG on Windows as if it had never been installed on the machine.

## 1. Close running apps

Close PhotoRAG and any open installer windows.

Open `cmd.exe` and move to a safe directory so Windows is not trying to delete the current working directory:

```cmd
cd /d %USERPROFILE%
```

## 2. Stop PhotoRAG-related processes

```cmd
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|PhotoRAG' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
```

## 3. Remove the installed app and user data

```cmd
powershell -NoProfile -Command "Remove-Item \"$env:LOCALAPPDATA\Programs\PhotoRAG\" -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item \"$env:APPDATA\PhotoRAG\" -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item \"$env:LOCALAPPDATA\PhotoRAG\" -Recurse -Force -ErrorAction SilentlyContinue"
```

## 4. Verify cleanup

```cmd
powershell -NoProfile -Command "Test-Path \"$env:LOCALAPPDATA\Programs\PhotoRAG\"; Test-Path \"$env:APPDATA\PhotoRAG\"; Test-Path \"$env:LOCALAPPDATA\PhotoRAG\""
```

Expected output:

```text
False
False
False
```

Verify that no PhotoRAG or PhotoRAG Python processes remain:

```cmd
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|PhotoRAG' } | Format-List ProcessId,Name,CommandLine"
```

Expected output: empty.

## 5. Verify the installer hash

Use the SHA256 published in the current release notes for the Windows x64 installer.

Check the downloaded installer, replacing the filename with the current release artifact name if needed:

```cmd
powershell -NoProfile -Command "Get-FileHash \"$env:USERPROFILE\Downloads\PhotoRAG-Setup-<version>-x64.exe\" -Algorithm SHA256"
```

## 6. Install from scratch

Run the current Windows x64 installer, for example:

```cmd
"%USERPROFILE%\Downloads\PhotoRAG-Setup-<version>-x64.exe"
```

If the installer is not in `Downloads`, run it from its actual location.

## 7. Check first-run dependency installation

During first-run setup, the `Installing collected packages` stage should visibly stay active in the wizard. The progress bar should animate, and the detail text should show that installation is still running.

The setup log should also contain heartbeat lines like:

```text
[setup:pip:installing] Installing packages: ...
```

Use this command to watch the log:

```cmd
powershell -NoProfile -Command "Get-Content \"$env:APPDATA\PhotoRAG\photorag.log\" -Tail 120 -Wait"
```
