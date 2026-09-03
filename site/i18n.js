(function () {
  var SUPPORTED = ['en', 'ru', 'es'];
  var DEFAULT_LANG = 'en';
  var STORAGE_KEY = 'photorag-site-lang';
  var cache = {};

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
    var langLabel = resolve(dict, 'meta.langLabel');
    var switcher = document.querySelector('.lang-switch');
    if (switcher && typeof langLabel === 'string') {
      switcher.setAttribute('aria-label', langLabel);
    }
    document.querySelectorAll('.lang-switch button').forEach(function (btn) {
      var isActive = btn.getAttribute('data-lang') === lang;
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-pressed', String(isActive));
    });
  }

  function fetchDict(lang) {
    if (cache[lang]) {
      return Promise.resolve(cache[lang]);
    }
    return fetch('i18n/' + lang + '.json')
      .then(function (res) {
        if (!res.ok) {
          throw new Error('Failed to load ' + lang + '.json: HTTP ' + res.status);
        }
        return res.json();
      })
      .then(function (dict) {
        cache[lang] = dict;
        return dict;
      });
  }

  function loadLang(lang) {
    return fetchDict(lang)
      .then(function (dict) {
        applyTranslations(dict, lang);
        localStorage.setItem(STORAGE_KEY, lang);
      })
      .catch(function (err) {
        console.error('[photorag-site-i18n] could not load language "' + lang + '":', err);
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
