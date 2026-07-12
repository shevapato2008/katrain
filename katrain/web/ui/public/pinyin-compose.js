/*!
 * pinyin-compose.js — smartkeyboard 的候选合成层(纯函数,node 可测)
 * lookup: 多长度合并候选 —— 每候选携带 l(消费的拼音长度)。
 *   余串递归可切分才保留该层(R4-1):选任何候选后,余串要么空要么仍有候选,杜绝悬挂 buffer。
 *   公平封顶(R3-1/R4-2):三趟配额 1→10→cap,长层大列表挤不掉短层,层多时每层仍有代表。
 *   跨层同文本消费长度取存活层最长 L(R4-3):引擎只对 query ≤ 词全拼长度返回该词,
 *   最长 L 永不多吃下一词字母;取短 L 会少吃(women 选我们只吃 wom → 剩 en)。
 * segment: 候选区「分词下划线」用的纯切分(零 DOM、零引擎依赖,只用静态音节表)。
 *   不用 getCandidates——引擎的 key 含多音节词(如 wugong=蜈蚣),贪心会切出词级段,
 *   而候选区要的是音节级 bei·wu·gong·yuan 下划线;脱离引擎后词库替换对 segment 测试零影响。
 *   已知取舍:贪心最长切分,xian 切 xian 不切 xi·an(主流 IME 无分隔符输入时同此行为)。
 */
(function (global) {
  "use strict";

  // 音节表:tools/gen-syllables.py 产物(pypinyin 0.55.0,MIT,仅构建期依赖),字典序,420 个,含 lv/nv。
  var SYLLABLES = [
    "a", "ai", "an", "ang", "ao", "ba", "bai", "ban", "bang", "bao",
    "bei", "ben", "beng", "bi", "bian", "biang", "biao", "bie", "bin", "bing",
    "bo", "bong", "bu", "ca", "cai", "can", "cang", "cao", "ce", "cei",
    "cen", "ceng", "cha", "chai", "chan", "chang", "chao", "che", "chen", "cheng",
    "chi", "chong", "chou", "chu", "chua", "chuai", "chuan", "chuang", "chui", "chun",
    "chuo", "ci", "cong", "cou", "cu", "cuan", "cui", "cun", "cuo", "da",
    "dai", "dan", "dang", "dao", "de", "dei", "den", "deng", "di", "dia",
    "dian", "diao", "die", "din", "ding", "diu", "dong", "dou", "du", "duan",
    "dui", "dun", "duo", "e", "ei", "en", "eng", "er", "fa", "fan",
    "fang", "fei", "fen", "feng", "fiao", "fo", "fou", "fu", "ga", "gai",
    "gan", "gang", "gao", "ge", "gei", "gen", "geng", "gong", "gou", "gu",
    "gua", "guai", "guan", "guang", "gui", "gun", "guo", "ha", "hai", "han",
    "hang", "hao", "he", "hei", "hen", "heng", "hong", "hou", "hu", "hua",
    "huai", "huan", "huang", "hui", "hun", "huo", "ji", "jia", "jian", "jiang",
    "jiao", "jie", "jin", "jing", "jiong", "jiu", "ju", "juan", "jue", "jun",
    "ka", "kai", "kan", "kang", "kao", "ke", "kei", "ken", "keng", "kong",
    "kou", "ku", "kua", "kuai", "kuan", "kuang", "kui", "kun", "kuo", "la",
    "lai", "lan", "lang", "lao", "le", "lei", "len", "leng", "li", "lia",
    "lian", "liang", "liao", "lie", "lin", "ling", "liu", "lo", "long", "lou",
    "lu", "luan", "lun", "luo", "lv", "lve", "ma", "mai", "man", "mang",
    "mao", "me", "mei", "men", "meng", "mi", "mian", "miao", "mie", "min",
    "ming", "miu", "mo", "mou", "mu", "na", "nai", "nan", "nang", "nao",
    "ne", "nei", "nen", "neng", "ni", "nia", "nian", "niang", "niao", "nie",
    "nin", "ning", "niu", "nong", "nou", "nu", "nuan", "nun", "nuo", "nv",
    "nve", "o", "ou", "pa", "pai", "pan", "pang", "pao", "pei", "pen",
    "peng", "pi", "pian", "piao", "pie", "pin", "ping", "po", "pou", "pu",
    "qi", "qia", "qian", "qiang", "qiao", "qie", "qin", "qing", "qiong", "qiu",
    "qu", "quan", "que", "qun", "ran", "rang", "rao", "re", "ren", "reng",
    "ri", "rong", "rou", "ru", "rua", "ruan", "rui", "run", "ruo", "sa",
    "sai", "san", "sang", "sao", "se", "sen", "seng", "sha", "shai", "shan",
    "shang", "shao", "she", "shei", "shen", "sheng", "shi", "shou", "shu", "shua",
    "shuai", "shuan", "shuang", "shui", "shun", "shuo", "si", "song", "sou", "su",
    "suan", "sui", "sun", "suo", "ta", "tai", "tan", "tang", "tao", "te",
    "tei", "teng", "ti", "tian", "tiao", "tie", "ting", "tong", "tou", "tu",
    "tuan", "tui", "tun", "tuo", "wa", "wai", "wan", "wang", "wei", "wen",
    "weng", "wo", "wong", "wu", "xi", "xia", "xian", "xiang", "xiao", "xie",
    "xin", "xing", "xiong", "xiu", "xu", "xuan", "xue", "xun", "ya", "yan",
    "yang", "yao", "ye", "yi", "yin", "ying", "yo", "yong", "you", "yu",
    "yuan", "yue", "yun", "za", "zai", "zan", "zang", "zao", "ze", "zei",
    "zen", "zeng", "zha", "zhai", "zhan", "zhang", "zhao", "zhe", "zhei", "zhen",
    "zheng", "zhi", "zhong", "zhou", "zhu", "zhua", "zhuai", "zhuan", "zhuang", "zhui",
    "zhun", "zhuo", "zi", "zong", "zou", "zu", "zuan", "zui", "zun", "zuo"
  ];
  var _SYL = Object.create(null), _SYLPRE = Object.create(null);
  (function () {                       // 音节集 + 前缀集(判「打了一半的音节」)
    for (var i = 0; i < SYLLABLES.length; i++) {
      var s = SYLLABLES[i]; _SYL[s] = 1;
      for (var j = 1; j <= s.length; j++) _SYLPRE[s.slice(0, j)] = 1;
    }
  })();

  // segment(buffer, headL):把缓冲切成展示段。
  // 第一段 = buffer.slice(0, headL)(当前头候选将消费的段,由调用方从 lookup 头候选取 l;headL=0 无当前段)。
  // 余下部分贪心取最长音节,且余串仍可切(_segFeasible);
  // 结尾若是某音节的真前缀 → {text, partial:true}(打字中,虚线不报错);
  // 无任何可行切分 → 余串整段 {text, dead:true}(与 commit 死尾丢弃语义一致)。
  // 返回 [{text, partial?, dead?}, ...];空 buffer 返回 []。
  function _segFeasible(s, memo) {     // s 可被切为「音节* + 可选的音节前缀结尾」
    if (!s) return true;
    if (memo[s] !== undefined) return memo[s];
    memo[s] = _SYLPRE[s] === 1;        // 整个剩余是半个音节 → 可行(partial 尾)
    if (!memo[s])
      for (var L = Math.min(s.length, 6); L >= 1; L--)
        if (_SYL[s.slice(0, L)] === 1 && _segFeasible(s.slice(L), memo)) { memo[s] = true; break; }
    return memo[s];
  }
  function segment(buffer, headL) {
    var segs = [], rest = buffer, memo = {};
    if (headL > 0) { segs.push({ text: buffer.slice(0, headL) }); rest = buffer.slice(headL); }
    while (rest.length > 0) {
      if (_SYLPRE[rest] === 1 && _SYL[rest] !== 1) { segs.push({ text: rest, partial: true }); break; }
      var took = 0;
      for (var L = Math.min(rest.length, 6); L >= 1; L--)
        if (_SYL[rest.slice(0, L)] === 1 && _segFeasible(rest.slice(L), memo)) { took = L; break; }
      if (!took) { segs.push({ text: rest, dead: true }); break; }
      segs.push({ text: rest.slice(0, took) });
      rest = rest.slice(took);
    }
    return segs;
  }

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

  var api = { lookup: lookup, boostByHistory: boostByHistory, recordChoice: recordChoice, segment: segment };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  global.PinyinCompose = api;
})(typeof window !== "undefined" ? window : globalThis);
