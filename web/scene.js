/* Pannellum 2.5.6, self-hosted (MIT). A generated equirectangular panorama
 * provides real, continuous 360-degree yaw, independent of the chat layer. */
(function () {
  "use strict";
  var scene = document.querySelector(".scene");
  var host = document.getElementById("panorama-scene");
  var workspace = document.querySelector(".workspace");
  var toggle = document.getElementById("motion-toggle");
  var reset = document.getElementById("scene-reset");
  var angle = document.getElementById("panorama-angle");
  var angleOutput = document.getElementById("panorama-angle-value");
  var reduce = matchMedia("(prefers-reduced-motion: reduce)");
  var blocked =
    "a, button, input, textarea, label, select, summary, dialog, .sidebar, .topbar, .welcome, .thread, .restextra, .composer-note, .foot, .searchbar, .err";
  var viewer,
    ready = false,
    drag = null,
    manual = false,
    disposed = false;
  var yaw = 0,
    pitch = -8,
    last = 0,
    frame = 0,
    enabled = true;
  try {
    enabled = localStorage.getItem("verdict-motion") !== "off";
  } catch (e) {}

  // No horizontal clamp: after 180 degrees, continue through the rear of the room.
  function fieldOfView() {
    // Keep portrait screens from looking through an exaggerated fisheye lens.
    return Math.max(
      42,
      Math.min(
        100,
        (2 *
          Math.atan(
            (Math.tan((75 * Math.PI) / 360) * scene.clientWidth) /
              scene.clientHeight,
          ) *
          180) /
          Math.PI,
      ),
    );
  }
  function wrap(value) {
    return ((((value + 180) % 360) + 360) % 360) - 180;
  }
  function updateLabels() {
    var degrees = Math.round(((yaw % 360) + 360) % 360) % 360;
    angle.value = degrees;
    angleOutput.textContent = degrees + "°";
    scene.dataset.yaw = String(yaw);
    scene.dataset.pitch = String(pitch);
    toggle.setAttribute(
      "aria-pressed",
      String(ready && enabled && !reduce.matches),
    );
    toggle.title = reduce.matches
      ? "Tự xoay đã tắt theo cài đặt hệ thống; bạn vẫn có thể kéo để xem"
      : "Bật hoặc tắt tự xoay nền";
    workspace.dataset.rotatable = String(ready);
    reset.disabled =
      !ready || (!manual && Math.abs(yaw) < 0.1 && Math.abs(pitch + 8) < 0.1);
    angle.disabled = !ready;
  }
  function render() {
    if (!ready) return;
    viewer.lookAt(pitch, yaw, undefined, false);
    updateLabels();
  }
  function endDrag() {
    var previous = drag;
    drag = null;
    if (previous && workspace.hasPointerCapture(previous.id))
      workspace.releasePointerCapture(previous.id);
    delete workspace.dataset.dragging;
  }
  function canDrag(e) {
    return (
      ready &&
      e.pointerType !== "touch" &&
      workspace.contains(e.target) &&
      !e.target.closest(blocked)
    );
  }
  function tick(stamp) {
    frame = 0;
    if (
      !ready ||
      disposed ||
      document.hidden ||
      !enabled ||
      reduce.matches ||
      manual
    )
      return;
    var elapsed = Math.min((stamp - last) / 1000, 0.1);
    if (stamp - last >= 40) {
      last = stamp;
      if (!/^(TEXTAREA|INPUT)$/.test(document.activeElement.tagName)) {
        yaw = wrap(yaw + elapsed * 1.2);
        render();
      }
    }
    frame = requestAnimationFrame(tick);
  }
  function resume() {
    cancelAnimationFrame(frame);
    frame = 0;
    last = performance.now();
    updateLabels();
    if (
      ready &&
      !disposed &&
      !document.hidden &&
      enabled &&
      !reduce.matches &&
      !manual
    )
      frame = requestAnimationFrame(tick);
  }
  function chooseView(nextYaw, nextPitch) {
    manual = true;
    cancelAnimationFrame(frame);
    frame = 0;
    yaw = wrap(nextYaw);
    pitch = Math.max(-85, Math.min(85, nextPitch));
    render();
  }
  function center() {
    endDrag();
    manual = false;
    yaw = 0;
    pitch = -8;
    render();
    resume();
  }
  function fallback() {
    ready = false;
    endDrag();
    cancelAnimationFrame(frame);
    host.hidden = true;
    scene.dataset.renderer = "static";
    toggle.disabled = true;
    updateLabels();
    toggle.title = "Đang dùng ảnh nền tĩnh vì toàn cảnh 360° chưa khả dụng";
  }
  toggle.addEventListener("click", function () {
    enabled = !enabled;
    if (enabled) manual = false;
    try {
      localStorage.setItem("verdict-motion", enabled ? "on" : "off");
    } catch (e) {}
    resume();
  });
  reset.addEventListener("click", center);
  angle.addEventListener("input", function () {
    chooseView(Number(angle.value), pitch);
  });
  workspace.addEventListener("pointerdown", function (e) {
    if (e.button !== 0 || !canDrag(e)) return;
    e.preventDefault();
    if (/^(TEXTAREA|INPUT)$/.test(document.activeElement.tagName))
      document.activeElement.blur();
    manual = true;
    cancelAnimationFrame(frame);
    frame = 0;
    drag = {
      id: e.pointerId,
      x: e.clientX,
      y: e.clientY,
      yaw: yaw,
      pitch: pitch,
    };
    workspace.setPointerCapture(e.pointerId);
    workspace.dataset.dragging = "true";
  });
  workspace.addEventListener("pointermove", function (e) {
    workspace.dataset.grabbable = String(canDrag(e));
    if (!drag || drag.id !== e.pointerId) return;
    // Roughly one half-turn per workspace width; repeated drags can loop forever.
    var sensitivity = 180 / Math.max(scene.clientWidth, 320);
    chooseView(
      drag.yaw + (drag.x - e.clientX) * sensitivity,
      drag.pitch + (e.clientY - drag.y) * sensitivity,
    );
  });
  workspace.addEventListener("pointerup", endDrag);
  workspace.addEventListener("pointercancel", endDrag);
  workspace.addEventListener("lostpointercapture", function () {
    drag = null;
    delete workspace.dataset.dragging;
  });
  window.addEventListener("blur", endDrag);
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) endDrag();
    resume();
  });
  reduce.addEventListener("change", resume);
  var observer = new ResizeObserver(function () {
    if (ready) {
      viewer.resize();
      viewer.setHfov(fieldOfView(), false);
    }
  });
  observer.observe(scene);
  window.addEventListener("pagehide", function (e) {
    cancelAnimationFrame(frame);
    endDrag();
    if (!e.persisted) {
      disposed = true;
      observer.disconnect();
      if (viewer) viewer.destroy();
    }
  });
  window.addEventListener("pageshow", resume);
  try {
    if (!window.pannellum) {
      fallback();
      return;
    }
    viewer = pannellum.viewer("panorama-scene", {
      type: "equirectangular",
      panorama: "/assets/library-panorama.png",
      autoLoad: true,
      showControls: false,
      showFullscreenCtrl: false,
      showZoomCtrl: false,
      draggable: false,
      mouseZoom: false,
      keyboardZoom: false,
      disableKeyboardCtrl: true,
      compass: false,
      hfov: fieldOfView(),
      minHfov: 30,
      yaw: 0,
      pitch: -8,
      haov: 360,
      vaov: 180,
      backgroundColor: [0.08, 0.06, 0.04],
      strings: { loadingLabel: "Đang tải toàn cảnh…" },
    });
    viewer.on("load", function () {
      ready = true;
      scene.dataset.renderer = "panorama-360";
      host.classList.add("ready");
      host.querySelectorAll("[tabindex]").forEach(function (el) {
        el.tabIndex = -1;
      });
      var canvas = host.querySelector("canvas");
      if (canvas)
        canvas.addEventListener("webglcontextlost", function (e) {
          e.preventDefault();
          fallback();
        });
      render();
      resume();
    });
    viewer.on("error", fallback);
  } catch (e) {
    fallback();
  }
})();
