# Чистая переустановка PhotoRAG на macOS

Эта инструкция позволяет проверить первый запуск PhotoRAG так, будто приложение ещё не устанавливали для текущего пользователя macOS. Она удаляет приложение, базу фотографий и очереди задач, настройки, виртуальное окружение Python, загруженные через PhotoRAG встроенные модели, кэш и журналы. **Исходные фотографии в ваших папках не удаляются.** Для проверки установки зависимостей с нуля необходимо удалить именно папку `~/Library/Application Support/PhotoRAG`: простое перемещение `.app` в Корзину сохраняет данные предыдущей установки.

Команды ниже вводятся в **Терминале macOS**. Они рассчитаны на стандартную установку `PhotoRAG.app` в `/Applications` или `~/Applications`. Если приложение находится в другом месте, удалите также ту копию вручную. [Инструкция для Windows](windows_clean_reinstall.md) лежит рядом.

## 1. Закройте приложение

Выберите **PhotoRAG → Завершить PhotoRAG** или нажмите **⌘Q**. Закройте открытые окна установщика и подождите несколько секунд, чтобы завершились процессы Python. Проверьте их:

```bash
pgrep -fl 'PhotoRAG\.app|Application Support/PhotoRAG/(venv|python)' || true
```

Если команда показывает процессы PhotoRAG или его Python-окружения, завершите их по указанным PID через «Мониторинг системы» или командой `kill PID`. Повторите проверку; перед удалением она должна ничего не выводить. Не завершайте все процессы с именем `python`: они могут принадлежать другим программам.

## 2. Удалите PhotoRAG и его данные

Сначала можно посмотреть, какие основные пути существуют:

```bash
ls -ld "/Applications/PhotoRAG.app" "$HOME/Applications/PhotoRAG.app" "$HOME/Library/Application Support/PhotoRAG" 2>/dev/null || true
```

Затем удалите приложение и данные **текущего пользователя**:

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

`sudo` может запросить пароль учётной записи macOS для удаления приложения из общей папки `/Applications`. Команды не удаляют скачанный `.dmg` и ваши фотографии. Папка `Application Support/PhotoRAG` содержит в том числе `venv`, `setup_done`, базы SQLite, очереди и `.hf_cache`; после её удаления мастер первоначальной настройки должен запуститься заново и установить пакеты Python.

## 3. Проверьте очистку

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
  if [ -e "$path" ] || [ -L "$path" ]; then printf 'ОСТАЛОСЬ: %s\n' "$path"; fi
done
pgrep -fl 'PhotoRAG\.app|Application Support/PhotoRAG/(venv|python)' || true
```

Нормальный результат — **нет строк `ОСТАЛОСЬ` и нет процессов PhotoRAG**. Если что-то осталось, проверьте путь и удалите только соответствующий объект после остановки процесса.

## 4. При необходимости сбросьте также Ollama

Для чистой установки **PhotoRAG** этот шаг не нужен: Ollama — отдельная программа, а её модели могут использовать другие приложения. Если вы хотите проверить и установку Ollama с нуля, сначала завершите Ollama через значок в строке меню и убедитесь, что её процессы остановились. Затем следуйте [официальной инструкции Ollama для macOS](https://github.com/ollama/ollama/blob/main/docs/macos.mdx#uninstall). В частности, удаление `~/.ollama` удалит **все** скачанные модели Ollama; при нестандартном `OLLAMA_MODELS` проверьте и его путь отдельно. Если Ollama была установлена через менеджер пакетов или в нестандартное место, удаляйте её тем же способом, которым устанавливали.

## 5. Проверьте установочный файл

Для тестового `0.1.5-pre.5` выполните команду, подставив фактический путь к DMG:

```bash
shasum -a 256 "$HOME/Downloads/PhotoRAG-0.1.5-pre.5-universal.dmg"
```

Ожидаемый SHA-256 для собранного тестового файла: `3cb8017e1ca8d56fa9ad4bee22a658c962c9f19fc89a8f5e527bd030c88e9ebb`. Для другой версии берите сумму из её `SHA256SUMS` или примечаний к сборке.

## 6. Установите и проверьте первый запуск

Откройте DMG, перетащите `PhotoRAG.app` в «Программы», извлеките образ и запустите копию из «Программ». Для неподписанной тестовой сборки macOS может потребовать открыть приложение через контекстное меню **Открыть**. Должен появиться мастер первоначальной настройки с выбором языка и установкой зависимостей.

Пока мастер работает, можно наблюдать журнал в отдельном окне Терминала:

```bash
tail -n 120 -f "$HOME/Library/Application Support/PhotoRAG/photorag.log"
```

Если журнал ещё не создан, дождитесь начала настройки и повторите команду. После завершения мастер создаст новую папку `~/Library/Application Support/PhotoRAG` и маркер `setup_done`; старые фото и незавершённые очереди в неё не вернутся.
