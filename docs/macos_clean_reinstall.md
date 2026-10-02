# PhotoRAG clean reinstall test procedure for macOS

Use this procedure to test PhotoRAG's first launch as if it had never been installed for the current macOS user. It removes the app, photo database and task queues, settings, Python virtual environment, models downloaded by PhotoRAG, caches, and logs. **Your original photo files are not deleted.** To test dependency installation from scratch, remove `~/Library/Application Support/PhotoRAG`; moving only the `.app` to the Trash leaves the previous installation's data in place.

Run the commands below in **macOS Terminal**. They cover a standard `PhotoRAG.app` installation in `/Applications` or `~/Applications`. If you installed the app elsewhere, remove that copy manually as well. The [Windows procedure](windows_clean_reinstall.md) is in the same directory.

## 1. Quit the app

Choose **PhotoRAG → Quit PhotoRAG** or press **⌘Q**. Close any installer windows and wait a few seconds for the Python processes to exit. Check for remaining processes:

```bash
/bin/ps -axo pid=,command= | /usr/bin/awk '$0 ~ /PhotoRAG[.]app|Application Support\/PhotoRAG\/(venv|python)/ { print }'
```

If the command lists PhotoRAG or its Python environment, stop only those listed PIDs in Activity Monitor or with `kill PID`. Repeat the check; it should print nothing before you delete files. Do not stop every process named `python`, since other apps may use Python too.

## 2. Remove PhotoRAG and its data

You can inspect the main paths first:

```bash
ls -ld "/Applications/PhotoRAG.app" "$HOME/Applications/PhotoRAG.app" "$HOME/Library/Application Support/PhotoRAG" 2>/dev/null || true
```

Then remove the app and **the current user's** data:

```bash
sudo rm -rf "/Applications/PhotoRAG.app"
rm -rf "$HOME/Applications/PhotoRAG.app" \
  "$HOME/Library/Application Support/PhotoRAG" \
  "$HOME/Library/Logs/PhotoRAG" \
  "$HOME/Library/Saved Application State/com.photorag.app.savedState" \
  "$HOME/Library/Caches/PhotoRAG" \
  "$HOME/Library/Caches/com.photorag.app" \
  "$HOME/Library/HTTPStorages/com.photorag.app" \
  "$HOME/Library/WebKit/com.photorag.app"
defaults delete com.photorag.app 2>/dev/null || true
rm -f "$HOME/Library/Preferences/com.photorag.app.plist"
```

`sudo` may ask for your macOS account password to remove the app from the shared `/Applications` directory. These commands do not remove the downloaded `.dmg` or your photo files. `Application Support/PhotoRAG` contains `venv`, `setup_done`, SQLite databases, task queues, and `.hf_cache`; removing it makes the first-run wizard start again and reinstall the Python packages.

## 3. Verify cleanup

```bash
for path in "/Applications/PhotoRAG.app" "$HOME/Applications/PhotoRAG.app" \
  "$HOME/Library/Application Support/PhotoRAG" \
  "$HOME/Library/Logs/PhotoRAG" \
  "$HOME/Library/Saved Application State/com.photorag.app.savedState" \
  "$HOME/Library/Caches/PhotoRAG" \
  "$HOME/Library/Caches/com.photorag.app" \
  "$HOME/Library/HTTPStorages/com.photorag.app" \
  "$HOME/Library/WebKit/com.photorag.app" \
  "$HOME/Library/Preferences/com.photorag.app.plist"; do
  if [ -e "$path" ] || [ -L "$path" ]; then printf 'REMAINS: %s\n' "$path"; fi
done
/bin/ps -axo pid=,command= | /usr/bin/awk '$0 ~ /PhotoRAG[.]app|Application Support\/PhotoRAG\/(venv|python)/ { print }'
```

Expected result: **no `REMAINS` lines and no PhotoRAG processes**. If anything remains, check its path and remove only that item after stopping its process.

## 4. Reset Ollama only if needed

This step is not required for a clean **PhotoRAG** installation. Ollama is a separate app, and other apps may use its models. To test Ollama installation from scratch as well, first quit Ollama from its menu bar icon and make sure its processes have stopped. Then follow [Ollama's official macOS uninstall instructions](https://github.com/ollama/ollama/blob/main/docs/macos.mdx#uninstall). Deleting `~/.ollama` removes **all** downloaded Ollama models. If you configured a custom `OLLAMA_MODELS` directory, check that location separately. If you installed Ollama with a package manager or in a custom location, uninstall it using the corresponding method.

## 5. Verify the installer

For the `0.1.5-pre.7` test build, run this command with the actual path to the DMG:

```bash
shasum -a 256 "$HOME/Downloads/PhotoRAG-0.1.5-pre.7-universal.dmg"
# Expected SHA-256: d09b470c1fb23b9dcb60d4e14b308611c0fc4c1ed887f1dc3b11884fb08ae7cc
```

For another version, use its `SHA256SUMS` file or build notes.

## 6. Install and check the first launch

Open the DMG, drag `PhotoRAG.app` into Applications, eject the disk image, and launch the copy in Applications. For an unsigned test build, macOS may require you to right-click the app and choose **Open**. The first-run wizard should appear with language selection and dependency installation.

While the wizard runs, you can watch its log in another Terminal window:

```bash
tail -n 120 -f "$HOME/Library/Application Support/PhotoRAG/photorag.log"
```

If the log does not exist yet, wait for setup to begin and retry the command. When setup finishes, the wizard creates a new `~/Library/Application Support/PhotoRAG` directory and `setup_done` marker; the old photo database and unfinished task queues will not return.
