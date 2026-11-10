(function () {
  const data = window.KioskOGSFixture;
  if (!data) return;
  const family = window.KioskDesignFamilies = window.KioskDesignFamilies || {};
  let chapterIndex = 0;
  let lessonId = 'rules-intro';
  let stepIndex = 0;
  let choiceStepIndex = 0;
  let answer = null;
  let physicalMode = false;
  const icon = kind => {
    const paths = {
      back: '<path d="m15 4-8 8 8 8M7 12h15"/>',
      next: '<path d="m9 4 8 8-8 8"/>',
      check: '<path d="m4 12 5 5L20 6"/>',
      book: '<path d="M12 6c-3-3-6-3-10-2v15c4-1 7-1 10 2 3-3 6-3 10-2V4c-4-1-7-1-10 2ZM12 6v15"/>',
      physical: '<path d="M3 8h18v10H3zM7 18l-2 3m12-3 2 3M7 11h10M7 15h10M10 8v10m4-10v10"/><circle cx="19" cy="4" r="2"/>',
    };
    return `<svg class="ogs-inline-icon" viewBox="0 0 24 24" aria-hidden="true">${paths[kind] || paths.book}</svg>`;
  };
  const esc = value => String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
  const chapter = () => data.chapters[chapterIndex];
  const lesson = () => data.lessons.find(item => item.id === lessonId) || data.lessons[0];
  const steps = () => data.steps[lessonId] || [];
  const refresh = () => window.KioskTrainingRefresh?.();
  const resetAnswer = () => { answer = null; };

  function home() {
    const chapterCards = data.chapters.map((item, index) => `<button type="button" class="ogs-chapter" data-ogs-chapter="${index}" data-switch="books"><span class="ogs-chapter-no">${String(item.number).padStart(2, '0')}</span><span class="ogs-chapter-copy"><strong>${esc(item.title)}</strong><em>${item.lesson_count} 课 · ${item.step_count} 步</em></span>${icon('next')}</button>`).join('');
    return `<div class="u-ogs ogs-home"><section class="ogs-card ogs-hero"><span class="ogs-kicker">边学边下 · 互动教程</span><h1>围棋入门</h1><h2>OGS 围棋入门与基础练习</h2><p>从第一手落子开始，逐章掌握规则与基本技巧。</p><div class="ogs-metrics"><span><strong>7</strong>章节</span><span><strong>248</strong>课目</span><span><strong>3,551</strong>练习步骤</span></div><button type="button" class="ogs-key ogs-key-primary" data-ogs-chapter="0" data-switch="books">开始第一章 ${icon('next')}</button></section><main class="ogs-home-right"><div class="ogs-section-head"><h2>课程目录</h2><span>选一章开始</span></div><div class="ogs-chapter-grid">${chapterCards}</div></main></div>`;
  }

  function lessons() {
    const ch = chapter();
    const list = data.lessons.filter(item => item.chapter_id === ch.id);
    const tabs = data.chapters.map((item, index) => `<button type="button" class="ogs-chapter-tab ${index === chapterIndex ? 'is-current' : ''}" data-ogs-chapter-tab="${index}" aria-current="${index === chapterIndex ? 'true' : 'false'}"><strong>${String(item.number).padStart(2, '0')}</strong>${esc(item.title)}</button>`).join('');
    const lessonCards = list.map(item => `<button type="button" class="ogs-lesson" data-ogs-lesson="${esc(item.id)}" data-switch="${item.id === 'count-liberties' ? 'books-chapter-open' : 'section'}"><span class="ogs-lesson-number">${String(item.code.split('.').at(-1)).padStart(2, '0')}</span><span class="ogs-lesson-copy"><strong>${esc(item.title)}</strong><span>${esc(item.subtext || `${item.step_count} 步互动练习`)}</span></span>${icon('next')}</button>`).join('');
    return `<div class="u-ogs ogs-lesson-layout"><aside class="ogs-card ogs-chapter-rail"><div class="ogs-rail-head">七章学习路径</div><div class="ogs-chapter-tabs">${tabs}</div></aside><main class="ogs-lesson-main"><div class="ogs-lesson-head"><button type="button" class="ogs-key" data-switch="courses">${icon('back')}课程</button><h2>${esc(ch.title)}</h2><span class="ogs-meta">第 ${ch.number} 章 / 共 7 章</span></div><div class="ogs-lesson-sub"><span>按顺序学习，也可以点选任意课目</span><span>${ch.lesson_count} 课 · ${ch.step_count} 步</span></div><div class="ogs-lesson-list">${lessonCards}</div></main></div>`;
  }

  function boardSvg(step, currentAnswer) {
    const size = step.size || 9;
    const o = 60, gap = 380 / (size - 1);
    const lines = Array.from({ length: size }, (_, index) => `<path d="M${o} ${o + index * gap}H${o + 380} M${o + index * gap} ${o}V${o + 380}"/>`).join('');
    const starsAt = size === 9 ? [2, 4, 6] : size === 13 ? [3, 6, 9] : [3, 9, 15];
    const stars = starsAt.flatMap(x => starsAt.map(y => `<circle cx="${o + x * gap}" cy="${o + y * gap}" r="3" fill="#4c321a"/>`)).join('');
    const labels = Array.from({ length: size }, (_, i) => `<text x="${o + i * gap}" y="34" text-anchor="middle">${'ABCDEFGHJKLMNOPQRST'[i]}</text><text x="${o + i * gap}" y="478" text-anchor="middle">${'ABCDEFGHJKLMNOPQRST'[i]}</text><text x="27" y="${o + i * gap + 5}" text-anchor="middle">${size - i}</text><text x="473" y="${o + i * gap + 5}" text-anchor="middle">${size - i}</text>`).join('');
    const initial = ['B', 'W'].flatMap(color => (step.stones?.[color] || []).map(([x, y]) => `<circle cx="${o + x * gap}" cy="${o + y * gap}" r="${Math.min(17, gap * .37)}" fill="url(#ogs-${color})" stroke="${color === 'B' ? '#111718' : '#d5d8d0'}" stroke-width="1.7"/>`)).join('');
    const placed = currentAnswer?.point ? `<circle cx="${o + currentAnswer.point[0] * gap}" cy="${o + currentAnswer.point[1] * gap}" r="${Math.min(17, gap * .37)}" fill="url(#ogs-${step.player})" stroke="${step.player === 'B' ? '#111718' : '#d5d8d0'}" stroke-width="1.7"/>` : '';
    const occupied = new Set([...step.stones.B, ...step.stones.W].map(([x, y]) => `${x},${y}`));
    const hit = step.kind === 'puzzle' && !currentAnswer?.correct ? Array.from({ length: size * size }, (_, index) => {
      const x = index % size, y = Math.floor(index / size);
      return occupied.has(`${x},${y}`) ? '' : `<circle class="ogs-hit" cx="${o + x * gap}" cy="${o + y * gap}" r="${Math.min(21, gap * .44)}" data-ogs-point="${x},${y}" aria-label="在 ${x + 1} 列 ${y + 1} 行落子"/>`;
    }).join('') : '';
    return `<svg viewBox="0 0 500 500" role="img" aria-label="${size} 路互动棋盘"><defs><linearGradient id="ogs-wood" x2=".9" y2="1"><stop stop-color="#e8bd77"/><stop offset=".48" stop-color="#e6b66d"/><stop offset="1" stop-color="#c98f4b"/></linearGradient><radialGradient id="ogs-B" cx=".32" cy=".22" r=".82"><stop stop-color="#555a58"/><stop offset=".64" stop-color="#202524"/><stop offset="1" stop-color="#060808"/></radialGradient><radialGradient id="ogs-W" cx=".32" cy=".22" r=".82"><stop stop-color="#fff"/><stop offset=".7" stop-color="#eff2eb"/><stop offset="1" stop-color="#bdc3b9"/></radialGradient></defs><rect width="500" height="500" rx="10" fill="#6c4525"/><rect x="18" y="18" width="464" height="464" rx="5" fill="url(#ogs-wood)"/><path d="M23 23H477V477H23Z" stroke="#f8d28c" stroke-width="2" fill="none" opacity=".7"/><g stroke="#674825" stroke-width="1.25">${lines}</g>${stars}<g fill="#f2d09c" font-family="Kiosk Plex Mono,monospace" font-size="16">${labels}</g>${initial}${placed}${hit}</svg>`;
  }

  function exercise(forceChoice = false) {
    const item = forceChoice ? data.lessons.find(x => x.id === 'count-liberties') : lesson();
    const stepList = forceChoice ? data.steps['count-liberties'] : steps();
    const index = Math.min(forceChoice ? choiceStepIndex : stepIndex, stepList.length - 1);
    const step = stepList[index];
    if (!step) return lessons();
    const currentAnswer = answer?.lessonId === item.id ? answer : null;
    const count = item.step_count;
    const chapterInfo = data.chapters.find(x => x.id === item.chapter_id);
    const isChoice = step.kind === 'choice';
    const physicalAvailable = step.size === 19 && step.kind === 'puzzle';
    const physicalHint = step.size !== 19 ? '实体盘当前支持 19 路练习' : physicalAvailable ? physicalMode ? '实机将先检查摄像头与标定，再引导清盘、摆题' : '也可以在实体盘上练习' : '本步骤请在屏幕完成';
    const status = currentAnswer?.correct ? ['回答正确',index + 1 >= count ? '这一课已完成。' : '继续进入下一步。','is-success'] : currentAnswer ? ['再试一次',isChoice ? '再数一数这块棋的气。' : '仔细看棋盘上的交叉点。','is-error'] : physicalMode && physicalAvailable ? ['准备实体盘','请清空棋盘，再按设备提示摆出题面。',''] : isChoice ? ['选出答案','点按下方的数字。',''] : ['轮到你落子',step.player === 'B' ? '黑棋先行 · 点按棋盘交叉点。' : '白棋行棋 · 点按棋盘交叉点。',''];
    const interaction = isChoice ? `<div class="ogs-choice-row">${step.choices.map(choice => `<button type="button" class="ogs-key ${currentAnswer?.value === choice.value ? 'is-picked' : ''}" data-ogs-choice="${esc(choice.value)}">${esc(choice.label)}</button>`).join('')}</div>` : '';
    const progress = Array.from({ length: Math.min(count, 20) }, (_, i) => `<i class="${i === index ? 'is-current' : ''}"></i>`).join('');
    const backTo = 'books';
    return `<div class="u-ogs ogs-exercise"><div class="ogs-board-wrap">${boardSvg(step, currentAnswer)}</div><main class="ogs-exercise-rail"><div class="ogs-exercise-title"><button type="button" class="ogs-key" data-switch="${backTo}">${icon('back')}课目</button><h2>${esc(item.title)}</h2></div><div class="ogs-breadcrumb"><span>第 ${chapterInfo.number} 章 · 第 ${esc(item.code.split('.').at(-1))} 课</span><span>第 ${index + 1} / ${count} 步</span></div><div class="ogs-progress">${progress}</div><section class="ogs-card ogs-instruction"><span class="ogs-instruction-label">这一题</span><p>${esc(step.instruction)}</p></section><section class="ogs-card ogs-interaction ${status[2]}"><strong>${status[0]}</strong><span>${status[1]}</span>${interaction}</section><div class="ogs-physical-hint">${esc(physicalHint)}</div><div class="ogs-exercise-actions"><button type="button" class="ogs-key" data-ogs-prev ${index === 0 ? 'disabled' : ''}>${icon('back')}上一步</button><button type="button" class="ogs-key ${physicalMode && physicalAvailable ? 'is-physical' : ''}" data-ogs-physical aria-pressed="${physicalMode && physicalAvailable}" ${physicalAvailable ? '' : 'disabled'}>${icon('physical')}实体盘</button><button type="button" class="ogs-key ogs-key-primary" data-ogs-next ${currentAnswer?.correct ? '' : 'disabled'}>${index + 1 >= count ? '完成本课' : '下一步'}${icon('next')}</button></div></main></div>`;
  }

  Object.assign(family, {
    courses: () => home(),
    books: () => lessons(),
    section: () => exercise(false),
    'books-chapter-open': () => exercise(true),
  });

  document.addEventListener('click', event => {
    const ch = event.target.closest('#stage [data-ogs-chapter]');
    if (ch) { chapterIndex = Number(ch.dataset.ogsChapter); lessonId = data.lessons.find(x => x.chapter_id === chapter().id)?.id || 'rules-intro'; stepIndex = 0; physicalMode = false; resetAnswer(); return; }
    const lessonButton = event.target.closest('#stage [data-ogs-lesson]');
    if (lessonButton) { lessonId = lessonButton.dataset.ogsLesson; stepIndex = 0; choiceStepIndex = 0; physicalMode = false; resetAnswer(); return; }
    if (event.target.closest('.chooser button[data-id="books-chapter-open"]')) { choiceStepIndex = 0; resetAnswer(); return; }
  }, true);

  document.addEventListener('click', event => {
    const chapterTab = event.target.closest('#stage [data-ogs-chapter-tab]');
    if (chapterTab) { chapterIndex = Number(chapterTab.dataset.ogsChapterTab); lessonId = data.lessons.find(x => x.chapter_id === chapter().id)?.id || 'rules-intro'; stepIndex = 0; physicalMode = false; resetAnswer(); refresh(); return; }
    if (event.target.closest('#stage [data-ogs-physical]')) { physicalMode = !physicalMode; refresh(); return; }
    const point = event.target.closest('#stage [data-ogs-point]');
    if (point) {
      const current = steps()[stepIndex];
      const picked = point.dataset.ogsPoint.split(',').map(Number);
      answer = { lessonId, point: picked, correct: current.correct_points.some(p => p[0] === picked[0] && p[1] === picked[1]) };
      refresh(); return;
    }
    const choice = event.target.closest('#stage [data-ogs-choice]');
    if (choice) { answer = { lessonId: 'count-liberties', value: choice.dataset.ogsChoice, correct: choice.dataset.ogsChoice === data.steps['count-liberties'][choiceStepIndex].correct_choice }; refresh(); return; }
    if (event.target.closest('#stage [data-ogs-prev]')) { if (location.hash === '#books-chapter-open') choiceStepIndex = Math.max(0, choiceStepIndex - 1); else stepIndex = Math.max(0, stepIndex - 1); physicalMode = false; resetAnswer(); refresh(); return; }
    if (event.target.closest('#stage [data-ogs-next]')) {
      if (!answer?.correct) return;
      if (location.hash === '#books-chapter-open' && choiceStepIndex + 1 < data.steps['count-liberties'].length) { choiceStepIndex += 1; physicalMode = false; resetAnswer(); refresh(); }
      else if (location.hash !== '#books-chapter-open' && lessonId === 'rules-intro' && stepIndex + 1 < steps().length) { stepIndex += 1; physicalMode = false; resetAnswer(); refresh(); }
      else { document.querySelector('.chooser button[data-id="books"]')?.click(); }
    }
  });
})();
