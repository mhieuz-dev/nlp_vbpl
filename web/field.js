(function () {
  var canvas = document.getElementById('field');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  var root = document.documentElement;
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  var coords = null;   // Float32Array N*3, mỗi giá trị trong [-1,1]
  var count = 0;
  var idIndex = {};    // chunk_id -> chỉ số hàng
  var hot = [];        // [{x,y,z}] toạ độ chuẩn hoá của top-5
  var qx = 0, qy = 0;  // tâm cụm top-5, toạ độ màn hình
  var W = 0, H = 0, t = 0;
  var still = null;    // canvas ngoài màn hình chứa trường tĩnh

  function css(n) { return getComputedStyle(root).getPropertyValue(n).trim(); }

  function project(i) {
    return {
      x: W * 0.5 + coords[i * 3] * W * 0.42,
      y: H * 0.5 + coords[i * 3 + 1] * H * 0.42,
      z: coords[i * 3 + 2]
    };
  }

  /* Trường tĩnh vẽ một lần vào canvas ngoài màn hình rồi blit mỗi khung —
     48.803 chấm mà vẽ lại từng khung thì phí CPU vô ích. */
  function renderStill() {
    if (!coords || !W || !H) return;
    still = document.createElement('canvas');
    still.width = canvas.width;
    still.height = canvas.height;
    var s = still.getContext('2d');
    s.setTransform(canvas.width / W, 0, 0, canvas.height / H, 0, 0);
    var dot = css('--field-dot');
    var mul = parseFloat(css('--field-alpha')) || 1;
    s.fillStyle = dot;
    for (var i = 0; i < count; i++) {
      var p = project(i);
      var depth = (p.z + 1) / 2;              // 0 xa, 1 gần
      s.globalAlpha = mul * (0.10 + depth * 0.30);
      var size = 0.7 + depth * 1.1;
      s.fillRect(p.x, p.y, size, size);
    }
    s.globalAlpha = 1;
  }

  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = canvas.clientWidth;
    H = canvas.clientHeight;
    if (!W || !H) return;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    renderStill();
    recomputeHot();
    paintOnce();
  }
  window.addEventListener('resize', resize);

  function recomputeHot() {
    if (!hot.length || !W || !H) return;
    var sx = 0, sy = 0;
    hot.forEach(function (h) {
      h.px = W * 0.5 + h.x * W * 0.42;
      h.py = H * 0.5 + h.y * H * 0.42;
      sx += h.px; sy += h.py;
    });
    qx = sx / hot.length;
    qy = sy / hot.length;
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    if (still) ctx.drawImage(still, 0, 0, W, H);
    if (hot.length) {
      var mint = css('--field-near');
      var link = css('--coral');
      var ring = css('--mint-ring');
      ctx.globalAlpha = 0.7;
      ctx.strokeStyle = link;
      ctx.lineWidth = 1;
      hot.forEach(function (h) {
        ctx.beginPath(); ctx.moveTo(qx, qy); ctx.lineTo(h.px, h.py); ctx.stroke();
      });
      hot.forEach(function (h, k) {
        ctx.globalAlpha = 0.65 + 0.35 * Math.sin(t * 1.6 + k);
        ctx.fillStyle = mint;
        ctx.beginPath(); ctx.arc(h.px, h.py, 3.2, 0, 6.283); ctx.fill();
      });
      ctx.globalAlpha = 0.6;
      ctx.strokeStyle = ring;
      ctx.beginPath(); ctx.arc(qx, qy, 14 + Math.sin(t * 1.1) * 3, 0, 6.283); ctx.stroke();
      ctx.globalAlpha = 1;
    }
    t += 0.016;
    if (!reduce) requestAnimationFrame(draw);
  }

  /* Vòng rAF bị tắt khi người dùng bật giảm chuyển động, nên phải vẽ lại thủ công
     mỗi khi trạng thái đổi — nếu không, nền và các điểm nổi bật sẽ không bao giờ cập nhật. */
  function paintOnce() {
    if (reduce) draw();
  }

  Promise.all([
    fetch('/vector_map.bin').then(function (r) {
      if (!r.ok) throw new Error('không có vector_map.bin');
      return r.arrayBuffer();
    }),
    fetch('/vector_map.json').then(function (r) {
      if (!r.ok) throw new Error('không có vector_map.json');
      return r.json();
    })
  ]).then(function (res) {
    coords = new Float32Array(res[0]);
    count = res[1].count;
    res[1].ids.forEach(function (id, i) { idIndex[id] = i; });
    /* Không ghi #corpus-count ở đây nữa: vector_map.json là artifact đồ hoạ,
       chụp lại kho ở thời điểm chạy export_vector_map.py, nên nó tụt hậu ngay
       sau lần crawl kế tiếp. Con số đó do app.js lấy từ /api/corpus. */
    resize();
    draw();
  }).catch(function () {
    /* Chưa chạy scripts/export_vector_map.py — nền để trống, app vẫn dùng được. */
  });

  window.addEventListener('luatai:mode', function () {
    renderStill();
    paintOnce();
  });

  window.addEventListener('luatai:answer', function (e) {
    if (!coords) return;
    hot = [];
    e.detail.chunks.forEach(function (c) {
      var i = idIndex[c.chunk_id];
      if (i === undefined) return;
      hot.push({ x: coords[i * 3], y: coords[i * 3 + 1], z: coords[i * 3 + 2] });
    });
    recomputeHot();
    paintOnce();
  });
})();
