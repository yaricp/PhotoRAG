(function () {
  var cache = {};
  var currentDocs = null;
  var currentUI = null;
  var requestId = 0;
  var article = document.getElementById('docs-article');
  var topicList = document.getElementById('docs-topics');
  var status = document.getElementById('docs-status');
  var toc = document.querySelector('.docs-toc');

  if (window.matchMedia('(max-width: 720px)').matches) {
    toc.removeAttribute('open');
  }

  function currentTopicId() {
    var hash;
    try {
      hash = decodeURIComponent(window.location.hash.slice(1));
    } catch (_) {
      hash = '';
    }
    return Object.prototype.hasOwnProperty.call(currentDocs.topics, hash) ? hash : currentDocs.topicOrder[0];
  }

  function appendRichText(element, text) {
    var linkRe = /\[([^\]]+)\]\(((?:https?:\/\/|\/)[^)]+)\)/g;
    var last = 0;
    var match;
    while ((match = linkRe.exec(text)) !== null) {
      element.append(document.createTextNode(text.slice(last, match.index)));
      var link = document.createElement('a');
      link.textContent = match[1];
      if (match[2].startsWith('/help/')) {
        link.href = '#' + match[2].slice('/help/'.length);
      } else {
        link.href = match[2];
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
      }
      element.append(link);
      last = linkRe.lastIndex;
    }
    element.append(document.createTextNode(text.slice(last)));
  }

  function addParagraph(text, className) {
    var p = document.createElement('p');
    if (className) p.className = className;
    appendRichText(p, text);
    article.append(p);
  }

  function render() {
    if (!currentDocs) return;
    var id = currentTopicId();
    var topic = currentDocs.topics[id];
    topicList.replaceChildren();
    currentDocs.topicOrder.forEach(function (topicId) {
      var item = document.createElement('li');
      var link = document.createElement('a');
      link.href = '#' + topicId;
      link.textContent = currentDocs.topics[topicId].title;
      if (topicId === id) link.setAttribute('aria-current', 'page');
      item.append(link);
      topicList.append(item);
    });

    article.replaceChildren();
    var heading = document.createElement('h2');
    heading.textContent = topic.title;
    article.append(heading);
    if (topic.intro) addParagraph(topic.intro, 'docs-intro');
    topic.body.split('\n\n').forEach(function (paragraph) {
      addParagraph(paragraph);
    });
    if (topic.examples) {
      var examplesHeading = document.createElement('h3');
      examplesHeading.textContent = currentDocs.examplesHeading;
      article.append(examplesHeading);
      topic.examples.split('\n\n').forEach(function (paragraph) {
        addParagraph(paragraph);
      });
    }
    document.title = topic.title + ' — PhotoRAG';
    status.hidden = true;
    article.hidden = false;
  }

  window.addEventListener('hashchange', function () {
    render();
    if (window.matchMedia('(max-width: 720px)').matches) toc.removeAttribute('open');
    window.scrollTo(0, 0);
  });

  window.addEventListener('photorag:languagechange', function (event) {
    var lang = event.detail.lang;
    currentUI = event.detail.dict;
    var id = ++requestId;
    article.hidden = true;
    status.hidden = false;
    status.textContent = currentUI.docs.loading;
    var pending = cache[lang] || fetch('help-content/' + lang + '.json').then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    });
    cache[lang] = pending;
    Promise.resolve(pending).then(function (docs) {
      if (id !== requestId) return;
      currentDocs = docs;
      render();
    }).catch(function (error) {
      if (id !== requestId) return;
      cache[lang] = null;
      article.hidden = true;
      status.hidden = false;
      status.textContent = currentUI.docs.loadError;
      console.error('[photorag-docs] could not load help:', error);
    });
  });
})();
