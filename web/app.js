(function () {
  var root = document.documentElement;
  var STEP_LABELS = {
    retrieve: ['Quét kho điều luật', 'ChromaDB · HNSW cosine'],
    generate: ['Tổng hợp câu trả lời', 'mô hình ngôn ngữ'],
    cite: ['Gắn trích dẫn về điều gốc', 'đối chiếu số nguồn']
  };

  /* ---------- chế độ màu ---------- */
  function currentMode() {
    return root.getAttribute('data-mode') ||
      (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
  }
  function setMode(m) {
    root.setAttribute('data-mode', m);
    try { localStorage.setItem('ng-mode', m); } catch (e) {}
    document.querySelectorAll('.mode button').forEach(function (b) {
      b.setAttribute('aria-pressed', b.dataset.set === m ? 'true' : 'false');
    });
    window.dispatchEvent(new CustomEvent('luatai:mode', { detail: m }));
  }
  try {
    var saved = localStorage.getItem('ng-mode');
    if (saved === 'light' || saved === 'dark') root.setAttribute('data-mode', saved);
  } catch (e) {}
  document.querySelectorAll('.mode button').forEach(function (b) {
    b.addEventListener('click', function () { setMode(b.dataset.set); });
  });
  setMode(currentMode());

  /* ---------- chuyển trạng thái ---------- */
  var states = {
    rest: document.getElementById('state-rest'),
    think: document.getElementById('state-think'),
    answer: document.getElementById('state-answer')
  };
  function showState(name) {
    Object.keys(states).forEach(function (k) { states[k].hidden = k !== name; });
  }

  /* ---------- tiện ích ---------- */
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmt(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }

  function renderSteps(done, active) {
    var order = ['retrieve', 'generate', 'cite'];
    document.getElementById('steps').innerHTML = order.map(function (key, i) {
      var cls = done[key] !== undefined ? 'done' : (key === active ? 'now' : 'wait');
      var icon = cls === 'done' ? '✓' : String(i + 1);
      var ms = done[key] !== undefined
        ? '<div class="ms">' + (done[key] / 1000).toFixed(2).replace('.', ',') + 's</div>'
        : '';
      return '<div class="step ' + cls + '"><span class="ic">' + icon + '</span>' +
        '<div class="tx"><b>' + STEP_LABELS[key][0] + '</b>' +
        '<span>' + STEP_LABELS[key][1] + '</span>' + ms + '</div></div>';
    }).join('');
  }

  /* Nguyên văn điều luật được trích: serif, khung viền ngọc — tách khỏi lời máy. */
  function renderStatutes(payload) {
    var byN = {};
    payload.chunks.forEach(function (c) { byN[c.n] = c; });
    return payload.citations.map(function (n) {
      var c = byN[n];
      if (!c) return '';
      var src = (c.article != null ? 'Điều ' + esc(c.article) + ' · ' : '') +
        esc(c.title) + ' · nguyên văn';
      return '<div class="statute"><div class="src">' + src + '</div>' +
        '<q>' + esc(c.text) + '</q></div>';
    }).join('');
  }

  /* Chú dẫn [n] trong câu trả lời -> chip bấm được, làm nổi nguồn tương ứng. */
  /* Model trả markdown (**đậm**, danh sách "- ", tiêu đề "##"). Escape TRƯỚC rồi
     mới dựng thẻ, nên chuỗi do model sinh không thể chèn HTML. Chỉ nhận đúng ba
     dạng model thực sự dùng - không phải bộ parse markdown đầy đủ. */
  function mdToHtml(text) {
    var esced = esc(String(text == null ? '' : text));
    function inline(t) {
      return t
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\[(\d+)\]/g, '<span class="ref" data-n="$1">$1</span>');
    }
    var out = [], list = null;
    esced.split('\n').forEach(function (raw) {
      var line = raw.trim();
      if (!line) return;
      var bullet = line.match(/^[-*]\s+(.*)$/);
      if (bullet) {
        list = list || [];
        list.push('<li>' + inline(bullet[1]) + '</li>');
        return;
      }
      if (list) { out.push('<ul>' + list.join('') + '</ul>'); list = null; }
      var head = line.match(/^#{1,6}\s+(.*)$/);
      out.push(head ? '<p class="sub-h">' + inline(head[1]) + '</p>'
                    : '<p>' + inline(line) + '</p>');
    });
    if (list) out.push('<ul>' + list.join('') + '</ul>');
    return out.join('');
  }

  function renderAnswer(payload) {
    var lbl = document.querySelector('#state-answer .lbl b');
    if (lbl && payload.model) lbl.textContent = payload.model;
    var noAnswer = payload.answered === false;
    document.getElementById('answer-body').innerHTML =
      (noAnswer ? '<p class="noans">Không tìm thấy câu trả lời trong kho văn bản</p>' : '') +
      '<div class="synth">' + mdToHtml(payload.answer) + '</div>' +
      (noAnswer ? '' : renderStatutes(payload));

    var top = payload.chunks[0] || {};
    var totalMs = payload.timings.retrieve_ms + payload.timings.generate_ms;
    var metrics = noAnswer ? [
      { b: String(payload.chunks.length), s: 'điều đã xét' },
      { b: (totalMs / 1000).toFixed(1).replace('.', ',') + 's', s: 'phản hồi' }
    ] : [
      { b: String(payload.chunks.length), s: 'điều trích' },
      { b: String(top.score != null ? top.score : 0).replace('.', ','), s: 'khớp nhất' },
      { b: (totalMs / 1000).toFixed(1).replace('.', ',') + 's', s: 'phản hồi' },
      { b: String(payload.citations.length), s: 'trích dẫn' }
    ];
    document.getElementById('metrics').innerHTML = metrics.map(function (m) {
      return '<div class="metric"><b>' + m.b + '</b><span>' + m.s + '</span></div>';
    }).join('');
  }

  function renderSources(chunks) {
    var cnt = document.getElementById('src-count');
    if (cnt) cnt.textContent = 'top ' + chunks.length;
    document.getElementById('src-list').innerHTML = chunks.map(function (c, i) {
      var label = c.article ? 'Điều ' + c.article : c.title;
      var pct = Math.round(c.score * 100);
      return '<div class="srcitem' + (i < 2 ? ' top' : '') + '" data-n="' + c.n + '">' +
        '<div class="h"><span class="id">' + esc(label) + '</span>' +
        '<span class="v">' + String(c.score).replace('.', ',') + '</span></div>' +
        '<div class="t">' + esc(c.title) + '</div>' +
        '<div class="bar"><i style="width:' + pct + '%"></i></div></div>';
    }).join('');
    if (window.gsap) {
      gsap.from('#src-list .srcitem', { opacity: 0, y: 10, duration: .4, stagger: .06 });
      gsap.from('#src-list .bar i', { scaleX: 0, transformOrigin: 'left', duration: .6, stagger: .06 });
    }
  }

  /* ---------- gọi API ---------- */
  var current = null;
  function ask(question) {
    if (current) { current.close(); current = null; }
    var ae = document.getElementById('ask-err');
    if (ae) ae.hidden = true;
    document.getElementById('think-q').textContent = question;
    var done = {};
    renderSteps(done, 'retrieve');
    showState('think');

    var es = new EventSource('/api/ask/stream?q=' + encodeURIComponent(question));
    current = es;
    var next = { retrieve: 'generate', generate: 'cite', cite: null };

    es.addEventListener('step', function (e) {
      var d = JSON.parse(e.data);
      done[d.step] = d.ms;
      renderSteps(done, next[d.step]);
    });
    es.addEventListener('done', function (e) {
      es.close();
      if (current === es) current = null;
      var payload = JSON.parse(e.data);
      renderAnswer(payload);
      renderSources(payload.chunks);
      showState('answer');
      if (window.gsap) {
        gsap.from('#answer-body p', { opacity: 0, y: 8, duration: .45, stagger: .09 });
      }
      window.dispatchEvent(new CustomEvent('luatai:answer', { detail: payload }));
    });
    es.addEventListener('error', function (e) {
      if (current !== es) return;
      es.close();
      current = null;
      var msg = 'Mất kết nối tới máy chủ. Thử lại giúp mình.';
      try { if (e.data) msg = JSON.parse(e.data).error; } catch (_) {}
      var ae = document.getElementById('ask-err');
      if (ae) { ae.textContent = msg + ' — bấm Tra cứu để thử lại.'; ae.hidden = false; }
      showState('rest');
    });
  }

  document.getElementById('ask-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var q = document.getElementById('q-input').value.trim();
    if (q) ask(q);
  });
  document.getElementById('qchips').addEventListener('click', function (e) {
    if (!e.target.classList.contains('qchip')) return;
    document.getElementById('q-input').value = e.target.textContent;
    ask(e.target.textContent);
  });
  document.getElementById('answer-body').addEventListener('mouseover', function (e) {
    if (!e.target.classList.contains('ref')) return;
    var n = e.target.dataset.n;
    document.querySelectorAll('#src-list .srcitem').forEach(function (el) {
      el.style.opacity = el.dataset.n === n ? '1' : '.4';
    });
  });
  document.getElementById('answer-body').addEventListener('mouseout', function () {
    document.querySelectorAll('#src-list .srcitem').forEach(function (el) {
      el.style.opacity = '1';
    });
  });

  window.LuatAI = { setMode: setMode, showState: showState, currentMode: currentMode };
})();
