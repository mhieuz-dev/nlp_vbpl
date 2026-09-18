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
  var KEY = 'ng-chats-v1';
  var MAX = 50;

  function read() {
    try {
      var raw = localStorage.getItem(KEY);
      var v = raw ? JSON.parse(raw) : [];
      return Array.isArray(v) ? v : [];
    } catch (e) {
      return [];   // hỏng định dạng hoặc bị chặn: coi như chưa có gì
    }
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

    /* Trả về bản ghi vừa lưu để bên gọi biết id mà đánh dấu đang mở. */
    add: function (question, payload) {
      var item = {
        id: String(Date.now()) + '-' + Math.random().toString(36).slice(2, 8),
        q: question,
        at: Date.now(),
        payload: payload
      };
      write([item].concat(read()).slice(0, MAX));
      return item;
    },

    remove: function (id) {
      write(read().filter(function (c) { return c.id !== id; }));
    },

    clear: function () {
      try { localStorage.removeItem(KEY); } catch (e) {}
    }
  };
})();
