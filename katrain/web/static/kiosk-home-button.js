/* SmartBox kiosk "主页" button — injected (same-origin) into the KaTrain (:8081) and
 * hermes-webui (:8787) app pages so the user can always return to the launcher
 * (:8080/launcher) to switch modes. Self-contained: no dependencies, no globals leaked,
 * idempotent. Positioned top-left to avoid the bottom smartkeyboard.
 */
(function () {
  "use strict";
  if (window.__smartboxHomeBtn) return;
  window.__smartboxHomeBtn = true;
  var LAUNCHER_URL = "http://127.0.0.1:8080/launcher";

  function mount() {
    if (document.getElementById("smartbox-home-btn")) return;
    var btn = document.createElement("button");
    btn.id = "smartbox-home-btn";
    btn.type = "button";
    btn.textContent = "🏠 主页";
    btn.setAttribute("aria-label", "返回主页切换模式");
    var s = btn.style;
    s.position = "fixed"; s.top = "10px"; s.left = "10px"; s.zIndex = "2147483647";
    s.padding = "8px 14px"; s.fontSize = "15px"; s.fontWeight = "600";
    s.color = "#fff"; s.background = "rgba(15,20,25,.82)"; s.border = "1px solid rgba(255,255,255,.35)";
    s.borderRadius = "10px"; s.cursor = "pointer"; s.fontFamily = "-apple-system,'PingFang SC',sans-serif";
    s.webkitTapHighlightColor = "transparent"; s.touchAction = "manipulation"; s.userSelect = "none";
    btn.addEventListener("click", function () { window.location.href = LAUNCHER_URL; });
    document.body.appendChild(btn);
  }

  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount);
})();
