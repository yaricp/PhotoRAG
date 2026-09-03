# Expand User Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the GitHub Pages user site into a self-sufficient onboarding path (About → Download & Install → Getting Started → Platform support) in 3 languages, and surface it from the README for non-technical visitors.
**Architecture:** Plain static HTML/CSS/vanilla JS, no build step. A tiny `i18n.js` fetches one of three JSON dictionaries (`site/i18n/{en,ru,es}.json`) and swaps `[data-i18n="dot.path"]` element text client-side; language choice persists in `localStorage`.
**Tech Stack:** HTML, CSS, vanilla JS (ES2017+, no dependencies), Markdown (README).
---

### Task 1: README pointer for non-technical users

**Files:**
- Modify: `README.md:1-7`

- [ ] **Step 1: Insert the block**
      Insert immediately after the title line (`# Photo Describer 2 (PhotoRAG)`) and before the existing description paragraph:
      ```markdown
      ## 📖 Not a developer? Start here

      👉 **[Visit the PhotoRAG website](https://yaricp.github.io/PhotoRAG/)** — download, install, and get started in a few clicks.

      ---
      ```
- [ ] **Step 2: Verify**
      Open `README.md` in a Markdown preview; confirm the block renders above the developer description and the link is correct.
- [ ] **Step 3: Commit**
      `git commit -m "docs(readme): add prominent site link for non-technical users"`

---

### Task 2: i18n dictionaries

**Files:**
- Create: `site/i18n/en.json`
- Create: `site/i18n/ru.json`
- Create: `site/i18n/es.json`

- [ ] **Step 1: Create `site/i18n/en.json`**
      ```json
      {
        "meta": { "langLabel": "Language" },
        "hero": {
          "tagline": "Your photo library, described and searchable by AI — private by default, and fully under your control.",
          "download": "Download latest release",
          "source": "View source on GitHub"
        },
        "about": {
          "title": "About",
          "f1_title": "AI descriptions",
          "f1_desc": "Every photo gets a natural-language description from a vision model.",
          "f2_title": "Text extraction (OCR)",
          "f2_desc": "Finds and indexes text that appears inside your photos.",
          "f3_title": "Semantic search",
          "f3_desc": "Search your library by meaning, not just filenames or tags.",
          "f4_title": "Duplicate detection",
          "f4_desc": "Finds exact and near-duplicate photos automatically.",
          "f5_title": "Private by default",
          "f5_desc": "Descriptions, tags, and search all run on your machine out of the box — your photos never leave your computer unless you explicitly choose otherwise.",
          "f6_title": "Your choice of AI",
          "f6_desc": "Every AI capability (descriptions, tagging, search, translation, chat) can be switched independently between a local model and a remote provider you configure yourself (OpenAI, Anthropic, Ollama, and more) — you decide where your data goes."
        },
        "download": {
          "title": "Download & Install",
          "intro": "Download the installer for your platform from the latest release, then follow the steps below.",
          "colPlatform": "Platform",
          "colFile": "Installer file",
          "mac": "macOS (Intel + Apple Silicon)",
          "winx64": "Windows x64",
          "winarm64": "Windows arm64",
          "linuxx64": "Linux x64",
          "linuxarm64": "Linux arm64",
          "linuxarm64Status": "Not available yet — build currently fails, tracked in",
          "linuxarm64Link": "the tracking issue",
          "releaseLink": "Go to the latest release"
        },
        "gettingStarted": {
          "title": "Getting Started",
          "step1_title": "1. Install",
          "step1_desc": "Download the file for your platform above, then open it. On macOS, if you see a warning that the app is from an unidentified developer, right-click the app and choose Open.",
          "step1_linkText": "Full installation walkthrough",
          "step2_title": "2. First launch — Setup Wizard",
          "step2_desc": "On first launch, the Setup Wizard walks you through choosing which AI models to install. You can skip optional models and download them later from Settings.",
          "step3_title": "3. Configure Settings and Models",
          "step3_desc": "Open Settings to set your language and default photo folder. Open Models to choose which AI capabilities are active — descriptions, tagging, search, translation, and OCR.",
          "step4_title": "4. Add your photos: Watcher or Scan",
          "step4_desc": "On the Folders page, add a Watcher to automatically process new photos as they arrive in a folder (ideal for syncing from your phone), or run a one-time Scan to process an existing folder of photos.",
          "step5_title": "5. See the results",
          "step5_desc": "Track progress on the Processing page, then browse your described, searchable library in the Gallery."
        },
        "platform": {
          "title": "Platform support",
          "colPlatform": "Platform",
          "colStatus": "Status",
          "mac": "macOS (Universal: Intel + Apple Silicon)",
          "macStatus": "✅ Tested and working",
          "win": "Windows x64 / arm64",
          "winStatus": "⚠️ Installer builds; known issues after install",
          "linux": "Linux x64",
          "linuxStatus": "⚠️ Installer builds; known issues after install",
          "linuxarm64": "Linux arm64",
          "linuxarm64Status": "❌ Currently fails to build",
          "notePrefix": "Windows/Linux problems are tracked in",
          "noteLink": "issue #11",
          "noteSuffix": "— help testing and fixing these is welcome."
        },
        "footer": {
          "installGuide": "Detailed installation instructions",
          "license": "MIT License",
          "issues": "Known issues"
        }
      }
      ```
- [ ] **Step 2: Create `site/i18n/ru.json`**
      ```json
      {
        "meta": { "langLabel": "Язык" },
        "hero": {
          "tagline": "Ваша фототека, описанная и доступная для поиска с помощью ИИ — приватная по умолчанию и полностью под вашим контролем.",
          "download": "Скачать последнюю версию",
          "source": "Исходный код на GitHub"
        },
        "about": {
          "title": "О программе",
          "f1_title": "Описания от ИИ",
          "f1_desc": "Каждое фото получает описание на естественном языке от модели компьютерного зрения.",
          "f2_title": "Распознавание текста (OCR)",
          "f2_desc": "Находит и индексирует текст, встречающийся на ваших фотографиях.",
          "f3_title": "Семантический поиск",
          "f3_desc": "Ищите по смыслу, а не только по именам файлов или тегам.",
          "f4_title": "Поиск дубликатов",
          "f4_desc": "Автоматически находит точные и почти одинаковые фотографии.",
          "f5_title": "Приватность по умолчанию",
          "f5_desc": "Описания, теги и поиск по умолчанию работают на вашем компьютере — фотографии не покидают его, если вы сами этого не выберете.",
          "f6_title": "Выбор ИИ — за вами",
          "f6_desc": "Каждую функцию ИИ (описания, теги, поиск, перевод, чат) можно независимо переключать между локальной моделью и удалённым провайдером на ваш выбор (OpenAI, Anthropic, Ollama и другие) — вы решаете, куда уходят ваши данные."
        },
        "download": {
          "title": "Скачивание и установка",
          "intro": "Скачайте установщик для вашей платформы со страницы последнего релиза, затем выполните шаги ниже.",
          "colPlatform": "Платформа",
          "colFile": "Файл установщика",
          "mac": "macOS (Intel + Apple Silicon)",
          "winx64": "Windows x64",
          "winarm64": "Windows arm64",
          "linuxx64": "Linux x64",
          "linuxarm64": "Linux arm64",
          "linuxarm64Status": "Пока недоступно — сборка не проходит, отслеживается в",
          "linuxarm64Link": "отслеживающем issue",
          "releaseLink": "Перейти к последнему релизу"
        },
        "gettingStarted": {
          "title": "Первые шаги",
          "step1_title": "1. Установка",
          "step1_desc": "Скачайте файл для вашей платформы выше и откройте его. На macOS, если появится предупреждение о неизвестном разработчике, нажмите правой кнопкой по приложению и выберите «Открыть».",
          "step1_linkText": "Подробная инструкция по установке",
          "step2_title": "2. Первый запуск — мастер настройки",
          "step2_desc": "При первом запуске мастер настройки поможет выбрать, какие модели ИИ установить. Необязательные модели можно пропустить и скачать позже в Настройках.",
          "step3_title": "3. Настройка Settings и Models",
          "step3_desc": "В разделе Settings задайте язык и папку по умолчанию. В разделе Models выберите, какие функции ИИ активны — описания, теги, поиск, перевод и OCR.",
          "step4_title": "4. Добавление фото: Watcher или Scan",
          "step4_desc": "На странице Folders добавьте Watcher для автоматической обработки новых фото по мере их появления в папке (удобно для синхронизации с телефона), либо запустите разовый Scan для обработки уже существующей папки с фото.",
          "step5_title": "5. Результаты",
          "step5_desc": "Следите за прогрессом на странице Processing, затем просматривайте описанную и доступную для поиска библиотеку в Gallery."
        },
        "platform": {
          "title": "Поддержка платформ",
          "colPlatform": "Платформа",
          "colStatus": "Статус",
          "mac": "macOS (Universal: Intel + Apple Silicon)",
          "macStatus": "✅ Протестировано и работает",
          "win": "Windows x64 / arm64",
          "winStatus": "⚠️ Установщик собирается; известны проблемы после установки",
          "linux": "Linux x64",
          "linuxStatus": "⚠️ Установщик собирается; известны проблемы после установки",
          "linuxarm64": "Linux arm64",
          "linuxarm64Status": "❌ Сборка не проходит",
          "notePrefix": "Проблемы Windows/Linux отслеживаются в",
          "noteLink": "issue #11",
          "noteSuffix": "— будем рады помощи с тестированием и исправлением."
        },
        "footer": {
          "installGuide": "Подробная инструкция по установке",
          "license": "Лицензия MIT",
          "issues": "Известные проблемы"
        }
      }
      ```
- [ ] **Step 3: Create `site/i18n/es.json`**
      ```json
      {
        "meta": { "langLabel": "Idioma" },
        "hero": {
          "tagline": "Tu biblioteca de fotos, descrita y buscable con IA — privada por defecto y totalmente bajo tu control.",
          "download": "Descargar última versión",
          "source": "Ver código fuente en GitHub"
        },
        "about": {
          "title": "Acerca de",
          "f1_title": "Descripciones con IA",
          "f1_desc": "Cada foto recibe una descripción en lenguaje natural generada por un modelo de visión.",
          "f2_title": "Extracción de texto (OCR)",
          "f2_desc": "Encuentra e indexa el texto que aparece dentro de tus fotos.",
          "f3_title": "Búsqueda semántica",
          "f3_desc": "Busca en tu biblioteca por significado, no solo por nombres de archivo o etiquetas.",
          "f4_title": "Detección de duplicados",
          "f4_desc": "Encuentra automáticamente fotos duplicadas o casi idénticas.",
          "f5_title": "Privacidad por defecto",
          "f5_desc": "Las descripciones, etiquetas y búsquedas se ejecutan en tu equipo de forma predeterminada — tus fotos nunca salen de tu ordenador a menos que tú lo decidas.",
          "f6_title": "Tú eliges la IA",
          "f6_desc": "Cada función de IA (descripciones, etiquetado, búsqueda, traducción, chat) puede alternarse de forma independiente entre un modelo local y un proveedor remoto que configures tú mismo (OpenAI, Anthropic, Ollama y otros) — tú decides adónde van tus datos."
        },
        "download": {
          "title": "Descarga e instalación",
          "intro": "Descarga el instalador para tu plataforma desde la última versión y sigue los pasos a continuación.",
          "colPlatform": "Plataforma",
          "colFile": "Archivo del instalador",
          "mac": "macOS (Intel + Apple Silicon)",
          "winx64": "Windows x64",
          "winarm64": "Windows arm64",
          "linuxx64": "Linux x64",
          "linuxarm64": "Linux arm64",
          "linuxarm64Status": "Aún no disponible — la compilación falla actualmente, seguimiento en",
          "linuxarm64Link": "el issue de seguimiento",
          "releaseLink": "Ir a la última versión"
        },
        "gettingStarted": {
          "title": "Primeros pasos",
          "step1_title": "1. Instalar",
          "step1_desc": "Descarga el archivo para tu plataforma y ábrelo. En macOS, si aparece un aviso de desarrollador no identificado, haz clic derecho en la app y elige Abrir.",
          "step1_linkText": "Guía de instalación completa",
          "step2_title": "2. Primer inicio — Asistente de configuración",
          "step2_desc": "En el primer inicio, el Asistente de configuración te guía para elegir qué modelos de IA instalar. Puedes omitir los modelos opcionales y descargarlos más tarde desde Ajustes.",
          "step3_title": "3. Configura Ajustes y Modelos",
          "step3_desc": "Abre Ajustes para establecer tu idioma y la carpeta de fotos predeterminada. Abre Modelos para elegir qué funciones de IA están activas — descripciones, etiquetado, búsqueda, traducción y OCR.",
          "step4_title": "4. Añade tus fotos: Watcher o Scan",
          "step4_desc": "En la página Carpetas, añade un Watcher para procesar automáticamente las fotos nuevas que lleguen a una carpeta (ideal para sincronizar desde tu teléfono), o ejecuta un Scan puntual para procesar una carpeta ya existente.",
          "step5_title": "5. Ver los resultados",
          "step5_desc": "Sigue el progreso en la página Procesamiento y luego explora tu biblioteca descrita y buscable en la Galería."
        },
        "platform": {
          "title": "Compatibilidad de plataformas",
          "colPlatform": "Plataforma",
          "colStatus": "Estado",
          "mac": "macOS (Universal: Intel + Apple Silicon)",
          "macStatus": "✅ Probado y funcionando",
          "win": "Windows x64 / arm64",
          "winStatus": "⚠️ El instalador se genera; hay problemas conocidos tras la instalación",
          "linux": "Linux x64",
          "linuxStatus": "⚠️ El instalador se genera; hay problemas conocidos tras la instalación",
          "linuxarm64": "Linux arm64",
          "linuxarm64Status": "❌ La compilación falla actualmente",
          "notePrefix": "Los problemas de Windows/Linux se siguen en",
          "noteLink": "el issue #11",
          "noteSuffix": "— la ayuda para probar y corregirlos es bienvenida."
        },
        "footer": {
          "installGuide": "Instrucciones de instalación detalladas",
          "license": "Licencia MIT",
          "issues": "Problemas conocidos"
        }
      }
      ```
- [ ] **Step 4: Verify JSON validity**
      Run: `node -e "['en','ru','es'].forEach(l => JSON.parse(require('fs').readFileSync('site/i18n/'+l+'.json')))"`
      Expected: no output, exit code 0 (all three parse cleanly)
- [ ] **Step 5: Commit**
      `git commit -m "feat(site): add i18n dictionaries for en/ru/es"`

---

### Task 3: i18n engine + language switcher markup

**Files:**
- Create: `site/i18n.js`
- Modify: `site/index.html` (header)

- [ ] **Step 1: Create `site/i18n.js`**
      ```js
      (function () {
        var SUPPORTED = ['en', 'ru', 'es'];
        var DEFAULT_LANG = 'en';
        var STORAGE_KEY = 'photorag-site-lang';

        function resolve(dict, path) {
          return path.split('.').reduce(function (obj, key) {
            return (obj && Object.prototype.hasOwnProperty.call(obj, key)) ? obj[key] : undefined;
          }, dict);
        }

        function applyTranslations(dict, lang) {
          document.querySelectorAll('[data-i18n]').forEach(function (el) {
            var value = resolve(dict, el.getAttribute('data-i18n'));
            if (typeof value === 'string') {
              el.textContent = value;
            }
          });
          document.documentElement.lang = lang;
          document.querySelectorAll('.lang-switch button').forEach(function (btn) {
            var isActive = btn.getAttribute('data-lang') === lang;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', String(isActive));
          });
        }

        function loadLang(lang) {
          return fetch('i18n/' + lang + '.json')
            .then(function (res) { return res.json(); })
            .then(function (dict) {
              applyTranslations(dict, lang);
              localStorage.setItem(STORAGE_KEY, lang);
            });
        }

        document.querySelectorAll('.lang-switch button').forEach(function (btn) {
          btn.addEventListener('click', function () {
            loadLang(btn.getAttribute('data-lang'));
          });
        });

        var saved = localStorage.getItem(STORAGE_KEY);
        var initial = SUPPORTED.indexOf(saved) !== -1 ? saved : DEFAULT_LANG;
        loadLang(initial);
      })();
      ```
- [ ] **Step 2: Add the switcher markup to `site/index.html`**
      Insert as the first child of `<header class="hero">`, before the `<img class="hero-icon" ...>` line:
      ```html
      <nav class="lang-switch" aria-label="Language">
        <button type="button" data-lang="en" aria-pressed="true">EN</button>
        <button type="button" data-lang="ru" aria-pressed="false">RU</button>
        <button type="button" data-lang="es" aria-pressed="false">ES</button>
      </nav>
      ```
      Add before the closing `</body>` tag:
      ```html
      <script src="i18n.js" defer></script>
      ```
- [ ] **Step 3: Commit**
      `git commit -m "feat(site): add vanilla-JS language switcher engine"`

---

### Task 4: Wire `data-i18n` attributes into existing sections + restructure

**Files:**
- Modify: `site/index.html` (hero, About/features, Platform support, footer)

- [ ] **Step 1: Update the hero block**
      ```html
      <p class="tagline" data-i18n="hero.tagline">Your photo library, described and searchable by AI — private by default, and fully under your control.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="https://github.com/yaricp/PhotoRAG/releases/latest" data-i18n="hero.download">Download latest release</a>
        <a class="btn btn-secondary" href="https://github.com/yaricp/PhotoRAG" data-i18n="hero.source">View source on GitHub</a>
      </div>
      ```
- [ ] **Step 2: Rename "What it does" to "About" with `data-i18n`**
      ```html
      <section class="features">
        <h2 data-i18n="about.title">About</h2>
        <ul class="feature-grid">
          <li><strong data-i18n="about.f1_title">AI descriptions</strong><br><span data-i18n="about.f1_desc">Every photo gets a natural-language description from a vision model.</span></li>
          <li><strong data-i18n="about.f2_title">Text extraction (OCR)</strong><br><span data-i18n="about.f2_desc">Finds and indexes text that appears inside your photos.</span></li>
          <li><strong data-i18n="about.f3_title">Semantic search</strong><br><span data-i18n="about.f3_desc">Search your library by meaning, not just filenames or tags.</span></li>
          <li><strong data-i18n="about.f4_title">Duplicate detection</strong><br><span data-i18n="about.f4_desc">Finds exact and near-duplicate photos automatically.</span></li>
          <li><strong data-i18n="about.f5_title">Private by default</strong><br><span data-i18n="about.f5_desc">Descriptions, tags, and search all run on your machine out of the box — your photos never leave your computer unless you explicitly choose otherwise.</span></li>
          <li><strong data-i18n="about.f6_title">Your choice of AI</strong><br><span data-i18n="about.f6_desc">Every AI capability (descriptions, tagging, search, translation, chat) can be switched independently between a local model and a remote provider you configure yourself (OpenAI, Anthropic, Ollama, and more) — you decide where your data goes.</span></li>
        </ul>
      </section>
      ```
- [ ] **Step 3: Add `data-i18n` to the Platform support section**
      ```html
      <section class="platform-matrix">
        <h2 data-i18n="platform.title">Platform support</h2>
        <table>
          <thead>
            <tr><th data-i18n="platform.colPlatform">Platform</th><th data-i18n="platform.colStatus">Status</th></tr>
          </thead>
          <tbody>
            <tr><td data-i18n="platform.mac">macOS (Universal: Intel + Apple Silicon)</td><td class="status-ok" data-i18n="platform.macStatus">✅ Tested and working</td></tr>
            <tr><td data-i18n="platform.win">Windows x64 / arm64</td><td class="status-warn" data-i18n="platform.winStatus">⚠️ Installer builds; known issues after install</td></tr>
            <tr><td data-i18n="platform.linux">Linux x64</td><td class="status-warn" data-i18n="platform.linuxStatus">⚠️ Installer builds; known issues after install</td></tr>
            <tr><td data-i18n="platform.linuxarm64">Linux arm64</td><td class="status-fail" data-i18n="platform.linuxarm64Status">❌ Currently fails to build</td></tr>
          </tbody>
        </table>
        <p class="matrix-note">
          <span data-i18n="platform.notePrefix">Windows/Linux problems are tracked in</span>
          <a href="https://github.com/yaricp/PhotoRAG/issues/11" data-i18n="platform.noteLink">issue #11</a>
          <span data-i18n="platform.noteSuffix">— help testing and fixing these is welcome.</span>
        </p>
      </section>
      ```
- [ ] **Step 4: Add `data-i18n` to the footer**
      ```html
      <footer>
        <p>
          <a href="https://github.com/yaricp/PhotoRAG/blob/main/README-installer.md" data-i18n="footer.installGuide">Detailed installation instructions</a>
          · <a href="https://github.com/yaricp/PhotoRAG/blob/main/LICENSE" data-i18n="footer.license">MIT License</a>
          · <a href="https://github.com/yaricp/PhotoRAG/issues/11" data-i18n="footer.issues">Known issues</a>
        </p>
      </footer>
      ```
- [ ] **Step 5: Commit**
      `git commit -m "feat(site): wire i18n attributes into hero, about, platform, footer"`

---

### Task 5: Download & Install section

**Files:**
- Modify: `site/index.html` (new section, inserted between About and Getting Started)

- [ ] **Step 1: Insert the section** (immediately after the `</section>` closing the About/features block, before the screenshots comment)
      ```html
      <section class="downloads">
        <h2 data-i18n="download.title">Download & Install</h2>
        <p data-i18n="download.intro">Download the installer for your platform from the latest release, then follow the steps below.</p>
        <table>
          <thead>
            <tr><th data-i18n="download.colPlatform">Platform</th><th data-i18n="download.colFile">Installer file</th></tr>
          </thead>
          <tbody>
            <tr><td data-i18n="download.mac">macOS (Intel + Apple Silicon)</td><td><code>PhotoRAG-&lt;version&gt;-universal.dmg</code></td></tr>
            <tr><td data-i18n="download.winx64">Windows x64</td><td><code>PhotoRAG-Setup-&lt;version&gt;-x64.exe</code></td></tr>
            <tr><td data-i18n="download.winarm64">Windows arm64</td><td><code>PhotoRAG-Setup-&lt;version&gt;-arm64.exe</code></td></tr>
            <tr><td data-i18n="download.linuxx64">Linux x64</td><td><code>PhotoRAG-&lt;version&gt;-x86_64.AppImage</code></td></tr>
            <tr>
              <td data-i18n="download.linuxarm64">Linux arm64</td>
              <td class="status-fail">
                <span data-i18n="download.linuxarm64Status">Not available yet — build currently fails, tracked in</span>
                <a href="https://github.com/yaricp/PhotoRAG/issues/11" data-i18n="download.linuxarm64Link">the tracking issue</a>
              </td>
            </tr>
          </tbody>
        </table>
        <p><a class="btn btn-primary" href="https://github.com/yaricp/PhotoRAG/releases/latest" data-i18n="download.releaseLink">Go to the latest release</a></p>
      </section>
      ```
- [ ] **Step 2: Commit**
      `git commit -m "feat(site): add Download & Install section"`

---

### Task 6: Getting Started section

**Files:**
- Modify: `site/index.html` (new section, inserted after Download & Install, before the screenshots comment / Platform support)

- [ ] **Step 1: Insert the section**
      ```html
      <section class="getting-started">
        <h2 data-i18n="gettingStarted.title">Getting Started</h2>
        <ol class="steps">
          <li>
            <strong data-i18n="gettingStarted.step1_title">1. Install</strong>
            <p data-i18n="gettingStarted.step1_desc">Download the file for your platform above, then open it. On macOS, if you see a warning that the app is from an unidentified developer, right-click the app and choose Open.</p>
            <a href="https://github.com/yaricp/PhotoRAG/blob/main/README-installer.md" data-i18n="gettingStarted.step1_linkText">Full installation walkthrough</a>
          </li>
          <li>
            <strong data-i18n="gettingStarted.step2_title">2. First launch — Setup Wizard</strong>
            <p data-i18n="gettingStarted.step2_desc">On first launch, the Setup Wizard walks you through choosing which AI models to install. You can skip optional models and download them later from Settings.</p>
          </li>
          <li>
            <strong data-i18n="gettingStarted.step3_title">3. Configure Settings and Models</strong>
            <p data-i18n="gettingStarted.step3_desc">Open Settings to set your language and default photo folder. Open Models to choose which AI capabilities are active — descriptions, tagging, search, translation, and OCR.</p>
          </li>
          <li>
            <strong data-i18n="gettingStarted.step4_title">4. Add your photos: Watcher or Scan</strong>
            <p data-i18n="gettingStarted.step4_desc">On the Folders page, add a Watcher to automatically process new photos as they arrive in a folder (ideal for syncing from your phone), or run a one-time Scan to process an existing folder of photos.</p>
          </li>
          <li>
            <strong data-i18n="gettingStarted.step5_title">5. See the results</strong>
            <p data-i18n="gettingStarted.step5_desc">Track progress on the Processing page, then browse your described, searchable library in the Gallery.</p>
          </li>
        </ol>
      </section>
      ```
- [ ] **Step 2: Commit**
      `git commit -m "feat(site): add Getting Started section"`

---

### Task 7: Styling

**Files:**
- Modify: `site/styles.css`

- [ ] **Step 1: Add language switcher styles**
      ```css
      .lang-switch {
        display: flex;
        justify-content: center;
        gap: 0.4rem;
        margin-bottom: 1.5rem;
      }

      .lang-switch button {
        background: transparent;
        border: 1px solid var(--border);
        color: var(--text-muted);
        border-radius: var(--radius);
        padding: 0.3rem 0.7rem;
        font-size: 0.85rem;
        cursor: pointer;
      }

      .lang-switch button.active {
        background: var(--accent);
        color: var(--accent-text);
        border-color: var(--accent);
      }
      ```
- [ ] **Step 2: Add Getting Started steps styles**
      ```css
      .steps {
        list-style: none;
        margin: 1.5rem 0 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 1.25rem;
      }

      .steps li {
        background: var(--bg-elevated);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1rem 1.15rem;
      }

      .steps strong {
        display: block;
        margin-bottom: 0.3rem;
      }

      .steps p {
        margin: 0 0 0.5rem;
        color: var(--text-muted);
      }
      ```
- [ ] **Step 3: Add download table code styling**
      ```css
      .downloads code {
        font-size: 0.85rem;
        background: var(--bg);
        padding: 0.15rem 0.4rem;
        border-radius: 4px;
      }
      ```
- [ ] **Step 4: Commit**
      `git commit -m "style(site): style language switcher, steps, and download table"`

---

### Task 8: Manual verification

**Files:** none (verification only)

- [ ] **Step 1: Serve the site locally**
      Run: `cd site && python3 -m http.server 8080`
      (plain `file://` won't work — `fetch()` of local JSON is blocked by CORS in Chrome/Edge)
- [ ] **Step 2: Check all three languages**
      Open `http://localhost:8080/` in a browser. Click EN/RU/ES in the header. Confirm every heading and paragraph on the page changes language, no raw `data-i18n` dot-paths are visible as text, and there are no console errors (DevTools Console tab).
- [ ] **Step 3: Check links**
      Confirm the Download & Install release link, Getting Started walkthrough link, Platform support issue link, and footer links all resolve to the correct GitHub URLs.
- [ ] **Step 4: Stop the server**
      `Ctrl+C` in the terminal running the Python server.

---

### Task 9: Review & completion

- [ ] **Step 1: Request code review** (superpowers:requesting-code-review) comparing `BASE_SHA` (branch point from `main`) to `HEAD_SHA`
- [ ] **Step 2: Run `openspec validate 2026-09-04-expand-user-site --strict`** — must pass
- [ ] **Step 3: Update `openspec/changes/2026-09-04-expand-user-site/tasks.md`** — check off all completed tasks
- [ ] **Step 4: Invoke finishing-a-development-branch** to merge/PR per user choice
