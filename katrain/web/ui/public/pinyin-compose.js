/*!
 * pinyin-compose.js — smartkeyboard 的候选合成层(纯函数,node 可测)
 * lookup: 多长度合并候选 —— 每候选携带 l(消费的拼音长度)。
 *   余串递归可切分才保留该层(R4-1):选任何候选后,余串要么空要么仍有候选,杜绝悬挂 buffer。
 *   公平封顶(R3-1/R4-2):三趟配额 1→10→cap,长层大列表挤不掉短层,层多时每层仍有代表。
 *   跨层同文本消费长度取存活层最长 L(R4-3):引擎只对 query ≤ 词全拼长度返回该词,
 *   最长 L 永不多吃下一词字母;取短 L 会少吃(women 选我们只吃 wom → 剩 en)。
 */
(function (global) {
  "use strict";

  function _viable(s, getCandidates, memo) {
    // R4-1(R3-3 完整版):s 可整段切分为「每段都有候选」的拼音串。
    // 空串可行;否则存在某个有候选的前缀,且其余串递归可行。memo 按余串键控,
    // 余串都是 buffer 的后缀(≤ n 个),每个只算一次 → 每次按键 O(n²) 次查询封顶。
    if (!s) return true;
    if (memo[s] !== undefined) return memo[s];
    memo[s] = false;
    for (var L = s.length; L >= 1; L--) {
      if ((getCandidates(s.slice(0, L)) || []).length &&
          _viable(s.slice(L), getCandidates, memo)) { memo[s] = true; break; }
    }
    return memo[s];
  }

  function lookup(buffer, getCandidates, cap) {
    cap = cap || 120;
    var cache = Object.create(null);           // 本次调用内的查询缓存(层扫描与可行性检查共享)
    var gc = function (q) {
      if (cache[q] === undefined) cache[q] = getCandidates(q) || [];
      return cache[q];
    };
    var layers = [], memo = {}, L, i, j;
    for (L = buffer.length; L >= 1; L--) {
      var cands = gc(buffer.slice(0, L));
      if (!cands.length) continue;
      if (!_viable(buffer.slice(L), gc, memo)) continue;   // R4-1: 余串必须可整段切分
      layers.push({ L: L, cands: cands, idx: 0, taken: 0 });
    }
    var maxL = Object.create(null);            // R4-3: 文本 → 存活层中的最长 L(层已按 L 降序)
    for (i = 0; i < layers.length; i++)
      for (j = 0; j < layers[i].cands.length; j++) {
        var t0 = layers[i].cands[j];
        if (maxL[t0] === undefined) maxL[t0] = layers[i].L;
      }
    var items = [], seen = Object.create(null);
    function take(layer, upTo) {
      while (layer.idx < layer.cands.length && layer.taken < upTo && items.length < cap) {
        var t = layer.cands[layer.idx++];
        if (!seen[t]) { seen[t] = 1; items.push({ t: t, l: maxL[t] }); layer.taken++; }
      }
    }
    for (i = 0; i < layers.length; i++) take(layers[i], 1);    // R4-2 第 0 趟:每层至少 1 个代表
    for (i = 0; i < layers.length; i++) take(layers[i], 10);   // R3-1 第 1 趟:每层保底 10
    for (i = 0; i < layers.length; i++) take(layers[i], cap);  // 第 2 趟:按 L 降序补满
    return items;
  }

  function boostByHistory(items, counts) {
    if (!counts) return items.slice();
    return items.slice().sort(function (a, b) {
      return (counts[b.t] || 0) - (counts[a.t] || 0);   // Array.sort 是稳定排序(ES2019)
    });
  }

  function recordChoice(counts, t, cap) {
    cap = cap || 200;
    var next = {}, k;
    for (k in counts) next[k] = counts[k];
    next[t] = (next[t] || 0) + 1;
    var keys = Object.keys(next);
    if (keys.length > cap) {
      var minKey = null;                                 // R3-2: 只在非 t 里找淘汰对象
      for (var i = 0; i < keys.length; i++) {
        if (keys[i] === t) continue;
        if (minKey === null || next[keys[i]] < next[minKey]) minKey = keys[i]; // 平局取插入序最先
      }
      if (minKey !== null) delete next[minKey];
    }
    return next;
  }

  var api = { lookup: lookup, boostByHistory: boostByHistory, recordChoice: recordChoice };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  global.PinyinCompose = api;
})(typeof window !== "undefined" ? window : globalThis);
