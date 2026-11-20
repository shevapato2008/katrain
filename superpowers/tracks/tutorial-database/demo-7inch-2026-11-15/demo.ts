import { createOgsExercise, playOgsPoint, chooseOgsAnswer, actOgsExercise, retryOgsExercise } from '../../../../katrain/web/ui/src/kiosk/tutorial/ogsExercise';

const screen = document.querySelector('#screen') as HTMLElement;
const stage = document.querySelector('#stage') as HTMLElement;
const escape = (s: any) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
let course: any, manifest: any, chapter = 2, lessonId = '', view = 'catalog', clipIndex = 0, stepIndex = 0;
let step: any = null, answer: any = null, stepError = '', mode = 'fit', offline = false, fetchRevision = 0;
const tips: Record<string, string> = {
  'count-liberties': '气是棋块上下左右紧邻的空交叉点。先认同一块棋，再数气；共用的空点只算一次。',
  'count_chains': '同色棋子沿上下左右相连，才属于同一块棋；斜着靠近不算连接。',
  'in_atari': '整块棋只剩最后一口气，就处于被打吃的状态。要数整块棋，不能只看其中一颗。',
  'capture_stone': '先找到对方棋子的最后一口气，落在那个交叉点上，没气的对方棋子就会被提走。',
  'capture_chain': '相连的棋子共享气；最后一口气被堵住时，要把整块没气的棋取走。',
  'escape': '先找目标棋块的最后一口气，再看走出去以后能否获得新的气。',
  'find_escape': '救棋不能只看眼前一步。比较不同出路，看看对手继续打吃后，棋块还能不能跑。',
  'create_opening': '想一想对手的应手，再比较出路。可以重看讲解里的变化。',
  'ladder': '顺着打吃、逃跑的次序往前读；每一步都检查气，直到能够判断这条路的结果。',
};

function scale() {
  const full = !!document.fullscreenElement;
  const s = mode === 'actual' && !full ? 1 : Math.min(full ? 5 : 1.2, (innerWidth - (full ? 0 : 64)) / 1024, (innerHeight - (full ? 0 : 170)) / 600);
  stage.style.width = `${1024 * s}px`; stage.style.height = `${600 * s}px`;
  screen.style.transform = `scale(${s})`; document.body.classList.toggle('fullscreen', full);
}
addEventListener('resize', scale); document.addEventListener('fullscreenchange', scale);
document.querySelector('#fit')!.addEventListener('click', () => { mode = 'fit'; scale(); });
document.querySelector('#actual')!.addEventListener('click', () => { mode = 'actual'; scale(); });
document.querySelector('#fullscreen')!.addEventListener('click', () => { if (document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen(); });
document.querySelector('#offline')!.addEventListener('click', () => {
  offline = !offline; const button = document.querySelector('#offline')!;
  button.textContent = `本地备用：${offline ? '开' : '关'}`; button.classList.toggle('on', offline);
  if (view === 'video') render();
});

function lesson() { return course.lessons.find((l: any) => l.id === lessonId); }
function clips() { return (manifest.playlists[lessonId] || []).map((id: number) => manifest.clips.find((c: any) => c.id === id)); }
function clip() { return clips()[clipIndex] || null; }
function header(text: string, back = false) { return `<header class="topbar">${back ? '<button class="key small flat" id="back">‹ 返回</button>' : ''}<div class="brand">智星盒</div><div class="crumb">${escape(text)}</div><span class="tag">先学讲解 · 再做练习</span></header>`; }
function nav(next: string, lid?: string) {
  screen.querySelector('video')?.pause();
  if (lid && lid !== lessonId) { lessonId = lid; clipIndex = 0; stepIndex = 0; step = null; answer = null; }
  view = next; render();
}
function bind(id: string, fn: () => void) { screen.querySelector(id)?.addEventListener('click', fn); }

function renderCatalog() {
  const c = course.chapters.find((c: any) => c.number === chapter);
  const lessons = course.lessons.filter((l: any) => l.chapter_id === c.id);
  const videoCount = lessons.filter((l: any) => manifest.playlists[l.id]?.length).length;
  screen.innerHTML = header('围棋教程') + `<main class="course-layout"><aside class="rail"><div class="eyebrow">从认识棋盘，到亲手落子</div><h1>入门课程</h1>${course.chapters.map((c: any) => `<button class="tab ${chapter === c.number ? 'current' : ''}" data-chapter="${c.number}"><span class="num">0${c.number}</span>${escape(c.title)}</button>`).join('')}<p class="quiet">选一个小节，<br>先看棋盘上的讲解，<br>再亲手完成练习。</p><div class="rail-bottom">讲解图：围棋教室<br>互动练习：OGS原题</div></aside><section class="course-main"><div class="section-head"><h2>${escape(c.title)}</h2><span class="count">${lessons.length}小节 · ${videoCount}节配有视频</span></div><div class="section-sub">循序渐进，一次学懂一个小主题。</div><div class="lesson-list">${lessons.map((l: any) => {
    const n = manifest.playlists[l.id]?.length || 0;
    return `<button class="lesson" data-lesson="${escape(l.id)}"><span class="lesson-number">${escape(l.course_code)}</span><span class="copy"><strong>${escape(l.title)}</strong><span class="meta ${n ? 'ready' : ''}">${n ? `${n}段讲解 · ` : '视频待补 · '}${l.step_count}道练习</span></span><span class="chevron">›</span></button>`;
  }).join('')}</div></section></main>`;
  screen.querySelectorAll('[data-chapter]').forEach(el => el.addEventListener('click', () => { chapter = Number((el as HTMLElement).dataset.chapter); render(); }));
  screen.querySelectorAll('[data-lesson]').forEach(el => el.addEventListener('click', () => nav('lesson', (el as HTMLElement).dataset.lesson)));
}

function renderLesson() {
  const l = lesson(), c = clip(), list = clips();
  screen.innerHTML = header(`${l.course_code} ${l.title}`, true) + `<main class="lesson-layout"><section class="panel lesson-preview">${c ? `<button class="cover" id="watch-cover" aria-label="播放${escape(c.title)}"><img src="posters/${c.id}.jpg" alt="${escape(c.title)}的视频画面"><span class="play-bubble">▶</span></button>` : '<div class="cover no-video"><div class="quiet-copy">这节的互动练习已就绪<br>视频讲解待补充</div></div>'}<div class="playlist">${list.length ? list.map((c: any, i: number) => `<button class="key small ${i === clipIndex ? 'primary' : ''}" data-clip="${i}">${i + 1}. ${escape(c.title)}</button>`).join('') : '<span class="section-sub">可以直接开始本节OGS练习。</span>'}</div></section><section class="panel details"><div class="eyebrow">第${chapter}章 · ${escape(l.course_code)}</div><h1>${escape(l.title)}</h1><p class="learning-tip">${escape(tips[l.id] || l.subtext || '先看懂棋盘上的变化，再用练习检验自己的理解。')}</p><p class="lesson-meta">${list.length ? `${list.length}段讲解 · ` : ''}${l.step_count}道练习</p><div class="credit">${c ? `曹薰铉·李昌镐《围棋教室》<br>入门篇·${c.catalog_id === 'intro-up' ? '上' : '下'}卷 / PDF第${c.page}页` : '练习取自OGS围棋入门教程'}<br><button class="key small flat" id="source">查看来源</button></div><div class="actions">${c ? '<button class="key primary" id="watch">▶ 开始讲解</button>' : ''}<button class="key ${c ? '' : 'primary'}" id="practice">动手练习 →</button></div></section></main>`;
  bind('#watch', () => nav('video')); bind('#watch-cover', () => nav('video')); bind('#practice', startPractice); bind('#back', () => nav('catalog')); bind('#source', sourceDialog);
  screen.querySelectorAll('[data-clip]').forEach(el => el.addEventListener('click', () => { clipIndex = Number((el as HTMLElement).dataset.clip); nav('video'); }));
}

function renderVideo() {
  const c = clip(); if (!c) { nav('lesson'); return; }
  const more = clipIndex + 1 < clips().length;
  screen.innerHTML = `<section class="video-view"><video id="player" src="${offline ? `media-cache/${c.id}.mp4` : `stream/${c.id}.mp4`}" controls playsinline preload="metadata" poster="posters/${c.id}.jpg" aria-label="${escape(c.title)}"></video><div class="video-top"><button class="key small" id="back">‹ 返回</button><span class="video-name">${clipIndex + 1}/${clips().length} · ${escape(c.title)}</span><button class="key small primary next" id="next-video">${more ? '下一段讲解 ›' : '动手练习 →'}</button></div></section>`;
  const player = screen.querySelector('video')!;
  player.addEventListener('play', () => screen.querySelector('.video-view')?.classList.add('playing'));
  player.addEventListener('pause', () => screen.querySelector('.video-view')?.classList.remove('playing'));
  player.addEventListener('ended', () => { screen.querySelector('.video-view')?.classList.remove('playing'); screen.querySelector('#next-video')?.classList.add('primary'); });
  player.addEventListener('error', () => {
    const overlay = document.createElement('div'); overlay.className = 'video-error';
    overlay.innerHTML = `视频暂时无法加载<br><button class="key primary" id="fallback" style="margin-top:12px">${offline ? '重试播放' : '使用本地演示备用'}</button>`;
    screen.querySelector('.video-view')!.append(overlay); bind('#fallback', () => { offline = true; const b = document.querySelector('#offline')!; b.textContent = '本地备用：开'; b.classList.add('on'); renderVideo(); });
  });
  bind('#back', () => nav('lesson'));
  bind('#next-video', () => { if (more) { clipIndex += 1; nav('video'); } else startPractice(); });
  player.play().catch(() => { /* The native play button remains available. */ });
}

function startPractice() { step = null; answer = null; stepIndex = 0; nav('exercise'); }
async function loadStep() {
  const revision = ++fetchRevision, l = lesson(); stepError = '';
  try {
    const response = await fetch(`/api/steps/${l.first_page + stepIndex}`, { signal: AbortSignal.timeout(15000) });
    if (!response.ok) throw Error('unavailable');
    const data = await response.json();
    if (revision !== fetchRevision || view !== 'exercise') return;
    if (data.lesson_id !== lessonId || data.page !== l.first_page + stepIndex) throw Error('wrong identity');
    step = data; answer = createOgsExercise(data); render();
  } catch {
    if (revision === fetchRevision && view === 'exercise') { stepError = '练习暂时无法读取，请联网后重试。'; render(); }
  }
}

function boardSvg() {
  const n = step.size, vp = step.viewport || { col: 0, row: 0, cols: n, rows: n };
  const pos = (x: number) => 50 + x * 100;
  let shapes = `<defs><radialGradient id="black"><stop stop-color="#626560" offset="0"/><stop stop-color="#151815" offset=".4"/><stop stop-color="#020403" offset="1"/></radialGradient><radialGradient id="white"><stop stop-color="#fffef5"/><stop stop-color="#dedfd6" offset=".8"/><stop stop-color="#a5ada5" offset="1"/></radialGradient><linearGradient id="wood" x2="1" y2="1"><stop stop-color="#e9cb92"/><stop stop-color="#caa66f" offset="1"/></linearGradient></defs><rect width="${n * 100}" height="${n * 100}" fill="url(#wood)"/>`;
  for (let i = 0; i < n; i++) shapes += `<path d="M50 ${pos(i)}H${pos(n - 1)}M${pos(i)} 50V${pos(n - 1)}" stroke="#665027" stroke-width="2.5"/>`;
  const stars = n === 9 ? [2, 6] : n === 13 ? [3, 9] : [3, 9, 15];
  for (const x of stars) for (const y of stars) shapes += `<circle cx="${pos(x)}" cy="${pos(y)}" r="6" fill="#665027"/>`;
  const selected = new Set(answer.selectedRemoval.map((p: number[]) => p.join(',')));
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    if (answer.board[y][x]) {
      const stone = answer.board[y][x] === 'B' ? 'black.png' : `white-${String((x * 3 + y * 7) % 32).padStart(2, '0')}.png`;
      shapes += `<circle cx="${pos(x) + 4}" cy="${pos(y) + 6}" r="40" fill="#0004"/><image href="assets/stones/${stone}" x="${pos(x) - 42}" y="${pos(y) - 42}" width="84" height="84"/>${selected.has(`${x},${y}`) ? `<circle cx="${pos(x)}" cy="${pos(y)}" r="33" fill="none" stroke="#65c084" stroke-width="7"/>` : ''}`;
    }
  }
  for (const [point, label] of Object.entries(step.letters || {})) { const [x, y] = point.split(',').map(Number); shapes += `<text x="${pos(x)}" y="${pos(y) + 16}" font-size="50" fill="#18241b" stroke="#ead59c" stroke-width="6" paint-order="stroke" text-anchor="middle">${escape(label)}</text>`; }
  for (const [point, shape] of Object.entries(step.shapes || {})) { const [x, y] = point.split(',').map(Number); const label = ({ triangle: '△', square: '□', circle: '○', cross: '×' } as any)[shape as string] || shape; shapes += `<text x="${pos(x)}" y="${pos(y) + 15}" font-size="45" fill="#8b3f23" text-anchor="middle">${escape(label)}</text>`; }
  if (answer.status === 'active' && ['puzzle', 'remove'].includes(step.exercise.kind)) for (let y = vp.row; y < vp.row + vp.rows; y++) for (let x = vp.col; x < vp.col + vp.cols; x++) {
    if ((step.exercise.kind === 'puzzle' && answer.board[y][x]) || (step.exercise.kind === 'remove' && !answer.board[y][x])) continue;
    shapes += `<circle class="hit" data-point="${x},${y}" data-testid="point-${x}-${y}" cx="${pos(x)}" cy="${pos(y)}" r="47" fill="transparent" role="button" tabindex="0" aria-label="${'ABCDEFGHJKLMNOPQRST'[x]}${n - y}"/>`;
  }
  return `<svg viewBox="${vp.col * 100} ${vp.row * 100} ${vp.cols * 100} ${vp.rows * 100}" role="img" aria-label="${n}路OGS练习棋盘">${shapes}</svg>`;
}

function renderExercise() {
  const l = lesson();
  if (!step || !answer) {
    screen.innerHTML = header(`${l.course_code} ${l.title}`) + `<div class="error-state">${escape(stepError || '正在读取真实练习…')}<br><button class="key" id="back" style="margin-top:25px">‹ 返回小节</button>${stepError ? '<button class="key primary" id="retry-load" style="margin-left:15px">重试</button>' : ''}</div>`;
    bind('#back', () => nav('lesson')); bind('#retry-load', () => { stepError = ''; renderExercise(); loadStep(); });
    if (!stepError) loadStep(); return;
  }
  const kind = step.exercise.kind, status = answer.status;
  const choices = kind === 'choice' ? step.exercise.choices.map((c: any) => `<button class="key" data-answer="${escape(c.value)}" ${status !== 'active' ? 'disabled' : ''}>${escape(step.locale.text.choices?.[c.label_key] || c.value)}</button>`).join('') : '';
  const tip = tips[l.id] || '回到题目的目标，看看刚才这一手之后，对手能怎样应对。可以重看讲解，再试一次。';
  screen.innerHTML = header(`${l.course_code} ${l.title}`) + `<main class="exercise-layout"><section class="board">${boardSvg()}</section><section class="panel exercise-side"><div class="eyebrow">动手练习 · ${kind === 'choice' ? '观察棋盘后作答' : kind === 'remove' ? '点选需要移走的棋块' : '直接在棋盘上落子'}</div><h1>${escape(l.title)}</h1><div class="stepno">第${stepIndex + 1}题 / ${l.step_count}题</div><div class="instruction">${escape(step.locale.text.instruction)}</div><div class="choices">${choices}</div>${['pass', 'finish'].includes(kind) ? `<button class="key primary" id="action">${kind === 'pass' ? '停一手' : '确认终局'}</button>` : ''}<div class="feedback ${status}">${status === 'correct' ? '✓ 答对了！' : status === 'wrong' ? '再想一想。' : kind === 'choice' ? '先观察棋盘，再选择答案。' : `轮到${answer.player === 'B' ? '黑棋' : '白棋'}。请选择落子点。`}${status !== 'active' ? `<div style="margin-top:8px;font-size:20px">${escape(tip)}</div>` : ''}</div><div class="exercise-actions"><button class="key small" id="retry">重试本题</button>${clips().length ? '<button class="key small" id="rewatch">重看讲解</button>' : ''}</div><div class="foot"><button class="key flat" id="back">‹ 返回小节</button><button class="key primary" id="next-question" ${status !== 'correct' ? 'disabled' : ''}>${stepIndex + 1 === l.step_count ? '完成本节 →' : '下一题 →'}</button></div><div class="source">练习来源：OGS · ${escape(l.course_code)} / 第${stepIndex + 1}题 <button class="key small flat" id="source" style="min-height:30px;font-size:15px;padding:2px 9px">来源</button></div></section></main>`;
  screen.querySelectorAll('[data-point]').forEach(el => {
    const play = () => { const point = (el as HTMLElement).dataset.point!.split(',').map(Number) as [number, number]; answer = playOgsPoint(answer, point); render(); };
    el.addEventListener('click', play); el.addEventListener('keydown', (e: any) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); play(); } });
  });
  screen.querySelectorAll('[data-answer]').forEach(el => el.addEventListener('click', () => { answer = chooseOgsAnswer(answer, (el as HTMLElement).dataset.answer!); render(); }));
  bind('#retry', () => { answer = retryOgsExercise(answer); render(); }); bind('#rewatch', () => nav('video')); bind('#source', sourceDialog); bind('#back', () => nav('lesson'));
  bind('#action', () => { answer = actOgsExercise(answer, kind); render(); });
  bind('#next-question', () => { if (answer.status !== 'correct') return; if (stepIndex + 1 === l.step_count) nav('lesson'); else { stepIndex += 1; step = null; answer = null; nav('exercise'); } });
}

function sourceDialog() {
  const l = lesson(), list = clips();
  const overlay = document.createElement('div'); overlay.className = 'dialog';
  overlay.innerHTML = `<section class="dialog-inner" role="dialog" aria-modal="true" aria-label="课程来源"><button class="key small close">关闭</button><h2>课程来源</h2><p><strong>视频讲解</strong><br>${list.length ? list.map((c: any) => `${escape(c.book)} · PDF第${c.page}页<br>《${escape(c.title)}》`).join('<br>') : '本节尚未配置视频讲解。'}</p><p><strong>互动练习</strong><br>OGS围棋入门教程 · ${escape(l.course_code)} ${escape(l.title)}<br><a href="https://online-go.com/learn-to-play-go/${encodeURIComponent(l.route)}" target="_blank" rel="noopener">查看OGS原课程 ↗</a></p><p class="tiny">保留OGS原题、题型与分支判定；棋盘题直接落子，数气等文字问题按原题选择。${escape(course.license_notice)}</p></section>`;
  screen.append(overlay); overlay.querySelector('button')!.addEventListener('click', () => overlay.remove());
}

function render() {
  if (!course || !manifest) return;
  if (view === 'catalog') renderCatalog(); else if (view === 'lesson') renderLesson(); else if (view === 'video') renderVideo(); else renderExercise();
  history.replaceState(null, '', `#chapter=${chapter}${lessonId ? `&lesson=${encodeURIComponent(lessonId)}&view=${view}` : ''}`);
}

function restoreHash() {
  if (!course || !manifest) return;
  fetchRevision += 1; step = null; answer = null; stepError = ''; stepIndex = 0; clipIndex = 0;
  const params = new URLSearchParams(location.hash.slice(1)); chapter = Number(params.get('chapter')) || 2;
  if (!course.chapters.some((c: any) => c.number === chapter)) chapter = 2;
  lessonId = ''; view = 'catalog';
  const l = params.get('lesson');
  if (l && course.lessons.some((x: any) => x.id === l)) {
    lessonId = l; const wanted = params.get('view');
    view = ['lesson', 'video', 'exercise'].includes(wanted || '') ? wanted! : 'lesson';
  }
  render();
}
addEventListener('hashchange', restoreHash);

Promise.all([fetch('course.json').then(r => r.json()), fetch('manifest.json').then(r => r.json())]).then(([c, m]) => {
  course = c; manifest = m;
  restoreHash(); scale();
}).catch(() => { screen.innerHTML = '<div class="error-state">预览材料尚未准备好。<br>请先运行 prepare.py。</div>'; });
