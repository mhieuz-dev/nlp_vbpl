/* Lịch sử hỏi đáp, lưu ngay trong trình duyệt.
 *
 * Vì sao localStorage chứ không phải máy chủ: lịch sử chỉ có nghĩa với đúng
 * người đã hỏi, mà muốn nhận ra người trên máy chủ thì phải có tài khoản.
 * Không đăng nhập thì "từng cá nhân" rốt cuộc cũng chỉ là "từng trình duyệt" -
 * đúng bằng thứ localStorage cho sẵn, miễn phí, và không bắt ai giao câu hỏi
 * pháp luật của họ cho một cơ sở dữ liệu người khác giữ.
 *
 * Đánh đổi: đổi máy hoặc xoá dữ liệu duyệt web là mất lịch sử.
 */
(function () {
  var KEY = 'ng-chats-v2';
  var OLD_KEY = 'ng-chats-v1';   /* bản một-câu-một-đáp */
  var MAX = 50;

  function read() {
    try {
      var raw = localStorage.getItem(KEY);
      if (raw) {
        var v = JSON.parse(raw);
        return Array.isArray(v) ? v : [];
      }
      return migrate();
    } catch (e) {
      return [];   // hỏng định dạng hoặc bị chặn: coi như chưa có gì
    }
  }

  /* Bản v1 lưu mỗi mục là một cặp hỏi-đáp; v2 là một cuộc gồm nhiều lượt. Đổi
     một lần khi đọc, để người đã dùng bản trước không mở lên thấy trắng trơn. */
  function migrate() {
    var raw = null;
    try { raw = localStorage.getItem(OLD_KEY); } catch (e) {}
    if (!raw) return [];
    var cu = [];
    try { cu = JSON.parse(raw) || []; } catch (e) { return []; }
    var moi = cu.map(function (c) {
      return { id: c.id, title: c.q, at: c.at, turns: [{ q: c.q, payload: c.payload }] };
    });
    write(moi);
    try { localStorage.removeItem(OLD_KEY); } catch (e) {}
    return moi;
  }

  /* Ghi, và nếu hết chỗ thì bỏ dần cuộc cũ nhất rồi thử lại. Một câu trả lời
   * kèm 10 điều luật nặng vài chục KB, mà localStorage chỉ có ~5 MB. */
  function write(list) {
    for (var n = list.length; n > 0; n--) {
      try {
        localStorage.setItem(KEY, JSON.stringify(list.slice(0, n)));
        return list.slice(0, n);
      } catch (e) { /* QuotaExceededError: cắt bớt rồi thử lại */ }
    }
    try { localStorage.removeItem(KEY); } catch (e) {}
    return [];
  }

  window.LuatAIHistory = {
    list: read,

    get: function (id) {
      var found = null;
      read().forEach(function (c) { if (c.id === id) found = c; });
      return found;
    },

    /* Ghi một cuộc: mới thì thêm vào đầu, đã có thì cập nhật và đẩy lên đầu.
       Trả lại chính cuộc đó (đã gắn id) để bên gọi dùng tiếp. */
    save: function (conv) {
      if (!conv.id) conv.id = String(Date.now()) + '-' + Math.random().toString(36).slice(2, 8);
      conv.at = Date.now();
      if (!conv.title) conv.title = (conv.turns[0] || {}).q || 'Cuộc mới';
      var con_lai = read().filter(function (c) { return c.id !== conv.id; });
      write([conv].concat(con_lai).slice(0, MAX));
      return conv;
    },

    remove: function (id) {
      write(read().filter(function (c) { return c.id !== id; }));
    },

    clear: function () {
      try { localStorage.removeItem(KEY); } catch (e) {}
    }
  };
})();
