/*!
 * smartkeyboard.js — SmartBox kiosk 触屏软键盘(iOS/安卓风,含拼音)
 * 依赖: pinyin-ime.js (window.PinyinIME.getCandidates) — 缺失时拼音降级为不可用,英文照常。
 *       pinyin-compose.js (window.PinyinCompose) — 多长度候选合成 + 词频重排;缺失时候选
 *       退化为「整 buffer 一次性转换」的旧逻辑(与 pinyin-ime.js 缺失降级同款防御)。
 * 自动绑定页面所有 text/password/search/url/email/tel/number 输入框与 textarea。
 * 无外部依赖、无构建步骤。触屏用 pointerdown 触发以保证响应并保持输入框聚焦。
 */
(function () {
  "use strict";

  var CAND_PAGE_SIZE = 7;
  var FREQ_KEY = "skbd-freq-v1";

  function loadFreq() {
    try {
      var raw = window.localStorage && localStorage.getItem(FREQ_KEY);
      var parsed = raw ? JSON.parse(raw) : null;
      return (parsed && typeof parsed === "object" && !Array.isArray(parsed)) ? parsed : {};
    } catch (e) { return {}; }
  }

  function saveFreq(freq) {
    try { localStorage.setItem(FREQ_KEY, JSON.stringify(freq)); }
    catch (e) { /* 静默降级为不排序 */ }
  }

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

  var state = {
    mode: "en", layer: "letters", shift: false, target: null, buffer: "",
    cands: [], page: 0, freq: loadFreq()
  };
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
      if (state.buffer) flushBuffer();   // 非拼音键中断:整串 flush 上屏,不留孤悬 buffer
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
    if (state.mode === "zh" && state.buffer) { flushBuffer(); return; }
    var el = state.target;
    if (el && el.tagName === "TEXTAREA") { insertText("\n"); }
    else { hideKbd(); }
  }

  // 候选项统一为 {t: 上屏文本, l: 消费的拼音长度}。PinyinCompose 在场时走多长度合成 +
  // 词频重排;缺失时退回旧行为 —— 对整个 buf 一次性转换,l = buf.length(即"选中即清空整
  // 个缓冲"的旧语义),与 pinyin-ime.js 本身缺失时的降级同款(全部候选为空数组)。
  function computeCands(buf) {
    if (!buf) return [];
    try {
      if (window.PinyinCompose) {
        return window.PinyinCompose.boostByHistory(
          window.PinyinCompose.lookup(buf, function (p) {
            return (window.PinyinIME && window.PinyinIME.getCandidates(p)) || [];
          }),
          state.freq
        );
      }
      if (!window.PinyinIME) return [];
      var raw = window.PinyinIME.getCandidates(buf) || [];
      return raw.map(function (t) { return { t: t, l: buf.length }; });
    } catch (e) { return []; }
  }

  function getCands() { return computeCands(state.buffer); }

  // 空格 = 用户接受当前首选(单次选中,计入词频);死尾 buffer 无候选时原样上屏字母。
  function commitFirst() {
    var c = getCands();
    if (c.length) commit(c[0], true);
    else { insertText(state.buffer); clearBuffer(); }
  }

  // 非拼音键中断组词时整串 flush:循环上屏首选直到 buffer 耗尽。R4-1 递归可切分保证终止——
  // 候选非空 ⇒ 每轮至少消费 1 个字母(l ≥ 1),余串要么空要么仍有候选;某轮 lookup 为空
  // (死尾 buffer,如 beiwuu)则丢弃剩余死字母。自动 flush 不是用户点选,不记词频。
  function flushBuffer() {
    while (state.buffer) {
      var c = getCands();
      if (!c.length || c[0].l <= 0) { clearBuffer(); return; }  // 死尾丢弃(l<=0 为防御,不可达)
      commit(c[0], false);
    }
  }

  // 选中候选 item:上屏 item.t,buffer 只消费 item.l(可能 < buffer.length —— 多长度候选
  // 未必吃掉整串)。buffer 非空则立即用剩余串重查并回到第 1 页;buffer 空则清候选条。
  // isUserChoice: 仅用户主动点选(候选条点击/空格接受首选)计入词频;自动 flush 传 false。
  function commit(item, isUserChoice) {
    insertText(item.t);
    if (isUserChoice) recordFreq(item.t);
    state.buffer = state.buffer.slice(item.l);
    updateCandidates();
  }

  function recordFreq(t) {
    if (!window.PinyinCompose) return;
    try {
      state.freq = window.PinyinCompose.recordChoice(state.freq, t);
      saveFreq(state.freq);
    } catch (e) { /* 静默降级为不排序 */ }
  }

  function clearBuffer() { state.buffer = ""; updateCandidates(); }

  function updateCandidates() {
    if (!candBar) return;
    if (state.mode !== "zh") { compose.textContent = ""; candList.innerHTML = ""; state.cands = []; state.page = 0; return; }
    compose.textContent = state.buffer;
    state.cands = state.buffer ? getCands() : [];
    state.page = 0;
    renderCandPage();
  }

  // 只重渲染候选行(翻页调用路径),不触碰键盘主体(rowsEl 不重建)。
  function renderCandPage() {
    candList.innerHTML = "";
    if (!state.buffer) return;
    if (!state.cands.length) {
      var em = document.createElement("span");
      em.className = "skbd-cand-empty"; em.textContent = "无候选";
      candList.appendChild(em); return;
    }
    var totalPages = Math.max(1, Math.ceil(state.cands.length / CAND_PAGE_SIZE));
    if (state.page >= totalPages) state.page = totalPages - 1;
    if (state.page < 0) state.page = 0;
    var start = state.page * CAND_PAGE_SIZE;
    var pageItems = state.cands.slice(start, start + CAND_PAGE_SIZE);

    var prevBtn = document.createElement("button");
    prevBtn.type = "button"; prevBtn.className = "skbd-cand-prev"; prevBtn.textContent = "‹";
    var atFirst = state.page <= 0;
    prevBtn.disabled = atFirst;
    if (atFirst) prevBtn.className += " skbd-cand-nav-disabled";
    tap(prevBtn, function () {
      if (state.page > 0) { state.page--; renderCandPage(); }
    });
    candList.appendChild(prevBtn);

    pageItems.forEach(function (item) {
      var it = document.createElement("button");
      it.type = "button"; it.className = "skbd-cand-item"; it.textContent = item.t;
      tap(it, function () { commit(item, true); });
      candList.appendChild(it);
    });

    var nextBtn = document.createElement("button");
    nextBtn.type = "button"; nextBtn.className = "skbd-cand-next"; nextBtn.textContent = "›";
    var atLast = state.page >= totalPages - 1;
    nextBtn.disabled = atLast;
    if (atLast) nextBtn.className += " skbd-cand-nav-disabled";
    tap(nextBtn, function () {
      if (state.page < totalPages - 1) { state.page++; renderCandPage(); }
    });
    candList.appendChild(nextBtn);

    var pageLabel = document.createElement("span");
    pageLabel.className = "skbd-cand-page";
    pageLabel.textContent = (state.page + 1) + "/" + totalPages;
    candList.appendChild(pageLabel);
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
