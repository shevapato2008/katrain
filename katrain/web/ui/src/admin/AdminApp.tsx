import { useCallback, useEffect, useState } from 'react';
import { ArrowLeft, BookOpen, ChevronLeft, ChevronRight, Clock3 } from 'lucide-react';
import SGFBoard, { type SGFPayload } from '../components/tutorials/SGFBoard';
import galaxyLogo from '../../../../img/logo-white.png';
import { AdminApiError, createAdminApi, tutorialAssetUrl, type TutorialBook, type TutorialBookDetail, type TutorialFigure, type TutorialSection, type TutorialSectionDetail } from './api/client';
import CronDashboard from './cron/CronDashboard';
import './AdminApp.css';

const TOKEN_KEY = 'katrain_admin_session';
const api = createAdminApi((input, init) => fetch(input, init), () => localStorage.getItem(TOKEN_KEY));
const ENV_LABELS: Record<string, string> = { local: '本机环境', test: '测试环境', prod: '生产环境' };
const emptyBoard = (): SGFPayload => ({ size: 19, stones: { B: [], W: [] } });
const moveCount = (board: SGFPayload) => board.stones.B.length + board.stones.W.length;
type Draft = {
  narration: string; board: SGFPayload; added: [number, number][];
  baseNarration: string; baseBoard: SGFPayload | null; initializeBoard: boolean;
};
const boardEdited = (draft: Draft) =>
  (draft.initializeBoard && draft.baseBoard === null) ||
  JSON.stringify(draft.board) !== JSON.stringify(draft.baseBoard ?? emptyBoard());

export default function AdminApp() {
  const [checkingSession, setCheckingSession] = useState(true);
  const [signedIn, setSignedIn] = useState(false);
  const [page, setPage] = useState<'tutorial' | 'cron'>('tutorial');
  const [adminName, setAdminName] = useState('');
  const [environment, setEnvironment] = useState('后台环境');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [books, setBooks] = useState<TutorialBook[] | null>(null);
  const [bookId, setBookId] = useState<number | null>(null);
  const [bookDetail, setBookDetail] = useState<TutorialBookDetail | null>(null);
  const [chapterId, setChapterId] = useState<number | null>(null);
  const [sections, setSections] = useState<TutorialSection[] | null>(null);
  const [sectionId, setSectionId] = useState<number | null>(null);
  const [sectionDetail, setSectionDetail] = useState<TutorialSectionDetail | null>(null);
  const [figureIndex, setFigureIndex] = useState(0);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [conflictPending, setConflictPending] = useState(false);
  const [conflictFigure, setConflictFigure] = useState<TutorialFigure | null>(null);
  const [conflictFields, setConflictFields] = useState<string[]>([]);
  const [conflictApproved, setConflictApproved] = useState(false);
  const [moveStep, setMoveStep] = useState<number | null>(null);
  const [checkedFigureId, setCheckedFigureId] = useState<number | null>(null);
  const [showFigureList, setShowFigureList] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);

  const clearSession = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setSignedIn(false);
    setAdminName('');
    setBooks(null);
    setBookId(null);
    setBookDetail(null);
    setChapterId(null);
    setSections(null);
    setSectionId(null);
    setSectionDetail(null);
    setDraft(null);
    setConflictPending(false);
    setConflictFigure(null);
    setConflictFields([]); setConflictApproved(false);
  }, []);

  const reportFailure = useCallback((cause: unknown) => {
    if (cause instanceof AdminApiError && cause.status === 401) {
      clearSession();
      setLoginError('后台会话已失效，请重新登录。');
    } else if (cause instanceof AdminApiError && cause.status === 409) {
      setConflictPending(true);
      setConflictFigure(null);
      setError('内容已被其他会话修改。草稿仍在此页，请先刷新当前图并核对后重试。');
    } else {
      setError(cause instanceof Error ? cause.message : '操作失败，请重试。');
    }
  }, [clearSession]);

  useEffect(() => {
    let active = true;
    if (!localStorage.getItem(TOKEN_KEY)) { setCheckingSession(false); return; }
    api.me().then((profile) => {
      if (!active) return;
      setAdminName(profile.username);
      setEnvironment(profile.env);
      setSignedIn(true);
    }).catch(() => { if (active) clearSession(); }).finally(() => { if (active) setCheckingSession(false); });
    return () => { active = false; };
  }, [clearSession]);

  useEffect(() => {
    if (!signedIn) return;
    let active = true;
    setLoading(true); setError('');
    api.categories().then(async (categories) => (await Promise.all(categories.map((item) => api.books(item.slug)))).flat())
      .then((items) => { if (active) { setBooks(items); setBookId((previous) => items.some((item) => item.id === previous) ? previous : items[0]?.id ?? null); } })
      .catch((cause) => { if (active) reportFailure(cause); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [signedIn, retry, reportFailure]);

  useEffect(() => {
    if (bookId === null) return;
    let active = true;
    setBookDetail(null); setSections(null); setSectionDetail(null); setLoading(true); setError('');
    api.book(bookId).then((item) => { if (active) { setBookDetail(item); setChapterId(item.chapters[0]?.id ?? null); } })
      .catch((cause) => { if (active) reportFailure(cause); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [bookId, retry, reportFailure]);

  useEffect(() => {
    if (chapterId === null) return;
    let active = true;
    setSections(null); setSectionDetail(null); setLoading(true); setError('');
    api.sections(chapterId).then((items) => { if (active) { setSections(items); setSectionId(items[0]?.id ?? null); } })
      .catch((cause) => { if (active) reportFailure(cause); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [chapterId, retry, reportFailure]);

  useEffect(() => {
    if (sectionId === null) return;
    let active = true;
    setSectionDetail(null); setLoading(true); setError('');
    api.section(sectionId).then((item) => { if (active) { setSectionDetail(item); setFigureIndex(0); } })
      .catch((cause) => { if (active) reportFailure(cause); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [sectionId, retry, reportFailure]);

  const book = books?.find((item) => item.id === bookId);
  const chapter = bookDetail?.chapters.find((item) => item.id === chapterId);
  const section = sections?.find((item) => item.id === sectionId);
  const figure = sectionDetail?.figures[figureIndex];
  const board = draft?.board ?? figure?.board_payload ?? emptyBoard();
  const totalMoves = board ? moveCount(board) : 0;
  const shownStep = Math.min(moveStep ?? totalMoves, totalMoves);
  const environmentLabel = ENV_LABELS[environment] ?? '后台环境';

  function resetFigureState() {
    setDraft(null); setConflictPending(false); setConflictFigure(null); setConflictFields([]); setConflictApproved(false); setMoveStep(null); setCheckedFigureId(null); setShowFigureList(false); setMessage(''); setError('');
  }

  async function signIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoginError(''); setBusy(true);
    try {
      const result = await api.login(username.trim(), password);
      localStorage.setItem(TOKEN_KEY, result.access_token);
      const profile = await api.me();
      setAdminName(profile.username);
      setEnvironment(profile.env);
      setPassword(''); setSignedIn(true);
    } catch (cause) {
      localStorage.removeItem(TOKEN_KEY);
      setLoginError(cause instanceof Error ? cause.message : '登录失败，请重试。');
    } finally { setBusy(false); }
  }

  async function signOut() {
    try { await api.logout(); } catch { /* The local token is still discarded. */ }
    clearSession();
  }

  function startEdit(initializeBoard: boolean) {
    if (!figure) return;
    setDraft({ narration: figure.narration ?? '', board: structuredClone(figure.board_payload ?? emptyBoard()), added: [], baseNarration: figure.narration ?? '', baseBoard: structuredClone(figure.board_payload), initializeBoard });
    setConflictPending(false); setConflictFigure(null); setConflictFields([]); setConflictApproved(false); setMoveStep(null); setMessage(''); setError('');
  }

  function placeStone(col: number, row: number) {
    if (!draft) return;
    if ([...draft.board.stones.B, ...draft.board.stones.W].some(([c, r]) => c === col && r === row)) return;
    const next = structuredClone(draft.board);
    const color = moveCount(next) % 2 === 0 ? 'B' : 'W';
    next.stones[color].push([col, row]);
    next.labels = { ...next.labels, [`${col},${row}`]: String(moveCount(next)) };
    setDraft({ ...draft, board: next, added: [...draft.added, [col, row]] });
    setConflictApproved(false);
    setMoveStep(null); setCheckedFigureId(null);
  }

  function undoStone() {
    if (!draft?.added.length) return;
    const [col, row] = draft.added[draft.added.length - 1];
    const next = structuredClone(draft.board);
    next.stones.B = next.stones.B.filter(([c, r]) => c !== col || r !== row);
    next.stones.W = next.stones.W.filter(([c, r]) => c !== col || r !== row);
    if (next.labels) delete next.labels[`${col},${row}`];
    setDraft({ ...draft, board: next, added: draft.added.slice(0, -1) });
    setConflictApproved(false);
    setMoveStep(null);
  }

  function replaceFigure(updated: TutorialFigure) {
    setSectionDetail((current) => current ? { ...current, figures: current.figures.map((item) => item.id === updated.id ? updated : item) } : current);
  }

  async function reloadServerVersion() {
    if (!figure || !draft) return;
    setBusy(true);
    try {
      const latest = await api.figure(figure.id);
      const draftBoardEdited = boardEdited(draft);
      const draftNarrationEdited = draft.narration !== draft.baseNarration;
      const latestBoard = latest.board_payload ?? emptyBoard();
      const fields = [
        draftBoardEdited && JSON.stringify(latest.board_payload) !== JSON.stringify(draft.baseBoard) && JSON.stringify(draft.board) !== JSON.stringify(latestBoard) ? '棋图' : '',
        draftNarrationEdited && (latest.narration ?? '') !== draft.baseNarration && draft.narration !== (latest.narration ?? '') ? '讲解' : '',
      ].filter(Boolean);
      setDraft({
        ...draft,
        board: draftBoardEdited ? draft.board : structuredClone(latestBoard),
        narration: draftNarrationEdited ? draft.narration : latest.narration ?? '',
        baseBoard: structuredClone(latest.board_payload),
        baseNarration: latest.narration ?? '',
      });
      replaceFigure(latest);
      setConflictFigure(latest);
      setConflictFields(fields); setConflictApproved(false);
      setConflictPending(false);
      setError('');
      setMessage(fields.length ? '服务器版本已读取。以下字段两边都已修改，请核对后确认是否覆盖。' : '服务器版本已读取，草稿与其他字段的修改已合并。');
    } catch (cause) { reportFailure(cause); } finally { setBusy(false); }
  }

  async function saveDraft() {
    if (!figure || !draft) return;
    if (conflictPending || (conflictFields.length && !conflictApproved)) return;
    const boardChanged = boardEdited(draft);
    const narrationChanged = draft.narration !== draft.baseNarration;
    if (!boardChanged && !narrationChanged) { setDraft(null); setMessage('没有需要保存的更改。'); return; }
    setBusy(true); setError('');
    try {
      const updated = boardChanged
        ? await api.saveBoard(figure.id, { board_payload: draft.board, ...(narrationChanged ? { narration: draft.narration } : {}), expected_updated_at: figure.updated_at })
        : await api.saveNarration(figure.id, { narration: draft.narration, expected_updated_at: figure.updated_at });
      replaceFigure(updated); setDraft(null); setConflictPending(false); setConflictFigure(null); setConflictFields([]); setConflictApproved(false); setCheckedFigureId(null); setMoveStep(null); setMessage('更改已保存。');
    } catch (cause) { reportFailure(cause); } finally { setBusy(false); }
  }

  async function generateAudio() {
    if (!figure || draft) return;
    setBusy(true); setError('');
    try {
      const updated = await api.generateAudio(figure.id, { narration: figure.narration ?? '', expected_updated_at: figure.updated_at });
      replaceFigure(updated); setMessage('讲解音频已生成。');
    } catch (cause) { reportFailure(cause); } finally { setBusy(false); }
  }

  async function verifyFigure() {
    if (!figure || draft || checkedFigureId !== figure.id) return;
    setBusy(true); setError('');
    try {
      const result = await api.verify(figure.id, { expected_updated_at: figure.updated_at });
      replaceFigure(result.figure); setCheckedFigureId(null);
      setMessage(`审核已保存；训练样本${result.training_export.status === 'exported' ? `导出 ${result.training_export.count} 条` : result.training_export.status === 'skipped' ? '未导出' : '导出失败'}${result.training_export.reason ? `：${result.training_export.reason}` : '。'}`);
    } catch (cause) { reportFailure(cause); } finally { setBusy(false); }
  }

  const header = <header className="admin-top"><div className="admin-brand" aria-label="KaTrain 管理后台"><img src={galaxyLogo} alt="" /><span className="admin-brand-cn">智星盒</span><span className="admin-brand-en">StellaBox</span><span className="admin-brand-admin">管理后台</span></div><div className="admin-topright"><span className="admin-env" data-env={environment}>{environmentLabel}</span>{signedIn && <><span>{adminName}</span><button onClick={signOut}>退出</button></>}</div></header>;

  if (checkingSession) return <div className="admin-app">{header}<div className="admin-load-state" role="status">正在检查后台会话…</div></div>;
  if (!signedIn) return <div className="admin-app">{header}<section className="admin-signin-page" aria-label="后台登录"><form className="admin-signin-card" onSubmit={signIn}><h1>登录管理后台</h1><p>通过 SSH 隧道访问的后台专用账号，与公开 Galaxy 账号独立。</p><label htmlFor="admin-username">后台用户名</label><input id="admin-username" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" placeholder="输入后台用户名" required /><label htmlFor="admin-password">密码</label><input id="admin-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" placeholder="输入密码" required />{loginError && <p className="admin-form-error" role="alert">{loginError}</p>}<button type="submit" disabled={busy}>{busy ? '正在登录…' : '登录'}</button><div className="admin-signin-help">仅供授权管理员使用；无公开注册入口。</div></form></section></div>;

  return <div className="admin-app">{header}<div className="admin-wrap"><aside className="admin-side" aria-label="管理导航"><div className="admin-sidehead">内容与服务</div><button type="button" className={`admin-nav ${page === 'tutorial' ? 'active' : ''}`} style={{ width: '100%', textAlign: 'left', cursor: 'pointer', border: 0, fontFamily: 'inherit', background: page === 'tutorial' ? 'var(--admin-active)' : 'transparent' }} onClick={() => setPage('tutorial')}><BookOpen aria-hidden="true" />教程管理</button><button type="button" className={`admin-nav ${page === 'cron' ? 'active' : ''}`} style={{ width: '100%', textAlign: 'left', cursor: 'pointer', border: 0, fontFamily: 'inherit', background: page === 'cron' ? 'var(--admin-active)' : 'transparent' }} onClick={() => setPage('cron')}><Clock3 aria-hidden="true" />定时任务</button><div className="admin-sidefoot">当前环境：{environmentLabel}<br />{page === 'cron' ? '此页面只读，不会运行或暂停任务。' : '修改会写入该环境的教程数据'}</div></aside>{page === 'cron' ? <CronDashboard api={api} onUnauthorized={() => reportFailure(new AdminApiError(401, '后台会话已失效'))} /> : <main className="admin-main">
    <div className="admin-heading"><div><div className="admin-title">教程管理</div><div className="admin-crumb">{book?.title ?? '教材'} / {chapter?.title ?? '章节'} / {section?.title ?? '小节'} / {figure?.figure_label ?? '图'}</div></div><div className="admin-headcontrols"><select aria-label="选择教材" value={bookId ?? ''} onChange={(event) => { setBookId(Number(event.target.value)); setChapterId(null); setSectionId(null); resetFigureState(); }}>{books?.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select><select aria-label="选择章节" value={chapterId ?? ''} onChange={(event) => { setChapterId(Number(event.target.value)); setSectionId(null); resetFigureState(); }}>{bookDetail?.chapters.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select><select aria-label="选择小节" value={sectionId ?? ''} onChange={(event) => { setSectionId(Number(event.target.value)); resetFigureState(); }}>{sections?.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></div></div>
    {!figure && (loading || error || (books && books.length === 0) || (sections && sections.length === 0) || (sectionDetail && sectionDetail.figures.length === 0)) && <div className="admin-load-state" role={error ? 'alert' : 'status'}>{error || (loading ? '正在读取教程数据…' : books?.length === 0 ? '当前环境没有教程教材。' : sections?.length === 0 ? '当前章节没有小节。' : '当前小节没有棋图。')}{error && <button onClick={() => { setError(''); setRetry((value) => value + 1); }}>重试</button>}</div>}
    {figure && <div className="admin-workspace">
      <section className="admin-source" aria-label="原书页"><div className="admin-panehead"><strong>原书页对照</strong><span>第 {figure.page} 页</span></div><div className="admin-book">{tutorialAssetUrl(figure.page_image_path) ? <img className="admin-pageimage" src={tutorialAssetUrl(figure.page_image_path)!} alt={`第 ${figure.page} 页原书扫描`} /> : <div className="admin-source-missing">此图没有原书页图片</div>}<div className="admin-sourcecaption">{figure.book_text || figure.page_context_text || '暂无原书文字'}</div></div></section>
      <section className="admin-center" role="region" aria-label="2D 电子棋盘"><div className="admin-boardbar"><strong>{figure.figure_label} · 棋图预览</strong><span>当前第 {shownStep} / {totalMoves} 手 · 棋图局部</span></div>{figure.board_payload === null && !draft && <div className="admin-draft-note">此图尚无棋盘，空盘仅作为编辑起点。</div>}<div className="admin-boardstage"><SGFBoard payload={board} maxMoveStep={shownStep} onClick={draft ? placeStone : undefined} maxWidth="min(100%, 620px)" className="admin-board" /></div>{draft && <div className="admin-editbar"><button className="admin-tool on" type="button">落子</button><button className="admin-tool" type="button" onClick={undoStone} disabled={!draft.added.length}>撤销</button><span className="admin-edit-hint">草稿 {totalMoves} 手 · 未保存</span></div>}</section>
      <section className="admin-right" aria-label="图详情与编辑">
        <div className="admin-rightscroll">
          <div className="admin-figuretitle"><button type="button" className="admin-back" aria-label="返回图列表" onClick={() => setShowFigureList((open) => !open)}><ArrowLeft size={22} /></button><div><h1>{figure.figure_label}</h1><div className="admin-sub">图 {figureIndex + 1} · 本节共 {sectionDetail?.figures.length ?? 0} 图</div></div><span className="admin-viewtag">编辑工作台</span></div>
          {showFigureList && <div className="admin-figurelist" aria-label="图列表">{sectionDetail?.figures.map((item, index) => <button key={item.id} className={index === figureIndex ? 'selected' : ''} onClick={() => { setFigureIndex(index); resetFigureState(); }}>{item.figure_label}</button>)}</div>}
          <div className="admin-pager"><button aria-label="上一图" disabled={figureIndex === 0} onClick={() => { setFigureIndex((index) => index - 1); resetFigureState(); }}><ChevronLeft /></button><span>图 {figureIndex + 1} / {sectionDetail?.figures.length ?? 0}</span><button aria-label="下一图" disabled={figureIndex >= (sectionDetail?.figures.length ?? 0) - 1} onClick={() => { setFigureIndex((index) => index + 1); resetFigureState(); }}><ChevronRight /></button></div>
          <button className="admin-sourcebtn" onClick={() => document.querySelector('.admin-source')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })}>▣ 对照原书页</button>
          <div className="admin-section"><div className="admin-label">手数</div><div className="admin-moves"><span>当前 {shownStep} / {totalMoves}</span><span>逐手查看棋图</span></div><input className="admin-range" type="range" min="0" max={totalMoves} value={shownStep} aria-label="棋图手数" onChange={(event) => setMoveStep(Number(event.target.value))} /></div>
          <div className="admin-section"><div className="admin-label"><span>语音讲解</span><span>文字与语音分开保存</span></div>{draft ? <textarea className="admin-editcopy" aria-label="编辑语音讲解" value={draft.narration} onChange={(event) => { setDraft({ ...draft, narration: event.target.value }); setConflictApproved(false); }} /> : <p className="admin-copy">{figure.narration || '暂无讲解文字'}</p>}{draft && <div className="admin-draft-note">● 未保存的棋图和讲解不会影响公开页面</div>}<div className="admin-mini">讲解音频</div>{tutorialAssetUrl(figure.audio_asset) ? <audio controls src={tutorialAssetUrl(figure.audio_asset)!} aria-label="讲解音频" /> : <div className="admin-mini">尚未生成音频</div>}<div className="admin-media">{tutorialAssetUrl(figure.video_asset) ? <video controls src={tutorialAssetUrl(figure.video_asset)!} aria-label="配语音的视频预览" /> : <div>配语音的视频尚未生成</div>}</div></div>
          <div className="admin-section"><div className="admin-label">审核状态</div><div className="admin-mini">{figure.recognition_debug?.human_verified ? '已审核' : '未审核。请核对原书页、棋图和讲解后确认。'}</div></div>
        </div>
        <div className="admin-actions">
          {message && <div className="admin-feedback" role="status">{message}</div>}
          {error && <div className="admin-feedback" role="alert">{error}</div>}
          {conflictPending && draft && <button className="admin-action wide" disabled={busy} onClick={reloadServerVersion}>读取服务器版本</button>}
          {conflictFigure && draft && <div className="admin-feedback admin-conflict"><strong>服务器现有讲解</strong><p>{conflictFigure.narration || '暂无讲解文字'}</p><details><summary>对照服务器棋图</summary>{conflictFigure.board_payload ? <SGFBoard payload={conflictFigure.board_payload} maxWidth="220px" /> : <p>服务器尚无棋盘</p>}</details></div>}
          {conflictFields.length > 0 && draft && <div className="admin-feedback admin-conflict"><strong>双方都修改了：{conflictFields.join('、')}</strong><p>保存草稿会覆盖服务器的同字段内容；请先核对。</p><button className="admin-action wide" disabled={busy} onClick={() => setConflictApproved(true)}>确认以草稿覆盖服务器同字段内容</button></div>}
          {draft ? <><button className="admin-action primary" disabled={busy || conflictPending || (conflictFields.length > 0 && !conflictApproved)} onClick={saveDraft}>保存更改</button><button className="admin-action" disabled={busy} onClick={() => { setDraft(null); setConflictPending(false); setConflictFigure(null); setConflictFields([]); setConflictApproved(false); setMoveStep(null); setMessage('已取消草稿。'); }}>取消</button></> : <><button className="admin-action" disabled={busy} onClick={() => startEdit(true)}>编辑棋图</button><button className="admin-action" disabled={busy} onClick={() => startEdit(false)}>编辑讲解</button></>}
          <button className="admin-action" disabled={busy || !!draft || !figure.narration} onClick={generateAudio}>生成语音</button>
          <button className="admin-action" disabled={busy || !!draft || !figure.board_payload} onClick={() => { setCheckedFigureId(figure.id); setMessage('已标记人工核对；点击确认审核后才会保存。'); }}>人工核对完成</button>
          <button className="admin-action wide" disabled={busy || checkedFigureId !== figure.id || !!draft || !!figure.recognition_debug?.human_verified} onClick={verifyFigure}>✓ 确认审核</button>
        </div>
      </section>
    </div>}
  </main>}</div></div>;
}
