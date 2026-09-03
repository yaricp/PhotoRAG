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
