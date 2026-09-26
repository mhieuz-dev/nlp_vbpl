(function () {
  var root = document.documentElement;
  var reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
  var warmTimer = null;
  var STEP_LABELS = {
    retrieve: ["Quét kho điều luật", "ChromaDB · HNSW cosine"],
    generate: ["Tổng hợp câu trả lời", "mô hình ngôn ngữ"],
    cite: ["Gắn trích dẫn về điều gốc", "đối chiếu số nguồn"],
  };

  /* ---------- chế độ màu ---------- */
  function currentMode() {
    return (
      root.getAttribute("data-mode") ||
      (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark")
    );
  }
  function setMode(m) {
    root.setAttribute("data-mode", m);
    try {
      localStorage.setItem("ng-mode", m);
    } catch (e) {}
    document.querySelectorAll(".mode button").forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.set === m ? "true" : "false");
    });
    window.dispatchEvent(new CustomEvent("luatai:mode", { detail: m }));
  }
  try {
    var saved = localStorage.getItem("ng-mode");
    if (saved === "light" || saved === "dark")
      root.setAttribute("data-mode", saved);
  } catch (e) {}
  document.querySelectorAll(".mode button").forEach(function (b) {
    b.addEventListener("click", function () {
      setMode(b.dataset.set);
    });
  });
  setMode(currentMode());

  /* ---------- chuyển trạng thái ---------- */
  var states = {
    rest: document.getElementById("state-rest"),
    thread: document.getElementById("state-thread"),
  };
  function showState(name) {
    root.dataset.state = name;
    Object.keys(states).forEach(function (k) {
      states[k].hidden = k !== name;
    });
  }

  /* ---------- tiện ích ---------- */
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[c];
    });
  }
  function fmt(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function stepsHtml(done, active) {
    var order = ["retrieve", "generate", "cite"];
    return order
      .map(function (key, i) {
        var cls =
          done[key] !== undefined ? "done" : key === active ? "now" : "wait";
        var icon = cls === "done" ? "✓" : String(i + 1);
        var ms =
          done[key] !== undefined
            ? '<div class="ms">' +
              (done[key] / 1000).toFixed(2).replace(".", ",") +
              "s</div>"
            : "";
        return (
          '<div class="step ' +
          cls +
          '"><span class="ic">' +
          icon +
          "</span>" +
          '<div class="tx"><b>' +
          STEP_LABELS[key][0] +
          "</b>" +
          "<span>" +
          STEP_LABELS[key][1] +
          "</span>" +
          ms +
          "</div></div>"
        );
      })
      .join("");
  }

  /* Vẽ lại các bước bên trong ĐÚNG lượt đang chờ. Bản trước ghi vào một ô
     #steps duy nhất; giờ mỗi lượt có ô của riêng nó nên phải trỏ đúng chỗ. */
  function paintSteps(turnEl, done, active) {
    var box = turnEl && turnEl.querySelector(".steps");
    if (box) box.innerHTML = stepsHtml(done, active);
  }

  /* Số hiệu, ngày ban hành, link bản gốc. Chỉ văn bản crawl từ Công báo có ba
     trường này (~4,5 nghìn / 53 nghìn đoạn); đoạn từ bộ dữ liệu UTS_VLC không
     có link tới văn bản gốc thì nói thẳng nguồn, không tự dựng link. */
  function sourceMetaHtml(c) {
    var parts = [];
    if (c.doc_number) parts.push(esc(c.doc_number));
    if (viDate(c.issue_date)) parts.push("ban hành " + viDate(c.issue_date));
    parts.push(
      /^https:\/\//.test(c.source_url || "")
        ? '<a href="' +
            esc(c.source_url) +
            '" target="_blank" rel="noopener noreferrer">Bản gốc trên Công báo ↗</a>'
        : "Nguồn: bộ dữ liệu UTS_VLC",
    );
    return '<p class="srcmeta">' + parts.join(" · ") + "</p>";
  }

  /* Nguyên văn điều luật được trích: serif, khung viền ngọc — tách khỏi lời máy. */
  function renderStatutes(payload) {
    var byN = {};
    payload.chunks.forEach(function (c) {
      byN[c.n] = c;
    });
    return payload.citations
      .map(function (n) {
        var c = byN[n];
        if (!c) return "";
        var src =
          (c.article != null ? "Điều " + esc(c.article) + " · " : "") +
          esc(c.title) +
          " · nguyên văn";
        return (
          '<div class="statute" data-n="' +
          n +
          '"><div class="src">' +
          src +
          "</div>" +
          "<q>" +
          esc(c.text) +
          "</q>" +
          sourceMetaHtml(c) +
          "</div>"
        );
      })
      .join("");
  }

  /* Chú dẫn [n] trong câu trả lời -> chip bấm được, làm nổi nguồn tương ứng. */
  /* Model trả markdown (**đậm**, danh sách "- ", tiêu đề "##"). Escape TRƯỚC rồi
     mới dựng thẻ, nên chuỗi do model sinh không thể chèn HTML. Chỉ nhận đúng ba
     dạng model thực sự dùng - không phải bộ parse markdown đầy đủ. */
  function mdToHtml(text) {
    var esced = esc(String(text == null ? "" : text));
    function inline(t) {
      return t
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(
          /\[(\d+)\]/g,
          '<button type="button" class="ref" aria-label="Xem nguồn $1" data-n="$1">$1</button>',
        );
    }
    var out = [],
      list = null;
    esced.split("\n").forEach(function (raw) {
      var line = raw.trim();
      if (!line) return;
      var bullet = line.match(/^[-*]\s+(.*)$/);
      if (bullet) {
        list = list || [];
        list.push("<li>" + inline(bullet[1]) + "</li>");
        return;
      }
      if (list) {
        out.push("<ul>" + list.join("") + "</ul>");
        list = null;
      }
      var head = line.match(/^#{1,6}\s+(.*)$/);
      out.push(
        head
          ? '<p class="sub-h">' + inline(head[1]) + "</p>"
          : "<p>" + inline(line) + "</p>",
      );
    });
    if (list) out.push("<ul>" + list.join("") + "</ul>");
    return out.join("");
  }

  function answerCardHtml(payload) {
    var noAnswer = payload.answered === false;
    var body =
      (noAnswer
        ? '<p class="noans">Không tìm thấy câu trả lời trong kho văn bản</p>'
        : "") +
      '<div class="synth">' +
      mdToHtml(payload.answer) +
      "</div>" +
      (noAnswer ? "" : renderStatutes(payload));

    var totalMs = payload.timings.retrieve_ms + payload.timings.generate_ms;
    var metrics = [
      { b: String(payload.chunks.length), s: "điều đã đối chiếu" },
      { b: String(payload.citations.length), s: "trích dẫn" },
      { b: (totalMs / 1000).toFixed(1).replace(".", ",") + "s", s: "phản hồi" },
    ];

    return (
      '<article class="card card-answer">' +
      '<p class="lbl"><b>H2N LAW</b> · Cùng bạn tìm hiểu pháp luật</p>' +
      '<div class="ansbody">' +
      body +
      "</div>" +
      '<div class="metrics">' +
      metrics
        .map(function (m) {
          return (
            '<div class="metric"><b>' +
            m.b +
            "</b><span>" +
            m.s +
            "</span></div>"
          );
        })
        .join("") +
      '</div><div class="answer-tools"><button type="button" class="copy-answer">Sao chép câu trả lời</button></div></article>'
    );
  }

  function sourcesCardHtml(chunks) {
    var items = chunks
      .map(function (c, i) {
        var label = c.article ? "Điều " + c.article : c.title;
        return (
          '<details class="srcitem' +
          (i < 2 ? " top" : "") +
          '" data-n="' +
          c.n +
          '"><summary>' +
          '<div class="h"><span class="id">' +
          esc(label) +
          "</span>" +
          '<span class="v">' +
          String(c.score).replace(".", ",") +
          "</span></div>" +
          '<div class="t">' +
          esc(c.title) +
          "</div></summary>" +
          "<q>" +
          esc(c.text) +
          "</q>" +
          sourceMetaHtml(c) +
          "</details>"
        );
      })
      .join("");
    return (
      '<details class="card card-src"><summary>Đối chiếu nguồn · ' +
      chunks.length +
      " điều luật đã truy xuất</summary>" +
      '<div class="srclist">' +
      items +
      "</div></details>"
    );
  }

  function askedHtml(question) {
    return '<div class="ask"><span>' + esc(question) + "</span></div>";
  }

  /* Một lượt đã có câu trả lời. */
  function turnHtml(question, payload) {
    return (
      askedHtml(question) +
      '<div class="ansgrid">' +
      answerCardHtml(payload) +
      sourcesCardHtml(payload.chunks) +
      "</div>"
    );
  }

  /* Lượt đang chờ: câu hỏi hiện ngay, bên dưới là các bước đang chạy. */
  function pendingHtml(question) {
    return (
      askedHtml(question) +
      '<div class="pending"><div class="steps"></div>' +
      '<div class="skel" aria-hidden="true">' +
      '<div class="ln" style="width:96%"></div><div class="ln" style="width:88%"></div>' +
      '<div class="ln" style="width:71%"></div><div class="ln" style="width:46%"></div>' +
      "</div></div>"
    );
  }

  function appendTurn(html) {
    var el = document.createElement("article");
    el.className = "turn";
    el.innerHTML = html;
    document.getElementById("thread").appendChild(el);
    return el;
  }

  function scrollToTurn(el) {
    if (!el) return;
    try {
      el.scrollIntoView({
        behavior: reducedMotion.matches ? "auto" : "smooth",
        block: "start",
      });
    } catch (e) {
      el.scrollIntoView();
    }
  }

  /* ---------- lịch sử tra cứu ---------- */
  var History = window.LuatAIHistory;
  var openId = null; /* cuộc đang mở, để tô sáng trong danh sách */

  function setSidebar(open) {
    root.setAttribute("data-sidebar", open ? "open" : "closed");
    document.getElementById("sidebar").inert = !open;
    if (
      !open &&
      document.getElementById("sidebar").contains(document.activeElement)
    )
      document.getElementById("side-toggle").focus();
    document
      .getElementById("side-toggle")
      .setAttribute("aria-expanded", open ? "true" : "false");
    document.getElementById("scrim").hidden = !open;
    try {
      localStorage.setItem("ng-sidebar", open ? "open" : "closed");
    } catch (e) {}
  }

  function renderChatList() {
    var filter = document
      .getElementById("history-filter")
      .value.trim()
      .toLocaleLowerCase("vi");
    var items = History.list().filter(function (c) {
      return !filter || c.title.toLocaleLowerCase("vi").includes(filter);
    });
    var box = document.getElementById("chat-list");
    if (!items.length) {
      box.innerHTML =
        '<p class="chatempty">' +
        (filter
          ? "Không tìm thấy cuộc trò chuyện."
          : "Câu chuyện của bạn bắt đầu ở đây. Đặt câu hỏi đầu tiên để lưu lại cuộc trò chuyện.") +
        "</p>";
      return;
    }
    box.innerHTML = items
      .map(function (c) {
        return (
          '<div class="chatitem' +
          (c.id === openId ? " on" : "") +
          '" data-id="' +
          esc(c.id) +
          '" role="button" tabindex="0" title="' +
          esc(c.title) +
          '">' +
          '<span class="q">' +
          esc(c.title) +
          "</span>" +
          '<button class="del" type="button" data-del="' +
          esc(c.id) +
          '" aria-label="Xoá cuộc này">×</button></div>'
        );
      })
      .join("");
  }

  /* Mở lại từ payload đã lưu: KHÔNG gọi lại API. Câu trả lời cũ dựng lại được
   * trọn vẹn vì renderAnswer/renderSources chỉ phụ thuộc payload. */
  function openChat(id) {
    clearTimeout(warmTimer);
    document.getElementById("ask-err").hidden = true;
    var c = History.get(id);
    if (!c) return;
    if (current) {
      current.abort();
      current = null;
    }
    conv = c;
    openId = id;
    // Dựng lại từ payload đã lưu: KHÔNG gọi lại API lần nào.
    document.getElementById("thread").innerHTML = "";
    c.turns.forEach(function (tn) {
      appendTurn(turnHtml(tn.q, tn.payload));
    });
    document.getElementById("q-input").value = "";
    showState("thread");
    renderChatList();
    if (innerWidth < 1080) setSidebar(false);
    var last = document.querySelector("#thread .turn:last-child");
    if (last) scrollToTurn(last);
  }

  document.getElementById("chat-list").addEventListener("click", function (e) {
    var del = e.target.closest("[data-del]");
    if (del) {
      History.remove(del.dataset.del);
      if (openId === del.dataset.del) {
        newConv();
        showState("rest");
      }
      renderChatList();
      return;
    }
    var item = e.target.closest(".chatitem");
    if (item) openChat(item.dataset.id);
  });
  document
    .getElementById("chat-list")
    .addEventListener("keydown", function (e) {
      var item = e.target.closest(".chatitem");
      if (e.target.closest("[data-del]")) return;
      if (item && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        openChat(item.dataset.id);
      }
    });

  document.getElementById("new-chat").addEventListener("click", function () {
    if (current) {
      current.abort();
      current = null;
    }
    newConv();
    document.getElementById("q-input").value = "";
    showState("rest");
    renderChatList();
    document.getElementById("q-input").focus();
    if (innerWidth < 1080) setSidebar(false);
  });

  document.getElementById("clear-chats").addEventListener("click", function () {
    if (!History.list().length) return;
    if (!confirm("Xoá toàn bộ lịch sử tra cứu trên máy này?")) return;
    History.clear();
    newConv();
    showState("rest");
    renderChatList();
  });

  document.getElementById("side-toggle").addEventListener("click", function () {
    var open = root.getAttribute("data-sidebar") !== "open";
    setSidebar(open);
    if (open && innerWidth < 1080)
      document.getElementById("close-sidebar").focus();
  });
  document
    .getElementById("close-sidebar")
    .addEventListener("click", function () {
      setSidebar(false);
    });
  document
    .getElementById("history-filter")
    .addEventListener("input", renderChatList);
  document.getElementById("scrim").addEventListener("click", function () {
    setSidebar(false);
  });
  addEventListener("keydown", function (e) {
    if (e.key === "Escape" && root.getAttribute("data-sidebar") === "open")
      setSidebar(false);
  });

  (function initSidebar() {
    var pref = null;
    try {
      pref = localStorage.getItem("ng-sidebar");
    } catch (e) {}
    // Màn hẹp thì ngăn kéo che hết nội dung, nên mặc định đóng.
    setSidebar(innerWidth >= 1080 && pref !== "closed");
    renderChatList();
  })();

  /* ---------- gọi API ---------- */

  /* Cuộc hội thoại đang mở. turns giữ đủ để dựng lại màn hình VÀ để gửi ngữ
     cảnh cho máy chủ ở lượt sau. */
  var conv = null; /* { id, title, turns: [{q, payload}] } */
  var current = null; /* AbortController của lượt đang chạy */
  var asking = "";
  var pendingEl = null;

  function newConv() {
    if (current) {
      current.abort();
      current = null;
    }
    pendingEl = null;
    clearTimeout(warmTimer);
    warmSince = null;
    document.getElementById("ask-err").hidden = true;
    conv = null;
    openId = null;
    document.getElementById("thread").innerHTML = "";
  }

  /* Ngữ cảnh gửi lên máy chủ: chỉ ba cặp gần nhất. Máy chủ cũng chặn trần sáu
     lượt, nhưng cắt sẵn ở đây để không gửi đi thứ chắc chắn bị bỏ. */
  function historyForRequest() {
    var turns = (conv && conv.turns) || [];
    var out = [];
    turns.slice(-3).forEach(function (tn) {
      out.push({ role: "user", content: tn.q });
      if (tn.payload && tn.payload.answer) {
        out.push({
          role: "assistant",
          content: String(tn.payload.answer).slice(0, 2000),
        });
      }
    });
    return out;
  }

  /* Đọc text/event-stream từ một phản hồi fetch.
     Vì sao không dùng EventSource nữa: EventSource chỉ biết GET, mà lịch sử hội
     thoại không nhét vừa query string - URL vài KB sẽ bị proxy cắt ngang âm
     thầm. Đổi lại phải tự tách khung sự kiện, nhưng được cái đọc được cả mã
     trạng thái HTTP, nên phân biệt 503 "đang khởi động" với mất kết nối thật
     mà không phải hỏi thêm /api/healthz. */
  function readSSE(res, onEvent) {
    var reader = res.body.getReader();
    var dec = new TextDecoder();
    var buf = "";
    return reader.read().then(function step(r) {
      if (r.done) return;
      buf += dec.decode(r.value, { stream: true });
      var frames = buf.split("\n\n");
      buf = frames.pop(); /* khung cuối có thể còn dở */
      frames.forEach(function (f) {
        var ev = null,
          data = "";
        f.split("\n").forEach(function (line) {
          if (line.indexOf("event:") === 0) ev = line.slice(6).trim();
          else if (line.indexOf("data:") === 0) data += line.slice(5).trim();
        });
        if (ev) {
          var parsed;
          try {
            parsed = JSON.parse(data);
          } catch (e) {
            return;
          }
          onEvent(ev, parsed);
        }
      });
      return reader.read().then(step);
    });
  }

  function ask(question) {
    clearTimeout(warmTimer);
    if (current) {
      current.abort();
      removeTurn(pendingEl);
      current = null;
    }
    document.getElementById("q-input").style.height = "";
    if (innerWidth < 1080) setSidebar(false);
    if (current) {
      current.abort();
      current = null;
    }
    asking = question;
    var ae = document.getElementById("ask-err");
    if (ae) ae.hidden = true;

    if (!conv) conv = { id: null, title: question, turns: [] };
    showState("thread");
    pendingEl = appendTurn(pendingHtml(question));
    var done = {};
    paintSteps(pendingEl, done, "retrieve");
    scrollToTurn(pendingEl);
    document.getElementById("q-input").value = "";

    var ctl = new AbortController();
    current = ctl;
    var mine = pendingEl;
    var receivedAnswer = false;
    var next = { retrieve: "generate", generate: "cite", cite: null };

    fetch("/api/ask/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: question,
        history: historyForRequest(),
      }),
      signal: ctl.signal,
    })
      .then(function (res) {
        if (ctl.signal.aborted) return;
        if (res.status === 503) {
          return res.json().then(function (b) {
            if (ctl.signal.aborted) return;
            var d = (b && b.detail) || {};
            removeTurn(mine);
            warmThenRetry(question, d.elapsed_s);
          });
        }
        if (!res.ok || !res.body) throw new Error("HTTP " + res.status);

        return readSSE(res, function (ev, d) {
          if (ctl.signal.aborted) return;
          if (ev === "step") {
            done[d.step] = d.ms;
            paintSteps(mine, done, next[d.step]);
          } else if (ev === "error") {
            receivedAnswer = true;
            removeTurn(mine);
            if (d.retry_after)
              rateLimitThenRetry(question, d.error, d.retry_after);
            else failAsk(d.error);
          } else if (ev === "done") {
            receivedAnswer = true;
            rateRetried = null;
            warmSince =
              null; /* trả lời được rồi: quên đồng hồ khởi động cũ đi */
            finishTurn(mine, question, d);
          }
        }).then(function () {
          if (!receivedAnswer && !ctl.signal.aborted)
            throw new Error("Incomplete stream");
        });
      })
      .catch(function (err) {
        if (ctl.signal.aborted || (err && err.name === "AbortError")) return;
        removeTurn(mine);
        failAsk("Mất kết nối tới máy chủ. Thử lại giúp mình.");
      })
      .then(function () {
        if (current === ctl) current = null;
      });
  }

  function removeTurn(el) {
    if (el && el.parentNode) el.parentNode.removeChild(el);
    if (pendingEl === el) pendingEl = null;
    // Lượt hỏng bị gỡ đi mà cuộc chưa có lượt nào thành công thì coi như chưa
    // mở cuộc nào, để câu sau không bị dính ngữ cảnh của một lượt thất bại.
    if (conv && !conv.turns.length) conv = null;
  }

  function finishTurn(el, question, payload) {
    el.innerHTML = turnHtml(question, payload);
    if (pendingEl === el) pendingEl = null;
    conv.turns.push({ q: question, payload: payload });
    conv = History.save(conv);
    openId = conv.id;
    renderChatList();
    scrollToTurn(el);
    if (window.gsap && !reducedMotion.matches) {
      gsap.from(el.querySelectorAll(".srcitem"), {
        opacity: 0,
        y: 10,
        duration: 0.4,
        stagger: 0.06,
      });
    }
    window.dispatchEvent(new CustomEvent("luatai:answer", { detail: payload }));
  }

  function failAsk(msg) {
    document.getElementById("q-input").value = asking;
    var ae = document.getElementById("ask-err");
    if (ae) {
      ae.textContent = msg + " Bấm Tra cứu để thử lại.";
      ae.hidden = false;
    }
    // Một lượt hỏng không được xoá cả cuộc đang xem: chỉ về trang chủ khi
    // chưa có lượt nào thành công.
    showState(conv && conv.turns.length ? "thread" : "rest");
  }

  /* Máy chủ đang nạp model: nói thật là đang khởi động, rồi tự thử lại thay vì
     bắt người dùng bấm đi bấm lại. Bỏ cuộc sau 3 phút để không quay vô tận. */
  var WARM_RETRY_MS = 5000,
    WARM_GIVE_UP_MS = 180000;
  var warmSince = null;
  function warmThenRetry(question, elapsed) {
    if (warmSince === null) warmSince = Date.now();
    if (Date.now() - warmSince > WARM_GIVE_UP_MS) {
      warmSince = null;
      failAsk("Máy chủ khởi động quá lâu.");
      return;
    }
    var ae = document.getElementById("ask-err");
    if (ae) {
      ae.textContent =
        "Máy chủ đang khởi động (" +
        (elapsed || 0) +
        " giây), " +
        "thường mất 60-120 giây. Đang tự thử lại…";
      ae.hidden = false;
    }
    showState(conv && conv.turns.length ? "thread" : "rest");
    warmTimer = setTimeout(function () {
      ask(question);
    }, WARM_RETRY_MS);
  }

  /* Mô hình báo chạm giới hạn theo phút (Groq đếm token mỗi phút): đếm ngược
     rồi tự hỏi lại MỘT lần. Lần sau vẫn chạm thì dừng hẳn, tự hỏi tiếp chỉ đốt
     thêm hạn mức. Câu hỏi nằm lại trong ô nhập suốt lúc chờ; gửi câu khác hay
     mở cuộc khác thì đồng hồ bị huỷ cùng warmTimer. */
  var rateRetried = null;
  function rateLimitThenRetry(question, msg, seconds) {
    failAsk(msg);
    if (rateRetried === question) {
      rateRetried = null;
      return;
    }
    rateRetried = question;
    var ae = document.getElementById("ask-err");
    (function tick(left) {
      if (left <= 0) return ask(question);
      if (ae) ae.textContent = msg + " Tự thử lại sau " + left + " giây…";
      warmTimer = setTimeout(function () {
        tick(left - 1);
      }, 1000);
    })(seconds);
  }

  document.getElementById("ask-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var q = document.getElementById("q-input").value.trim();
    if (q) ask(q);
  });
  document.getElementById("back-btn").addEventListener("click", function () {
    // Đang hỏi dở mà bấm quay lại thì phải huỷ luồng, không thì câu trả lời
    // vẫn về và tự ý kéo màn hình sang cuộc vừa rời đi.
    if (current) {
      current.abort();
      current = null;
    }
    var ae = document.getElementById("ask-err");
    if (ae) ae.hidden = true;
    newConv();
    document.getElementById("q-input").value = "";
    showState("rest");
    renderChatList();
    document.getElementById("q-input").focus();
  });
  document.getElementById("qchips").addEventListener("click", function (e) {
    var chip = e.target.closest(".qchip");
    if (!chip) return;
    var input = document.getElementById("q-input");
    input.value = chip.dataset.question;
    input.focus();
  });
  /* Rê vào [n] thì làm mờ các nguồn khác. Uỷ quyền trên cả dòng hội thoại và
     giới hạn trong đúng lượt đang rê - nhiều lượt cùng có [3] nhưng [3] của
     mỗi lượt trỏ tới điều luật khác nhau. */
  var thread = document.getElementById("thread");
  thread.addEventListener("mouseover", function (e) {
    if (!e.target.classList.contains("ref")) return;
    var turn = e.target.closest(".turn");
    if (!turn) return;
    var n = e.target.dataset.n;
    turn.querySelectorAll(".srcitem").forEach(function (el) {
      el.style.opacity = el.dataset.n === n ? "1" : ".4";
    });
  });
  thread.addEventListener("mouseout", function (e) {
    var turn = e.target.closest && e.target.closest(".turn");
    if (!turn) return;
    turn.querySelectorAll(".srcitem").forEach(function (el) {
      el.style.opacity = "1";
    });
  });

  // Thống kê kho lấy từ máy chủ chứ không viết cứng trong HTML: con số viết
  // cứng sẽ sai ngay lần crawl kế tiếp, mà đó lại đúng là thứ người dùng nhìn
  // để tin dữ liệu còn mới.
  function viDate(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
    return m ? m[3] + "/" + m[2] + "/" + m[1] : null;
  }

  function fillCorpusStats() {
    fetch("/api/corpus")
      .then(function (r) {
        return r.json();
      })
      .then(function (meta) {
        if (!meta) {
          document.getElementById("corpus-freshness").textContent =
            "Chưa có thông tin cập nhật kho.";
          return;
        } // chưa refresh lần nào: giữ nguyên dấu gạch
        var n = meta.chunks.toLocaleString("vi-VN");
        var set = function (id, v) {
          var el = document.getElementById(id);
          if (el) el.textContent = v;
        };
        set("corpus-count", n);
        set("stat-chunks", n);
        set("stat-docs", meta.documents.toLocaleString("vi-VN"));

        var crawled = viDate(meta.last_refreshed);
        var newest = viDate(meta.newest_issue_date);
        // Nói rõ HAI mốc khác nhau: ngày kiểm tra nguồn, và ngày của văn bản mới
        // nhất đang có. Gộp làm một là nói quá độ mới của dữ liệu.
        var label = crawled ? "Cập nhật " + crawled : "";
        if (newest)
          label += (label ? " · " : "") + "văn bản mới nhất " + newest;
        set("corpus-freshness", label || "Chưa có thông tin cập nhật");
      })
      .catch(function () {
        document.getElementById("corpus-freshness").textContent =
          "Chưa kết nối được kho dữ liệu.";
      });
  }
  fillCorpusStats();

  var input = document.getElementById("q-input");
  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      document.getElementById("ask-form").requestSubmit();
    }
  });
  input.addEventListener("input", function () {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  });
  var about = document.getElementById("about-dialog");
  document.getElementById("about-open").addEventListener("click", function () {
    about.showModal();
  });
  document.getElementById("about-close").addEventListener("click", function () {
    about.close();
  });
  about.addEventListener("click", function (e) {
    if (e.target === about) {
      var b = about.getBoundingClientRect();
      if (
        e.clientX < b.left ||
        e.clientX > b.right ||
        e.clientY < b.top ||
        e.clientY > b.bottom
      )
        about.close();
    }
  });
  thread.addEventListener("click", function (e) {
    var ref = e.target.closest(".ref");
    if (ref) {
      var turn = ref.closest(".turn");
      var source = turn.querySelector(
        '.statute[data-n="' + ref.dataset.n + '"]',
      );
      if (!source) {
        var details = turn.querySelector("details");
        details.open = true;
        source = turn.querySelector('.srcitem[data-n="' + ref.dataset.n + '"]');
        if (source) source.open = true;
      }
      if (source) {
        source.scrollIntoView({
          behavior: reducedMotion.matches ? "auto" : "smooth",
          block: "center",
        });
        source.classList.add("highlight");
        setTimeout(function () {
          source.classList.remove("highlight");
        }, 1800);
      }
    }
    var copy = e.target.closest(".copy-answer");
    if (copy) {
      var body = copy
        .closest(".card-answer")
        .querySelector(".ansbody").innerText;
      if (!navigator.clipboard) {
        copy.textContent = "Chọn văn bản để sao chép";
        return;
      }
      navigator.clipboard
        .writeText(body)
        .then(function () {
          copy.textContent = "Đã sao chép";
          setTimeout(function () {
            copy.textContent = "Sao chép câu trả lời";
          }, 2000);
        })
        .catch(function () {
          copy.textContent = "Chọn văn bản để sao chép";
        });
    }
  });
  // Keep keyboard focus within the mobile drawer while it covers the chat.
  document.getElementById("sidebar").addEventListener("keydown", function (e) {
    if (e.key !== "Tab" || innerWidth >= 1080) return;
    var nodes = Array.from(
      this.querySelectorAll('a, button, input, [tabindex="0"]'),
    ).filter(function (el) {
      return !el.disabled;
    });
    var first = nodes[0],
      last = nodes[nodes.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });
  window.LuatAI = {
    setMode: setMode,
    showState: showState,
    currentMode: currentMode,
  };
})();
