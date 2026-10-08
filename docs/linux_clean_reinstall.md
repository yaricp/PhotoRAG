# PhotoRAG complete removal and clean reinstall procedure for Linux

Use this procedure to remove PhotoRAG completely for the current Linux user, or to prepare for a first-launch test. It removes the AppImage copy kept by PhotoRAG, its application-menu entry and icon, and its user data, including the photo database, task queues, settings, Python environment, caches, and models downloaded by PhotoRAG. **Your original photo files are not deleted.**

These instructions cover the x86_64 AppImage. No administrator password is needed. For other platforms, see the [macOS](macos_clean_reinstall.md) and [Windows](windows_clean_reinstall.md) procedures.

## 1. Quit PhotoRAG

Choose **PhotoRAG → Quit** and wait a few seconds for its processes to exit. In a terminal, check for remaining PhotoRAG processes:

```bash
ps -eo pid=,args= | grep -E '[P]hotoRAG|[p]hotorag'
```

If the command lists a PhotoRAG process, stop only that process with `kill PID`, replacing `PID` with the number shown. Repeat the check before deleting files. Do not stop every process named `python`; other applications may use Python too.

## 2. Inspect and remove PhotoRAG

The commands below use the standard Linux locations. If PhotoRAG was launched with custom `XDG_CONFIG_HOME` or `XDG_DATA_HOME` values, run the commands in that same environment or replace the variables with those locations.

```bash
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
ls -ld "$HOME/Applications/PhotoRAG.AppImage" \
  "$HOME/Applications/.photorag-appimage.json" \
  "$CONFIG_HOME/PhotoRAG" \
  "$DATA_HOME/applications/com.photorag.app.desktop" \
  "$DATA_HOME/icons/com.photorag.app.png" 2>/dev/null || true
```

Remove those PhotoRAG files and directories:

```bash
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -rf -- "$CONFIG_HOME/PhotoRAG" "$HOME/Applications/PhotoRAG.AppImage"
rm -f -- "$HOME/Applications/.photorag-appimage.json" \
  "$DATA_HOME/applications/com.photorag.app.desktop" \
  "$DATA_HOME/icons/com.photorag.app.png"
```

The `PhotoRAG` data directory contains the database and indexes, queues, `.env` settings, `setup_done` marker, Python virtual environment, and PhotoRAG-managed model cache. Removing it also resets the setup wizard. The app keeps a copy of the AppImage in `~/Applications` so it can still launch from the desktop menu if the downloaded file is deleted.

## 3. Remove the downloaded AppImage

PhotoRAG does not delete the original AppImage you downloaded. In the file manager, delete the file named `PhotoRAG-<version>-x86_64.AppImage` from Downloads or from wherever you saved it. You can also remove it from a terminal by replacing the example path with the file's actual path:

```bash
rm -i -- "$HOME/Downloads/PhotoRAG-<version>-x86_64.AppImage"
```

The `-i` option asks before removing the file. If you launched an AppImage from a different location, remove that copy too. When the source and `~/Applications` copy were hard-linked, deleting both paths removes the file contents and frees the disk space.

## 4. Verify cleanup

```bash
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
for path in "$CONFIG_HOME/PhotoRAG" \
  "$HOME/Applications/PhotoRAG.AppImage" \
  "$HOME/Applications/.photorag-appimage.json" \
  "$DATA_HOME/applications/com.photorag.app.desktop" \
  "$DATA_HOME/icons/com.photorag.app.png"; do
  if [ -e "$path" ] || [ -L "$path" ]; then printf 'REMAINS: %s\n' "$path"; fi
done
ps -eo pid=,args= | grep -E '[P]hotoRAG|[p]hotorag'
```

Expected result: no `REMAINS` lines and no PhotoRAG processes. Also confirm that you removed the downloaded AppImage from its original location. If a listed path remains, check it and remove only that PhotoRAG item.

## 5. Optional: remove Ollama separately

Ollama is a separate application and may be used by other programs. This procedure leaves Ollama and its models intact. If you want to remove those too, uninstall Ollama using the method you used to install it; deleting its model directory also deletes models used by any other application.

## 6. Optional: reinstall and check first launch

Download the current Linux x86_64 AppImage, make it executable, and launch it. For example, if it is in Downloads:

```bash
chmod +x "$HOME/Downloads/PhotoRAG-<version>-x86_64.AppImage"
"$HOME/Downloads/PhotoRAG-<version>-x86_64.AppImage"
```

The setup wizard should appear again. Once it has started, the log is at:

```bash
tail -n 120 -f "$HOME/.config/PhotoRAG/photorag.log"
```

If you use a custom `XDG_CONFIG_HOME`, look for `PhotoRAG/photorag.log` under that directory instead.
