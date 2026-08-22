/* ───────────────────── 教程 · 变化图（内部制作工具） ───────────────────── */
const FIG_STONES = [[3, 15, 'B'], [2, 14, 'W'], [4, 14, 'B'], [3, 13, 'W'], [5, 15, 'B'], [2, 16, 'W'],
  [4, 16, 'B'], [1, 15, 'W'], [5, 13, 'B'], [3, 12, 'W'], [6, 14, 'B'], [2, 12, 'W']];

const figToolBtn = (label, ic, on, act) => `<button class="tbtn" role="button" aria-pressed="${!!on}"
  data-toggle="fig-${label}" data-act="${esc(act)}" data-src="BoardEditToolbar.tsx"
  style="flex-direction:column;gap:2px;min-width:38px;height:44px;padding:4px 6px;font-size:.62rem">
  ${icon(ic, 'sm')}${esc(label)}</button>`;

SCREENS.push({
  id: 'tutorial-figure', group: '教程', label: '教程 · 变化图（制作工具）', route: '/galaxy/tutorials/section/:sectionId',
  nav: 'tutorials', kind: 'content', noBoardTarget: true,
  branches: [
    { id: 'read', label: 'L1 只读' }, { id: 'edit', label: 'L2 编辑棋盘' },
    { id: 'narration', label: '讲解编辑' }, { id: 'debug', label: '识别调试面板' },
    { id: 'nodata', label: '无棋盘数据' }, { id: 'error', label: '加载失败' },
  ],
  dialogs: {
    shape: `<div class="dlg" style="max-width:220px" data-zone="dialog"><h3>图形</h3>
      <div style="padding:0 8px 12px">
        ${['△ 三角形', '□ 正方形', '○ 圆形', '✕ 叉形'].map((s, i) => `<button class="navitem" ${i === 0 ? 'aria-current="page"' : ''}
          data-act="onShapeChange('${s.split(' ')[1]}') 并关闭菜单" data-src="BoardEditToolbar.tsx:225"><span>${s}</span></button>`).join('')}
      </div><div class="acts">${btn({ label: '关闭', color: 'inherit', act: '点外部 / Esc 也关闭' })}</div></div>`,
  },
  render(b) {
    if (b === 'error') {
      return { html: `<div data-zone="body"><div class="alert error">加载小节失败 ${btn({ label: '重试', size: 'sm', act: 'load()', src: 'TutorialFigurePage.tsx:261' })}</div></div>` };
    }
    const editing = b === 'edit';
    const narration = b === 'narration';
    const debug = b === 'debug';
    const nodata = b === 'nodata';

    const col1 = `<div class="figcol" data-zone="body">
      <p class="sec-label">原书内容</p>
      <div style="width:100%;aspect-ratio:3/4;border-radius:4px;border:1px solid var(--line2);background:linear-gradient(170deg,#f2ede2,#ded6c6);margin-bottom:14px;padding:14px;color:#3a352c;font-size:.68rem;line-height:1.7;overflow:hidden">
        <div style="font-weight:700;margin-bottom:6px">二、角上的空</div>
        <div style="opacity:.75">在角上围空效率最高。图一中黑1占据角地，白2挂角后黑3小飞守角，是最常见的下法之一。角上只需要较少的子数就能围出实空，这是围棋中「金角银边草肚皮」的由来……</div>
        <div style="margin-top:10px;height:96px;border:1px solid #b9ac93;border-radius:3px;background:#dcb468;opacity:.8"></div>
      </div>
      <p class="muted" style="margin:0;font-size:.78rem;line-height:1.7;white-space:pre-wrap">黑1占角，白2挂，黑3小飞守角。这是入门阶段最应当先记住的一个形。</p>
      <p class="dim" style="margin:8px 0 0;font-size:.75rem;font-style:italic">（页面上下文）本页出自第一章第二节，讲角上围空的效率。</p>
    </div>`;

    const col2 = `<div class="figcol" data-zone="board">
      <p class="sec-label">棋盘识别</p>
      ${nodata
        ? `<div style="padding:32px;text-align:center;border:1px dashed var(--line2);border-radius:8px">
             <p class="muted" style="margin:0 0 12px">暂无棋盘数据</p>
             ${btn({ label: '初始化空棋盘', variant: 'outlined', size: 'sm', act: 'handleServerSave(空 payload) → PUT figures/{id}', src: 'TutorialFigurePage.tsx:405' })}
           </div>`
        : `<canvas class="boardcv figboard" data-board='${esc(JSON.stringify({ stones: FIG_STONES, coords: false, numbers: true }))}'></canvas>
           ${editing ? `<div style="display:flex;flex-wrap:wrap;gap:4px;align-items:center;padding:6px 0;margin-top:8px" data-zone="body">
              ${figToolBtn('摆黑', STONE.b, true, "onToolChange('stone') + onStoneModeChange('black')")}
              ${figToolBtn('摆白', STONE.w, false, "onStoneModeChange('white')")}
              ${figToolBtn('交替', STONE.alt, false, "onStoneModeChange('alternate')")}
              ${figToolBtn('编号', glyph('123'), true, 'onNumberingChange(!numbering)')}
              <input class="field" type="number" min="1" value="13" aria-label="下一手编号" data-act="onNextMoveNumberChange" data-src="BoardEditToolbar.tsx" style="width:48px;height:32px;text-align:center;padding:4px">
              <span style="width:1px;height:28px;background:var(--line2);margin:0 4px"></span>
              ${figToolBtn('大写', glyph('A'), false, "onToolChange('letter_upper')")}
              ${figToolBtn('小写', glyph('a'), false, "onToolChange('letter_lower')")}
              ${dlgOpen('shape', '图形', { variant: 'outlined', size: 'sm', src: 'BoardEditToolbar.tsx:225' })}
              <input class="field" value="A" aria-label="下一个字母" data-act="onNextLetterChange" data-src="BoardEditToolbar.tsx" style="width:36px;height:32px;text-align:center;padding:4px">
              ${figToolBtn('橡皮', glyph('✕'), false, "onToolChange('eraser')")}
              <span style="flex:1"></span>
              ${ibtn({ icon: 'Undo', label: '撤销', size: 'sm', act: 'editor.undo()', src: 'BoardEditToolbar.tsx' })}
              ${ibtn({ icon: 'DeleteSweep', label: '一键清空', size: 'sm', act: 'editor.clearAll()（保留 viewport）', src: 'BoardEditToolbar.tsx' })}
              ${btn({ label: '保存', variant: 'contained', size: 'sm', act: 'PUT /api/v1/tutorials/figures/{id}', src: 'BoardEditToolbar.tsx' })}
              ${btn({ label: '取消', variant: 'outlined', size: 'sm', act: 'editor.cancelEdit() → 回滚 payload', src: 'BoardEditToolbar.tsx' })}
            </div>`
          : `<div style="padding:8px 4px 0">
              <label class="flabel">手数: <span class="mono">12</span></label>
              <input class="slider" type="range" min="0" max="12" value="12" aria-label="手数" data-act="setMoveStep(v) → SGFBoard maxMoveStep" data-src="TutorialFigurePage.tsx:354">
            </div>
            <div class="inline" style="gap:8px;margin-top:10px">
              ${btn({ label: '编辑', variant: 'outlined', size: 'sm', icon: 'Edit', act: 'editor.enterEdit()', src: 'TutorialFigurePage.tsx:367' })}
              ${btn({ label: '逻辑检查', variant: 'outlined', size: 'sm', icon: 'Rule', act: '纯前端校验，结果走浏览器原生 alert()', src: 'TutorialFigurePage.tsx:370' })}
              ${btn({ label: '确认审核', variant: 'outlined', size: 'sm', icon: 'CheckCircleOutline', act: 'PUT /api/v1/tutorials/figures/{id}/verify', src: 'TutorialFigurePage.tsx:374' })}
            </div>`}
           ${debug ? `<div class="card" style="margin-top:14px;padding:12px;border-radius:10px">
             <div class="rowbetween" style="margin-bottom:10px"><span class="sec-label" style="margin:0">识别流程</span>
             ${ibtn({ icon: 'ExpandLess', label: '收起调试面板', size: 'sm', act: '折叠 RecognitionDebugPanel', src: 'RecognitionDebugPanel.tsx' })}</div>
             ${['S0 画框检测 · 识别页面中每张棋谱图的位置',
                'S1 纠偏与网格扫描 · 纠偏 + 检测到的网格线',
                'S2 落子检测 · 检测到的落子点标注',
                'S3 棋盘定位 · 确定棋谱在 19×19 棋盘中的区域',
                'S4 编号绑定 · 数字与棋子配对'].map((s, i) => `
               <button class="rowbetween" data-act="展开第 ${i + 1} 步中间图" data-src="RecognitionDebugPanel.tsx" style="width:100%;background:none;border:0;border-top:${i ? '1px solid var(--line)' : '0'};color:inherit;font:inherit;padding:7px 0;cursor:pointer;text-align:left">
                 <span style="font-size:.75rem">${s}</span>
                 <span class="inline" style="gap:6px" aria-label="展开箭头">${icon('ExpandMore', 'sm')}</span></button>`).join('')}
           </div>` : ''}`}
    </div>`;

    const col3 = `<div class="figcol" data-zone="body">
      <div class="rowbetween" style="margin-bottom:10px">
        <p class="sec-label" style="margin:0">语音讲解</p>
        ${btn({ label: narration ? '收起编辑' : '编辑讲解', variant: 'outlined', size: 'sm', icon: 'Edit', act: 'setIsEditingNarration(v => !v)', src: 'TutorialFigurePage.tsx:414' })}
      </div>
      ${narration
        ? `<div class="stack g12">
            <textarea class="field" rows="7" aria-label="讲解文本" data-act="setEditedNarration" data-src="TutorialFigurePage.tsx:428">黑1占角，白2挂角，黑3小飞守角。角上围空的效率最高，这是入门阶段最应当先记住的一个形。</textarea>
            <div class="inline" style="gap:8px">
              ${btn({ label: '保存文字', variant: 'outlined', act: 'PUT figures/{id} narration', src: 'TutorialFigurePage.tsx:438' })}
              ${btn({ label: '生成语音并保存', variant: 'contained', icon: 'RecordVoiceOver', act: 'POST tutorials/tts → 写 audio_asset', src: 'TutorialFigurePage.tsx:445' })}
              ${btn({ label: '取消', color: 'inherit', act: '还原 narration，收起编辑器', src: 'TutorialFigurePage.tsx:454' })}
            </div>
          </div>`
        : `<p class="muted" style="margin:0 0 16px;font-size:.85rem;line-height:1.8;white-space:pre-wrap">黑1占角，白2挂角，黑3小飞守角。角上围空的效率最高，这是入门阶段最应当先记住的一个形。</p>`}
      <div class="card" style="padding:10px 12px;border-radius:10px;margin-top:14px">
        <div class="inline" style="gap:10px">
          ${ibtn({ icon: 'PlayArrow', label: '播放', act: 'audio.play() / audio.pause()', src: 'AudioPlayer.tsx' })}
          <div style="flex:1;height:4px;border-radius:2px;background:rgba(255,255,255,.12);position:relative">
            <div style="width:34%;height:100%;background:var(--jade-l);border-radius:2px"></div></div>
          <span class="mono dim" style="font-size:.72rem">0:12 / 0:35</span>
        </div>
      </div>
      <div style="margin-top:14px">
        <div style="aspect-ratio:16/9;border-radius:8px;background:linear-gradient(150deg,#1c1c1c,#0c0c0c);border:1px solid var(--line2);display:grid;place-items:center">
          <button class="iconbtn" aria-label="播放讲解视频" data-act="&lt;video controls preload=none&gt; 原生播放" data-src="TutorialFigurePage.tsx:487" style="width:52px;height:52px;background:rgba(74,107,92,.85);color:#eef4f0">${icon('PlayArrow')}</button>
        </div>
        <div class="mono dim" style="font-size:.72rem;margin-top:4px">1:24</div>
      </div>
    </div>`;

    return {
      raw: `<div style="padding:16px;height:100%;overflow:auto;display:flex;flex-direction:column" data-zone="body">
        <div style="margin-bottom:8px">${btn({ label: '← 返回', size: 'sm', color: 'inherit', act: 'navigate(-1) → 浏览器历史后退一步', src: 'TutorialFigurePage.tsx:267' })}</div>
        <h1 style="font-size:1.25rem;font-weight:600;margin:0 0 12px">二. 角上的空</h1>
        <div class="inline" style="gap:8px;margin-bottom:16px" data-zone="above-board">
          ${ibtn({ icon: 'NavigateBefore', label: '上一图', disabled: true, act: 'setCurrentFigureIndex(i-1)', src: 'TutorialFigurePage.tsx:275' })}
          <span class="mono" style="font-size:.85rem">图一 (1 / 42)</span>
          ${ibtn({ icon: 'NavigateNext', label: '下一图', act: 'setCurrentFigureIndex(i+1)', src: 'TutorialFigurePage.tsx:281' })}
        </div>
        <div class="figgrid">${col1}${col2}${col3}</div>
      </div>`,
    };
  },
  note: `<h3>这不是玩家用的棋盘页，是内部制作工具</h3>
    <p>三列：<b>原书页图</b> | <b>棋盘 + 编辑工具条</b> | <b>讲解文本 + 音频 + 视频</b>。
    做的事是「编辑落子 / 逻辑检查 / 确认审核 / 生成语音」。审图的人必须让原书页图和识别出的棋盘<b>并排</b>才能核对。</p>
    <p><code>BoardPageShell</code> 只有「棋盘 + 一条右栏」两列，塞不下并排的第三列。
    硬套模板等于把原书页图挪到右栏里、要上下滚动对照 —— 会真的弄坏这个工作流。
    这是我需要你裁定的一处：<b>当内容页只换页头</b>，还是<b>硬套 BoardPageShell</b>，还是<b>本轮先不动</b>。</p>
    <h3>不管走哪条路，这三处承重错误都要修</h3>
    <p><code>maxHeight: calc(100vh - 140px)</code> 在 <code>:290 / :293 / :316 / :415</code> 出现四次。
    140 是一个凭空的魔法数，跟顶栏 52 / 页头实际高度都对不上；三列各自一条滚动条，
    页面本身又不滚。窄视口下三列会各滚各的，标题和翻页行却滚不动。</p>
    <p>另外这页所有反馈都走浏览器原生 <code>alert()</code>（逻辑检查结果、保存失败），
    不是 <code>Snackbar</code>。spec §5.1 说错误要可执行、不泄露运维细节 —— 记录，本轮不改。</p>`,
});
