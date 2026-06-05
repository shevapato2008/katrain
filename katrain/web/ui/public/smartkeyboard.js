/*!
 * smartkeyboard.js — SmartBox kiosk 触屏软键盘(iOS/安卓风,含拼音)
 * 依赖: pinyin-ime.js (window.PinyinIME.getCandidates) — 缺失时拼音降级为不可用,英文照常。
 * 自动绑定页面所有 text/password/search/url/email/tel/number 输入框与 textarea。
 * 无外部依赖、无构建步骤。触屏用 pointerdown 触发以保证响应并保持输入框聚焦。
 */
(function () {
  "use strict";

  var ICON_BACK = '<svg viewBox="0 0 24 24"><path d="M22 3H7c-.7 0-1.3.4-1.7.9L0 12l5.3 8.1c.4.5 1 .9 1.7.9h15c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-3 12.6L17.6 17 14 13.4 10.4 17 9 15.6 12.6 12 9 8.4 10.4 7 14 10.6 17.6 7 19 8.4 15.4 12 19 15.6z"/></svg>';
  var ICON_SHIFT = '<svg viewBox="0 0 24 24"><path d="M12 5l8 8h-5v6H9v-6H4l8-8z"/></svg>';

  var LAYOUTS = {
    letters: [
      ["q","w","e","r","t","y","u","i","o","p"],
      ["a","s","d","f","g","h","j","k","l"],
      [{k:"shift",fn:1,wide:1,icon:ICON_SHIFT},"z","x","c","v","b","n","m",{k:"back",fn:1,wide:1,icon:ICON_BACK}],
      [{k:"num",fn:1,label:"123"},{k:"lang",fn:1},{k:"space",label:"空格"},{k:"return",label:"换行"}]
    ],
    num: [
      ["1","2","3","4","5","6","7","8","9","0"],
      ["-","/",":",";","(",")","¥","&","@","\""],
      [{k:"sym",fn:1,label:"#+="},".",",","?","!","'",{k:"back",fn:1,wide:1,icon:ICON_BACK}],
      [{k:"abc",fn:1,label:"ABC"},{k:"lang",fn:1},{k:"space",label:"空格"},{k:"return",label:"换行"}]
    ],
    sym: [
      ["[","]","{","}","#","%","^","*","+","="],
      ["_","\\","|","~","<",">","€","$","·","•"],
      [{k:"num",fn:1,label:"123"},".",",","?","!","'",{k:"back",fn:1,wide:1,icon:ICON_BACK}],
      [{k:"abc",fn:1,label:"ABC"},{k:"lang",fn:1},{k:"space",label:"空格"},{k:"return",label:"换行"}]
    ]
  };

  var state = { mode: "en", layer: "letters", shift: false, target: null, buffer: "" };
  var root, candBar, compose, candList, rowsEl;

  function isEditable(el) {
    if (!el) return false;
    if (el.tagName === "TEXTAREA") return true;
    if (el.tagName !== "INPUT") return false;
    var t = (el.type || "text").toLowerCase();
    return /^(text|password|search|url|email|tel|number)$/.test(t);
  }

  // 触屏/鼠标统一: pointerdown 触发并阻止默认(保持输入框聚焦、避免合成 click 丢失)
  function tap(el, fn) {
    el.addEventListener("pointerdown", function (e) {
      e.preventDefault();
      e.stopPropagation();
      fn();
    });
  }

  function build() {
    root = document.createElement("div");
    root.className = "skbd";

    var handle = document.createElement("div");
    handle.className = "skbd-handle";
    var grab = document.createElement("div"); grab.className = "skbd-grab";
    var hide = document.createElement("button"); hide.className = "skbd-hide"; hide.type = "button"; hide.innerHTML = "⌄";
    tap(hide, hideKbd);
    handle.appendChild(grab); handle.appendChild(hide);
    root.appendChild(handle);

    candBar = document.createElement("div"); candBar.className = "skbd-cand";
    compose = document.createElement("span"); compose.className = "skbd-compose";
    candList = document.createElement("div"); candList.className = "skbd-cand-list";
    candList.style.cssText = "display:flex;overflow-x:auto;flex:1 1 auto;";
    candBar.appendChild(compose); candBar.appendChild(candList);
    root.appendChild(candBar);

    rowsEl = document.createElement("div"); rowsEl.className = "skbd-rows";
    root.appendChild(rowsEl);

    // 点键盘背景空隙时也保持输入框聚焦
    root.addEventListener("pointerdown", function (e) { e.preventDefault(); });

    document.body.appendChild(root);
    render();
  }

  function keyLabel(spec) {
    if (typeof spec === "string") return state.shift ? spec.toUpperCase() : spec;
    if (spec.icon) return spec.icon;
    if (spec.k === "lang") return state.mode === "zh" ? "中" : "EN";
    return spec.label || spec.k;
  }

  function render() {
    root.classList.toggle("skbd-zh", state.mode === "zh");
    rowsEl.innerHTML = "";
    var rows = LAYOUTS[state.layer];
    rows.forEach(function (row) {
      var rEl = document.createElement("div"); rEl.className = "skbd-row";
      row.forEach(function (spec) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "skbd-key";
        var k = typeof spec === "string" ? spec : spec.k;
        if (typeof spec !== "string") {
          if (spec.fn) btn.className += " skbd-key-fn";
          if (spec.wide) btn.className += " skbd-key-wide";
          if (spec.k === "space") btn.className += " skbd-key-space";
          if (spec.k === "return") btn.className += " skbd-key-return";
          if (spec.k === "shift" && state.shift) btn.className += " skbd-key-active";
        }
        btn.innerHTML = keyLabel(spec);
        tap(btn, function () { onKey(k, spec); });
        rEl.appendChild(btn);
      });
      rowsEl.appendChild(rEl);
    });
    updateCandidates();
  }

  function onKey(k, spec) {
    switch (k) {
      case "shift": state.shift = !state.shift; render(); return;
      case "back": onBack(); return;
      case "space": onSpace(); return;
      case "return": onReturn(); return;
      case "num": state.layer = "num"; render(); return;
      case "sym": state.layer = "sym"; render(); return;
      case "abc": state.layer = "letters"; render(); return;
      case "lang":
        state.mode = state.mode === "zh" ? "en" : "zh";
        if (state.mode === "en") clearBuffer();
        render(); return;
      default:
        onChar(k);
    }
  }

  function onChar(ch) {
    var out = state.shift ? ch.toUpperCase() : ch;
    if (state.mode === "zh" && state.layer === "letters" && /^[a-z]$/.test(ch)) {
      state.buffer += ch;       // 拼音始终小写
      updateCandidates();
    } else {
      if (state.buffer) commitFirst();   // 有拼音缓冲时先上屏首选
      insertText(out);
    }
    if (state.shift && state.layer === "letters") { state.shift = false; render(); }
  }

  function onBack() {
    if (state.mode === "zh" && state.buffer) {
      state.buffer = state.buffer.slice(0, -1);
      updateCandidates();
    } else {
      deleteBack();
    }
  }

  function onSpace() {
    if (state.mode === "zh" && state.buffer) { commitFirst(); }
    else { insertText(" "); }
  }

  function onReturn() {
    if (state.mode === "zh" && state.buffer) { commitFirst(); return; }
    var el = state.target;
    if (el && el.tagName === "TEXTAREA") { insertText("\n"); }
    else { hideKbd(); }
  }

  function getCands() {
    if (!state.buffer || !window.PinyinIME) return [];
    try { return window.PinyinIME.getCandidates(state.buffer) || []; }
    catch (e) { return []; }
  }

  function commitFirst() {
    var c = getCands();
    if (c.length) commit(c[0]);
    else { insertText(state.buffer); clearBuffer(); }
  }

  function commit(text) { insertText(text); clearBuffer(); }

  function clearBuffer() { state.buffer = ""; updateCandidates(); }

  function updateCandidates() {
    if (!candBar) return;
    if (state.mode !== "zh") { compose.textContent = ""; candList.innerHTML = ""; return; }
    compose.textContent = state.buffer;
    candList.innerHTML = "";
    if (!state.buffer) return;
    var cands = getCands().slice(0, 60);
    if (!cands.length) {
      var em = document.createElement("span");
      em.className = "skbd-cand-empty"; em.textContent = "无候选";
      candList.appendChild(em); return;
    }
    cands.forEach(function (w) {
      var it = document.createElement("button");
      it.type = "button"; it.className = "skbd-cand-item"; it.textContent = w;
      tap(it, function () { commit(w); });
      candList.appendChild(it);
    });
  }

  // 用原生 value setter 赋值,绕过 React/Vue 的 value 追踪器,确保框架 onChange 能识别
  function setNativeValue(el, value) {
    var proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    var desc = Object.getOwnPropertyDescriptor(proto, "value");
    if (desc && desc.set) { desc.set.call(el, value); } else { el.value = value; }
  }

  function insertText(text) {
    var el = state.target; if (!el) return;
    try { el.focus(); } catch (e) {}
    var start, end;
    try { start = el.selectionStart; end = el.selectionEnd; } catch (e) { start = end = null; }
    var v = el.value;
    if (start === null || start === undefined) {
      setNativeValue(el, v + text);
    } else {
      setNativeValue(el, v.slice(0, start) + text + v.slice(end));
      var pos = start + text.length;
      try { el.setSelectionRange(pos, pos); } catch (e) {}
    }
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function deleteBack() {
    var el = state.target; if (!el) return;
    try { el.focus(); } catch (e) {}
    var start, end;
    try { start = el.selectionStart; end = el.selectionEnd; } catch (e) { start = end = null; }
    if (start === null || start === undefined) {
      setNativeValue(el, el.value.slice(0, -1));
    } else if (start !== end) {
      setNativeValue(el, el.value.slice(0, start) + el.value.slice(end));
      try { el.setSelectionRange(start, start); } catch (e) {}
    } else if (start > 0) {
      setNativeValue(el, el.value.slice(0, start - 1) + el.value.slice(end));
      try { el.setSelectionRange(start - 1, start - 1); } catch (e) {}
    }
    el.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function showKbd(target) {
    state.target = target;
    root.classList.add("skbd-open");
    document.body.classList.add("skbd-padded");
    requestAnimationFrame(function () {
      document.body.style.paddingBottom = root.offsetHeight + "px";
      try { target.scrollIntoView({ block: "center", behavior: "smooth" }); } catch (e) {}
    });
  }

  function hideKbd() {
    root.classList.remove("skbd-open");
    clearBuffer();
    state.target = null;
    document.body.style.paddingBottom = "";
    document.body.classList.remove("skbd-padded");
  }

  function init() {
    build();
    document.addEventListener("focusin", function (e) {
      if (isEditable(e.target)) showKbd(e.target);
    });
    document.addEventListener("focusout", function () {
      setTimeout(function () {
        if (!isEditable(document.activeElement)) hideKbd();
      }, 150);
    });
    window.SmartKeyboard = { show: showKbd, hide: hideKbd };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else { init(); }
})();
