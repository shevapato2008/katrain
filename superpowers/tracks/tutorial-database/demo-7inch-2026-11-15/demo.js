(() => {
  // ../../../../katrain/web/ui/src/kiosk/tutorial/ogsExercise.ts
  var other = (stone) => stone === "B" ? "W" : "B";
  var onBoard = (board, [x, y]) => Number.isInteger(x) && Number.isInteger(y) && y >= 0 && y < board.length && x >= 0 && x < board[y].length;
  var neighbors = ([x, y]) => [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]];
  var pointKey = ([x, y]) => `${x},${y}`;
  var samePoint = (a, b) => a?.[0] === b[0] && a?.[1] === b[1];
  function groupAt(board, point) {
    const color = board[point[1]][point[0]];
    if (!color) return { stones: [], hasLiberty: false };
    const seen = /* @__PURE__ */ new Set([pointKey(point)]);
    const stones = [point];
    let hasLiberty = false;
    for (let i = 0; i < stones.length; i += 1) {
      for (const neighbor of neighbors(stones[i])) {
        if (!onBoard(board, neighbor)) continue;
        const value = board[neighbor[1]][neighbor[0]];
        if (value === null) hasLiberty = true;
        else if (value === color && !seen.has(pointKey(neighbor))) {
          seen.add(pointKey(neighbor));
          stones.push(neighbor);
        }
      }
    }
    return { stones, hasLiberty };
  }
  function boardsEqual(a, b) {
    return a.length === b.length && a.every((row, y) => row.length === b[y].length && row.every((stone, x) => stone === b[y][x]));
  }
  function moveRecord(before, after, point, player) {
    const captured = [];
    for (let y = 0; y < before.length; y += 1) {
      for (let x = 0; x < before[y].length; x += 1) {
        if (before[y][x] === other(player) && after[y][x] === null) captured.push([x, y]);
      }
    }
    return { point, player, captured };
  }
  function hasCorrectContinuation(node) {
    return node.correct || node.children.some(hasCorrectContinuation);
  }
  function createOgsExercise(step2) {
    const board = Array.from({ length: step2.size }, () => Array(step2.size).fill(null));
    for (const stone of ["B", "W"]) {
      for (const [x, y] of step2.stones[stone]) {
        if (onBoard(board, [x, y])) board[y][x] = stone;
      }
    }
    return {
      step: step2,
      board,
      player: step2.initial_player,
      treeCursor: step2.exercise.kind === "puzzle" ? step2.exercise.tree : null,
      status: "active",
      selectedRemoval: [],
      previousBoard: null,
      lastTransition: null
    };
  }
  function applyGoMove(board, point, player, previousBoard) {
    if (!onBoard(board, point) || board[point[1]][point[0]] !== null) return null;
    const next = board.map((row) => [...row]);
    next[point[1]][point[0]] = player;
    for (const neighbor of neighbors(point)) {
      if (!onBoard(next, neighbor) || next[neighbor[1]][neighbor[0]] !== other(player)) continue;
      const group = groupAt(next, neighbor);
      if (!group.hasLiberty) {
        for (const [x, y] of group.stones) next[y][x] = null;
      }
    }
    if (!groupAt(next, point).hasLiberty || previousBoard && boardsEqual(next, previousBoard)) return null;
    return next;
  }
  function playOgsPoint(state, point) {
    if (state.status !== "active" || !onBoard(state.board, point)) return state;
    if (state.step.exercise.kind === "remove") {
      if (!state.board[point[1]][point[0]]) return state;
      const group = groupAt(state.board, point).stones.sort(([ax, ay], [bx, by]) => ax - bx || ay - by);
      const toggled = new Set(group.map(pointKey));
      const selectedRemoval = state.selectedRemoval.some((selected2) => toggled.has(pointKey(selected2))) ? state.selectedRemoval.filter((selected2) => !toggled.has(pointKey(selected2))) : [...state.selectedRemoval, ...group];
      const selected = new Set(selectedRemoval.map(pointKey));
      const targets = state.step.exercise.remove_targets;
      const correct = selected.size === targets.length && targets.every((target) => selected.has(pointKey(target)));
      return { ...state, selectedRemoval, status: correct ? "correct" : "active" };
    }
    if (state.step.exercise.kind !== "puzzle") return state;
    const afterMove = applyGoMove(state.board, point, state.player, state.previousBoard);
    if (!afterMove) return state;
    const child = state.treeCursor?.children.find((candidate) => samePoint(candidate.point, point));
    const playerMove = moveRecord(state.board, afterMove, point, state.player);
    let next = {
      ...state,
      board: afterMove,
      previousBoard: state.board,
      player: other(state.player),
      treeCursor: child ?? state.treeCursor,
      status: child?.correct ? "correct" : child?.wrong || !child ? "wrong" : "active",
      lastTransition: { playerMove, automaticResponses: [] }
    };
    if (next.status !== "active" || !child?.children.length) return next;
    const solvable = child.children.filter(hasCorrectContinuation);
    const replies = [...solvable, ...child.children.filter((reply) => !hasCorrectContinuation(reply))];
    for (const reply of replies) {
      if (!reply.point) continue;
      const afterReply = applyGoMove(next.board, reply.point, next.player, next.previousBoard);
      if (!afterReply) continue;
      const response = moveRecord(next.board, afterReply, reply.point, next.player);
      next = {
        ...next,
        board: afterReply,
        previousBoard: next.board,
        player: other(next.player),
        treeCursor: reply,
        status: reply.correct ? "correct" : reply.wrong ? "wrong" : "active",
        lastTransition: { playerMove, automaticResponses: [response] }
      };
      break;
    }
    return next;
  }
  function chooseOgsAnswer(state, value) {
    const exercise = state.step.exercise;
    if (state.status !== "active" || exercise.kind !== "choice" || !exercise.choices.some((choice) => choice.value === value)) return state;
    return { ...state, status: value === exercise.correct_choice ? "correct" : "wrong" };
  }
  function actOgsExercise(state, action) {
    if (state.status !== "active" || state.step.exercise.kind !== action) return state;
    return { ...state, status: "correct" };
  }
  function retryOgsExercise(state) {
    return createOgsExercise(state.step);
  }

  // demo.ts
  var screen = document.querySelector("#screen");
  var stage = document.querySelector("#stage");
  var escape = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  var course;
  var manifest;
  var chapter = 2;
  var lessonId = "";
  var view = "catalog";
  var clipIndex = 0;
  var stepIndex = 0;
  var step = null;
  var answer = null;
  var stepError = "";
  var mode = "fit";
  var offline = false;
  var fetchRevision = 0;
  var tips = {
    "count-liberties": "\u6C14\u662F\u68CB\u5757\u4E0A\u4E0B\u5DE6\u53F3\u7D27\u90BB\u7684\u7A7A\u4EA4\u53C9\u70B9\u3002\u5148\u8BA4\u540C\u4E00\u5757\u68CB\uFF0C\u518D\u6570\u6C14\uFF1B\u5171\u7528\u7684\u7A7A\u70B9\u53EA\u7B97\u4E00\u6B21\u3002",
    "count_chains": "\u540C\u8272\u68CB\u5B50\u6CBF\u4E0A\u4E0B\u5DE6\u53F3\u76F8\u8FDE\uFF0C\u624D\u5C5E\u4E8E\u540C\u4E00\u5757\u68CB\uFF1B\u659C\u7740\u9760\u8FD1\u4E0D\u7B97\u8FDE\u63A5\u3002",
    "in_atari": "\u6574\u5757\u68CB\u53EA\u5269\u6700\u540E\u4E00\u53E3\u6C14\uFF0C\u5C31\u5904\u4E8E\u88AB\u6253\u5403\u7684\u72B6\u6001\u3002\u8981\u6570\u6574\u5757\u68CB\uFF0C\u4E0D\u80FD\u53EA\u770B\u5176\u4E2D\u4E00\u9897\u3002",
    "capture_stone": "\u5148\u627E\u5230\u5BF9\u65B9\u68CB\u5B50\u7684\u6700\u540E\u4E00\u53E3\u6C14\uFF0C\u843D\u5728\u90A3\u4E2A\u4EA4\u53C9\u70B9\u4E0A\uFF0C\u6CA1\u6C14\u7684\u5BF9\u65B9\u68CB\u5B50\u5C31\u4F1A\u88AB\u63D0\u8D70\u3002",
    "capture_chain": "\u76F8\u8FDE\u7684\u68CB\u5B50\u5171\u4EAB\u6C14\uFF1B\u6700\u540E\u4E00\u53E3\u6C14\u88AB\u5835\u4F4F\u65F6\uFF0C\u8981\u628A\u6574\u5757\u6CA1\u6C14\u7684\u68CB\u53D6\u8D70\u3002",
    "escape": "\u5148\u627E\u76EE\u6807\u68CB\u5757\u7684\u6700\u540E\u4E00\u53E3\u6C14\uFF0C\u518D\u770B\u8D70\u51FA\u53BB\u4EE5\u540E\u80FD\u5426\u83B7\u5F97\u65B0\u7684\u6C14\u3002",
    "find_escape": "\u6551\u68CB\u4E0D\u80FD\u53EA\u770B\u773C\u524D\u4E00\u6B65\u3002\u6BD4\u8F83\u4E0D\u540C\u51FA\u8DEF\uFF0C\u770B\u770B\u5BF9\u624B\u7EE7\u7EED\u6253\u5403\u540E\uFF0C\u68CB\u5757\u8FD8\u80FD\u4E0D\u80FD\u8DD1\u3002",
    "create_opening": "\u60F3\u4E00\u60F3\u5BF9\u624B\u7684\u5E94\u624B\uFF0C\u518D\u6BD4\u8F83\u51FA\u8DEF\u3002\u53EF\u4EE5\u91CD\u770B\u8BB2\u89E3\u91CC\u7684\u53D8\u5316\u3002",
    "ladder": "\u987A\u7740\u6253\u5403\u3001\u9003\u8DD1\u7684\u6B21\u5E8F\u5F80\u524D\u8BFB\uFF1B\u6BCF\u4E00\u6B65\u90FD\u68C0\u67E5\u6C14\uFF0C\u76F4\u5230\u80FD\u591F\u5224\u65AD\u8FD9\u6761\u8DEF\u7684\u7ED3\u679C\u3002"
  };
  function scale() {
    const full = !!document.fullscreenElement;
    const s = mode === "actual" && !full ? 1 : Math.min(full ? 5 : 1.2, (innerWidth - (full ? 0 : 64)) / 1024, (innerHeight - (full ? 0 : 170)) / 600);
    stage.style.width = `${1024 * s}px`;
    stage.style.height = `${600 * s}px`;
    screen.style.transform = `scale(${s})`;
    document.body.classList.toggle("fullscreen", full);
  }
  addEventListener("resize", scale);
  document.addEventListener("fullscreenchange", scale);
  document.querySelector("#fit").addEventListener("click", () => {
    mode = "fit";
    scale();
  });
  document.querySelector("#actual").addEventListener("click", () => {
    mode = "actual";
    scale();
  });
  document.querySelector("#fullscreen").addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen();
  });
  document.querySelector("#offline").addEventListener("click", () => {
    offline = !offline;
    const button = document.querySelector("#offline");
    button.textContent = `\u672C\u5730\u5907\u7528\uFF1A${offline ? "\u5F00" : "\u5173"}`;
    button.classList.toggle("on", offline);
    if (view === "video") render();
  });
  function lesson() {
    return course.lessons.find((l) => l.id === lessonId);
  }
  function clips() {
    return (manifest.playlists[lessonId] || []).map((id) => manifest.clips.find((c) => c.id === id));
  }
  function clip() {
    return clips()[clipIndex] || null;
  }
  function header(text, back = false) {
    return `<header class="topbar">${back ? '<button class="key small flat" id="back">\u2039 \u8FD4\u56DE</button>' : ""}<div class="brand">\u667A\u661F\u76D2</div><div class="crumb">${escape(text)}</div><span class="tag">\u5148\u5B66\u8BB2\u89E3 \xB7 \u518D\u505A\u7EC3\u4E60</span></header>`;
  }
  function nav(next, lid) {
    screen.querySelector("video")?.pause();
    if (lid && lid !== lessonId) {
      lessonId = lid;
      clipIndex = 0;
      stepIndex = 0;
      step = null;
      answer = null;
    }
    view = next;
    render();
  }
  function bind(id, fn) {
    screen.querySelector(id)?.addEventListener("click", fn);
  }
  function renderCatalog() {
    const c = course.chapters.find((c2) => c2.number === chapter);
    const lessons = course.lessons.filter((l) => l.chapter_id === c.id);
    const videoCount = lessons.filter((l) => manifest.playlists[l.id]?.length).length;
    screen.innerHTML = header("\u56F4\u68CB\u6559\u7A0B") + `<main class="course-layout"><aside class="rail"><div class="eyebrow">\u4ECE\u8BA4\u8BC6\u68CB\u76D8\uFF0C\u5230\u4EB2\u624B\u843D\u5B50</div><h1>\u5165\u95E8\u8BFE\u7A0B</h1>${course.chapters.map((c2) => `<button class="tab ${chapter === c2.number ? "current" : ""}" data-chapter="${c2.number}"><span class="num">0${c2.number}</span>${escape(c2.title)}</button>`).join("")}<p class="quiet">\u9009\u4E00\u4E2A\u5C0F\u8282\uFF0C<br>\u5148\u770B\u68CB\u76D8\u4E0A\u7684\u8BB2\u89E3\uFF0C<br>\u518D\u4EB2\u624B\u5B8C\u6210\u7EC3\u4E60\u3002</p><div class="rail-bottom">\u8BB2\u89E3\u56FE\uFF1A\u56F4\u68CB\u6559\u5BA4<br>\u4E92\u52A8\u7EC3\u4E60\uFF1AOGS\u539F\u9898</div></aside><section class="course-main"><div class="section-head"><h2>${escape(c.title)}</h2><span class="count">${lessons.length}\u5C0F\u8282 \xB7 ${videoCount}\u8282\u914D\u6709\u89C6\u9891</span></div><div class="section-sub">\u5FAA\u5E8F\u6E10\u8FDB\uFF0C\u4E00\u6B21\u5B66\u61C2\u4E00\u4E2A\u5C0F\u4E3B\u9898\u3002</div><div class="lesson-list">${lessons.map((l) => {
      const n = manifest.playlists[l.id]?.length || 0;
      return `<button class="lesson" data-lesson="${escape(l.id)}"><span class="lesson-number">${escape(l.course_code)}</span><span class="copy"><strong>${escape(l.title)}</strong><span class="meta ${n ? "ready" : ""}">${n ? `${n}\u6BB5\u8BB2\u89E3 \xB7 ` : "\u89C6\u9891\u5F85\u8865 \xB7 "}${l.step_count}\u9053\u7EC3\u4E60</span></span><span class="chevron">\u203A</span></button>`;
    }).join("")}</div></section></main>`;
    screen.querySelectorAll("[data-chapter]").forEach((el) => el.addEventListener("click", () => {
      chapter = Number(el.dataset.chapter);
      render();
    }));
    screen.querySelectorAll("[data-lesson]").forEach((el) => el.addEventListener("click", () => nav("lesson", el.dataset.lesson)));
  }
  function renderLesson() {
    const l = lesson(), c = clip(), list = clips();
    screen.innerHTML = header(`${l.course_code} ${l.title}`, true) + `<main class="lesson-layout"><section class="panel lesson-preview">${c ? `<button class="cover" id="watch-cover" aria-label="\u64AD\u653E${escape(c.title)}"><img src="posters/${c.id}.jpg" alt="${escape(c.title)}\u7684\u89C6\u9891\u753B\u9762"><span class="play-bubble">\u25B6</span></button>` : '<div class="cover no-video"><div class="quiet-copy">\u8FD9\u8282\u7684\u4E92\u52A8\u7EC3\u4E60\u5DF2\u5C31\u7EEA<br>\u89C6\u9891\u8BB2\u89E3\u5F85\u8865\u5145</div></div>'}<div class="playlist">${list.length ? list.map((c2, i) => `<button class="key small ${i === clipIndex ? "primary" : ""}" data-clip="${i}">${i + 1}. ${escape(c2.title)}</button>`).join("") : '<span class="section-sub">\u53EF\u4EE5\u76F4\u63A5\u5F00\u59CB\u672C\u8282OGS\u7EC3\u4E60\u3002</span>'}</div></section><section class="panel details"><div class="eyebrow">\u7B2C${chapter}\u7AE0 \xB7 ${escape(l.course_code)}</div><h1>${escape(l.title)}</h1><p class="learning-tip">${escape(tips[l.id] || l.subtext || "\u5148\u770B\u61C2\u68CB\u76D8\u4E0A\u7684\u53D8\u5316\uFF0C\u518D\u7528\u7EC3\u4E60\u68C0\u9A8C\u81EA\u5DF1\u7684\u7406\u89E3\u3002")}</p><p class="lesson-meta">${list.length ? `${list.length}\u6BB5\u8BB2\u89E3 \xB7 ` : ""}${l.step_count}\u9053\u7EC3\u4E60</p><div class="credit">${c ? `\u66F9\u85B0\u94C9\xB7\u674E\u660C\u9550\u300A\u56F4\u68CB\u6559\u5BA4\u300B<br>\u5165\u95E8\u7BC7\xB7${c.catalog_id === "intro-up" ? "\u4E0A" : "\u4E0B"}\u5377 / PDF\u7B2C${c.page}\u9875` : "\u7EC3\u4E60\u53D6\u81EAOGS\u56F4\u68CB\u5165\u95E8\u6559\u7A0B"}<br><button class="key small flat" id="source">\u67E5\u770B\u6765\u6E90</button></div><div class="actions">${c ? '<button class="key primary" id="watch">\u25B6 \u5F00\u59CB\u8BB2\u89E3</button>' : ""}<button class="key ${c ? "" : "primary"}" id="practice">\u52A8\u624B\u7EC3\u4E60 \u2192</button></div></section></main>`;
    bind("#watch", () => nav("video"));
    bind("#watch-cover", () => nav("video"));
    bind("#practice", startPractice);
    bind("#back", () => nav("catalog"));
    bind("#source", sourceDialog);
    screen.querySelectorAll("[data-clip]").forEach((el) => el.addEventListener("click", () => {
      clipIndex = Number(el.dataset.clip);
      nav("video");
    }));
  }
  function renderVideo() {
    const c = clip();
    if (!c) {
      nav("lesson");
      return;
    }
    const more = clipIndex + 1 < clips().length;
    screen.innerHTML = `<section class="video-view"><video id="player" src="${offline ? `media-cache/${c.id}.mp4` : `stream/${c.id}.mp4`}" controls playsinline preload="metadata" poster="posters/${c.id}.jpg" aria-label="${escape(c.title)}"></video><div class="video-top"><button class="key small" id="back">\u2039 \u8FD4\u56DE</button><span class="video-name">${clipIndex + 1}/${clips().length} \xB7 ${escape(c.title)}</span><button class="key small primary next" id="next-video">${more ? "\u4E0B\u4E00\u6BB5\u8BB2\u89E3 \u203A" : "\u52A8\u624B\u7EC3\u4E60 \u2192"}</button></div></section>`;
    const player = screen.querySelector("video");
    player.addEventListener("play", () => screen.querySelector(".video-view")?.classList.add("playing"));
    player.addEventListener("pause", () => screen.querySelector(".video-view")?.classList.remove("playing"));
    player.addEventListener("ended", () => {
      screen.querySelector(".video-view")?.classList.remove("playing");
      screen.querySelector("#next-video")?.classList.add("primary");
    });
    player.addEventListener("error", () => {
      const overlay = document.createElement("div");
      overlay.className = "video-error";
      overlay.innerHTML = `\u89C6\u9891\u6682\u65F6\u65E0\u6CD5\u52A0\u8F7D<br><button class="key primary" id="fallback" style="margin-top:12px">${offline ? "\u91CD\u8BD5\u64AD\u653E" : "\u4F7F\u7528\u672C\u5730\u6F14\u793A\u5907\u7528"}</button>`;
      screen.querySelector(".video-view").append(overlay);
      bind("#fallback", () => {
        offline = true;
        const b = document.querySelector("#offline");
        b.textContent = "\u672C\u5730\u5907\u7528\uFF1A\u5F00";
        b.classList.add("on");
        renderVideo();
      });
    });
    bind("#back", () => nav("lesson"));
    bind("#next-video", () => {
      if (more) {
        clipIndex += 1;
        nav("video");
      } else startPractice();
    });
    player.play().catch(() => {
    });
  }
  function startPractice() {
    step = null;
    answer = null;
    stepIndex = 0;
    nav("exercise");
  }
  async function loadStep() {
    const revision = ++fetchRevision, l = lesson();
    stepError = "";
    try {
      const response = await fetch(`/api/steps/${l.first_page + stepIndex}`, { signal: AbortSignal.timeout(15e3) });
      if (!response.ok) throw Error("unavailable");
      const data = await response.json();
      if (revision !== fetchRevision || view !== "exercise") return;
      if (data.lesson_id !== lessonId || data.page !== l.first_page + stepIndex) throw Error("wrong identity");
      step = data;
      answer = createOgsExercise(data);
      render();
    } catch {
      if (revision === fetchRevision && view === "exercise") {
        stepError = "\u7EC3\u4E60\u6682\u65F6\u65E0\u6CD5\u8BFB\u53D6\uFF0C\u8BF7\u8054\u7F51\u540E\u91CD\u8BD5\u3002";
        render();
      }
    }
  }
  function boardSvg() {
    const n = step.size, vp = step.viewport || { col: 0, row: 0, cols: n, rows: n };
    const pos = (x) => 50 + x * 100;
    let shapes = `<defs><radialGradient id="black"><stop stop-color="#626560" offset="0"/><stop stop-color="#151815" offset=".4"/><stop stop-color="#020403" offset="1"/></radialGradient><radialGradient id="white"><stop stop-color="#fffef5"/><stop stop-color="#dedfd6" offset=".8"/><stop stop-color="#a5ada5" offset="1"/></radialGradient><linearGradient id="wood" x2="1" y2="1"><stop stop-color="#e9cb92"/><stop stop-color="#caa66f" offset="1"/></linearGradient></defs><rect width="${n * 100}" height="${n * 100}" fill="url(#wood)"/>`;
    for (let i = 0; i < n; i++) shapes += `<path d="M50 ${pos(i)}H${pos(n - 1)}M${pos(i)} 50V${pos(n - 1)}" stroke="#665027" stroke-width="2.5"/>`;
    const stars = n === 9 ? [2, 6] : n === 13 ? [3, 9] : [3, 9, 15];
    for (const x of stars) for (const y of stars) shapes += `<circle cx="${pos(x)}" cy="${pos(y)}" r="6" fill="#665027"/>`;
    const selected = new Set(answer.selectedRemoval.map((p) => p.join(",")));
    for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
      if (answer.board[y][x]) {
        const stone = answer.board[y][x] === "B" ? "black.png" : `white-${String((x * 3 + y * 7) % 32).padStart(2, "0")}.png`;
        shapes += `<circle cx="${pos(x) + 4}" cy="${pos(y) + 6}" r="40" fill="#0004"/><image href="assets/stones/${stone}" x="${pos(x) - 42}" y="${pos(y) - 42}" width="84" height="84"/>${selected.has(`${x},${y}`) ? `<circle cx="${pos(x)}" cy="${pos(y)}" r="33" fill="none" stroke="#65c084" stroke-width="7"/>` : ""}`;
      }
    }
    for (const [point, label] of Object.entries(step.letters || {})) {
      const [x, y] = point.split(",").map(Number);
      shapes += `<text x="${pos(x)}" y="${pos(y) + 16}" font-size="50" fill="#18241b" stroke="#ead59c" stroke-width="6" paint-order="stroke" text-anchor="middle">${escape(label)}</text>`;
    }
    for (const [point, shape] of Object.entries(step.shapes || {})) {
      const [x, y] = point.split(",").map(Number);
      const label = { triangle: "\u25B3", square: "\u25A1", circle: "\u25CB", cross: "\xD7" }[shape] || shape;
      shapes += `<text x="${pos(x)}" y="${pos(y) + 15}" font-size="45" fill="#8b3f23" text-anchor="middle">${escape(label)}</text>`;
    }
    if (answer.status === "active" && ["puzzle", "remove"].includes(step.exercise.kind)) for (let y = vp.row; y < vp.row + vp.rows; y++) for (let x = vp.col; x < vp.col + vp.cols; x++) {
      if (step.exercise.kind === "puzzle" && answer.board[y][x] || step.exercise.kind === "remove" && !answer.board[y][x]) continue;
      shapes += `<circle class="hit" data-point="${x},${y}" data-testid="point-${x}-${y}" cx="${pos(x)}" cy="${pos(y)}" r="47" fill="transparent" role="button" tabindex="0" aria-label="${"ABCDEFGHJKLMNOPQRST"[x]}${n - y}"/>`;
    }
    return `<svg viewBox="${vp.col * 100} ${vp.row * 100} ${vp.cols * 100} ${vp.rows * 100}" role="img" aria-label="${n}\u8DEFOGS\u7EC3\u4E60\u68CB\u76D8">${shapes}</svg>`;
  }
  function renderExercise() {
    const l = lesson();
    if (!step || !answer) {
      screen.innerHTML = header(`${l.course_code} ${l.title}`) + `<div class="error-state">${escape(stepError || "\u6B63\u5728\u8BFB\u53D6\u771F\u5B9E\u7EC3\u4E60\u2026")}<br><button class="key" id="back" style="margin-top:25px">\u2039 \u8FD4\u56DE\u5C0F\u8282</button>${stepError ? '<button class="key primary" id="retry-load" style="margin-left:15px">\u91CD\u8BD5</button>' : ""}</div>`;
      bind("#back", () => nav("lesson"));
      bind("#retry-load", () => {
        stepError = "";
        renderExercise();
        loadStep();
      });
      if (!stepError) loadStep();
      return;
    }
    const kind = step.exercise.kind, status = answer.status;
    const choices = kind === "choice" ? step.exercise.choices.map((c) => `<button class="key" data-answer="${escape(c.value)}" ${status !== "active" ? "disabled" : ""}>${escape(step.locale.text.choices?.[c.label_key] || c.value)}</button>`).join("") : "";
    const tip = tips[l.id] || "\u56DE\u5230\u9898\u76EE\u7684\u76EE\u6807\uFF0C\u770B\u770B\u521A\u624D\u8FD9\u4E00\u624B\u4E4B\u540E\uFF0C\u5BF9\u624B\u80FD\u600E\u6837\u5E94\u5BF9\u3002\u53EF\u4EE5\u91CD\u770B\u8BB2\u89E3\uFF0C\u518D\u8BD5\u4E00\u6B21\u3002";
    screen.innerHTML = header(`${l.course_code} ${l.title}`) + `<main class="exercise-layout"><section class="board">${boardSvg()}</section><section class="panel exercise-side"><div class="eyebrow">\u52A8\u624B\u7EC3\u4E60 \xB7 ${kind === "choice" ? "\u89C2\u5BDF\u68CB\u76D8\u540E\u4F5C\u7B54" : kind === "remove" ? "\u70B9\u9009\u9700\u8981\u79FB\u8D70\u7684\u68CB\u5757" : "\u76F4\u63A5\u5728\u68CB\u76D8\u4E0A\u843D\u5B50"}</div><h1>${escape(l.title)}</h1><div class="stepno">\u7B2C${stepIndex + 1}\u9898 / ${l.step_count}\u9898</div><div class="instruction">${escape(step.locale.text.instruction)}</div><div class="choices">${choices}</div>${["pass", "finish"].includes(kind) ? `<button class="key primary" id="action">${kind === "pass" ? "\u505C\u4E00\u624B" : "\u786E\u8BA4\u7EC8\u5C40"}</button>` : ""}<div class="feedback ${status}">${status === "correct" ? "\u2713 \u7B54\u5BF9\u4E86\uFF01" : status === "wrong" ? "\u518D\u60F3\u4E00\u60F3\u3002" : kind === "choice" ? "\u5148\u89C2\u5BDF\u68CB\u76D8\uFF0C\u518D\u9009\u62E9\u7B54\u6848\u3002" : `\u8F6E\u5230${answer.player === "B" ? "\u9ED1\u68CB" : "\u767D\u68CB"}\u3002\u8BF7\u9009\u62E9\u843D\u5B50\u70B9\u3002`}${status !== "active" ? `<div style="margin-top:8px;font-size:20px">${escape(tip)}</div>` : ""}</div><div class="exercise-actions"><button class="key small" id="retry">\u91CD\u8BD5\u672C\u9898</button>${clips().length ? '<button class="key small" id="rewatch">\u91CD\u770B\u8BB2\u89E3</button>' : ""}</div><div class="foot"><button class="key flat" id="back">\u2039 \u8FD4\u56DE\u5C0F\u8282</button><button class="key primary" id="next-question" ${status !== "correct" ? "disabled" : ""}>${stepIndex + 1 === l.step_count ? "\u5B8C\u6210\u672C\u8282 \u2192" : "\u4E0B\u4E00\u9898 \u2192"}</button></div><div class="source">\u7EC3\u4E60\u6765\u6E90\uFF1AOGS \xB7 ${escape(l.course_code)} / \u7B2C${stepIndex + 1}\u9898 <button class="key small flat" id="source" style="min-height:30px;font-size:15px;padding:2px 9px">\u6765\u6E90</button></div></section></main>`;
    screen.querySelectorAll("[data-point]").forEach((el) => {
      const play = () => {
        const point = el.dataset.point.split(",").map(Number);
        answer = playOgsPoint(answer, point);
        render();
      };
      el.addEventListener("click", play);
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          play();
        }
      });
    });
    screen.querySelectorAll("[data-answer]").forEach((el) => el.addEventListener("click", () => {
      answer = chooseOgsAnswer(answer, el.dataset.answer);
      render();
    }));
    bind("#retry", () => {
      answer = retryOgsExercise(answer);
      render();
    });
    bind("#rewatch", () => nav("video"));
    bind("#source", sourceDialog);
    bind("#back", () => nav("lesson"));
    bind("#action", () => {
      answer = actOgsExercise(answer, kind);
      render();
    });
    bind("#next-question", () => {
      if (answer.status !== "correct") return;
      if (stepIndex + 1 === l.step_count) nav("lesson");
      else {
        stepIndex += 1;
        step = null;
        answer = null;
        nav("exercise");
      }
    });
  }
  function sourceDialog() {
    const l = lesson(), list = clips();
    const overlay = document.createElement("div");
    overlay.className = "dialog";
    overlay.innerHTML = `<section class="dialog-inner" role="dialog" aria-modal="true" aria-label="\u8BFE\u7A0B\u6765\u6E90"><button class="key small close">\u5173\u95ED</button><h2>\u8BFE\u7A0B\u6765\u6E90</h2><p><strong>\u89C6\u9891\u8BB2\u89E3</strong><br>${list.length ? list.map((c) => `${escape(c.book)} \xB7 PDF\u7B2C${c.page}\u9875<br>\u300A${escape(c.title)}\u300B`).join("<br>") : "\u672C\u8282\u5C1A\u672A\u914D\u7F6E\u89C6\u9891\u8BB2\u89E3\u3002"}</p><p><strong>\u4E92\u52A8\u7EC3\u4E60</strong><br>OGS\u56F4\u68CB\u5165\u95E8\u6559\u7A0B \xB7 ${escape(l.course_code)} ${escape(l.title)}<br><a href="https://online-go.com/learn-to-play-go/${encodeURIComponent(l.route)}" target="_blank" rel="noopener">\u67E5\u770BOGS\u539F\u8BFE\u7A0B \u2197</a></p><p class="tiny">\u4FDD\u7559OGS\u539F\u9898\u3001\u9898\u578B\u4E0E\u5206\u652F\u5224\u5B9A\uFF1B\u68CB\u76D8\u9898\u76F4\u63A5\u843D\u5B50\uFF0C\u6570\u6C14\u7B49\u6587\u5B57\u95EE\u9898\u6309\u539F\u9898\u9009\u62E9\u3002${escape(course.license_notice)}</p></section>`;
    screen.append(overlay);
    overlay.querySelector("button").addEventListener("click", () => overlay.remove());
  }
  function render() {
    if (!course || !manifest) return;
    if (view === "catalog") renderCatalog();
    else if (view === "lesson") renderLesson();
    else if (view === "video") renderVideo();
    else renderExercise();
    history.replaceState(null, "", `#chapter=${chapter}${lessonId ? `&lesson=${encodeURIComponent(lessonId)}&view=${view}` : ""}`);
  }
  function restoreHash() {
    if (!course || !manifest) return;
    fetchRevision += 1;
    step = null;
    answer = null;
    stepError = "";
    stepIndex = 0;
    clipIndex = 0;
    const params = new URLSearchParams(location.hash.slice(1));
    chapter = Number(params.get("chapter")) || 2;
    if (!course.chapters.some((c) => c.number === chapter)) chapter = 2;
    lessonId = "";
    view = "catalog";
    const l = params.get("lesson");
    if (l && course.lessons.some((x) => x.id === l)) {
      lessonId = l;
      const wanted = params.get("view");
      view = ["lesson", "video", "exercise"].includes(wanted || "") ? wanted : "lesson";
    }
    render();
  }
  addEventListener("hashchange", restoreHash);
  Promise.all([fetch("course.json").then((r) => r.json()), fetch("manifest.json").then((r) => r.json())]).then(([c, m]) => {
    course = c;
    manifest = m;
    restoreHash();
    scale();
  }).catch(() => {
    screen.innerHTML = '<div class="error-state">\u9884\u89C8\u6750\u6599\u5C1A\u672A\u51C6\u5907\u597D\u3002<br>\u8BF7\u5148\u8FD0\u884C prepare.py\u3002</div>';
  });
})();
