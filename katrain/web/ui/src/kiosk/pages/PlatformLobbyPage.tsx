import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Snackbar } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { API, type PlatformChallenge, type PlatformUser } from '../../api';
import { useVision } from '../context/VisionContext';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { KioskCard } from '../shell/KioskCard';
import { Icon } from '../shell/icons';
import { PLATFORM_MARKS } from '../constants/platformMarks';
import { playInputState, writePlayOnBoard } from '../utils/playInput';
import { platformErrorMessage } from '../utils/platformErrorMessage';
import { backToState } from '../hooks/useBackTo';
import { writeActiveSession } from '../utils/activeSession';
import '../../kiosk-shell/ogs-home.css';

const timeLabel = (ch: PlatformChallenge) => {
  const tc = ch.time_control;
  const minutes = Math.round(tc.main_time / 60);
  const main = minutes > 0 ? `${minutes} 分` : `${tc.main_time} 秒`;
  if (tc.system === 'byoyomi' && tc.period_time && tc.periods) {
    return `${main} · 读秒 ${tc.period_time} 秒 × ${tc.periods}`;
  }
  return main;
};

const PlatformLobbyPage = () => {
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const { isVisionEnabled } = useVision();
  const navigate = useNavigate();
  const location = useLocation();
  const [connection, setConnection] = useState<
    { state: 'loading' } | { state: 'connected'; username: string | null } |
    { state: 'disconnected' } | { state: 'error' }
  >({ state: 'loading' });
  const [inputTick, setInputTick] = useState(0);
  const [onlyNineteen, setOnlyNineteen] = useState(false);
  const [challengeSearch, setChallengeSearch] = useState('');
  const [challengeState, setChallengeState] = useState<
    { state: 'loading' } | { state: 'ready'; challenges: PlatformChallenge[] } | { state: 'error' }
  >({ state: 'loading' });
  const [challengeRetry, setChallengeRetry] = useState(0);
  const [activeGame, setActiveGame] = useState<
    { state: 'loading' } | { state: 'ready'; sessionId: string | null } | { state: 'error' }
  >({ state: 'loading' });
  const [activeRetry, setActiveRetry] = useState(0);
  const [resumeError, setResumeError] = useState(false);
  const [resuming, setResuming] = useState(false);
  const resumingRef = useRef(false);
  const [acceptTarget, setAcceptTarget] = useState<PlatformChallenge | null>(null);
  const [accepting, setAccepting] = useState(false);
  const acceptingRef = useRef(false);
  const [acceptError, setAcceptError] = useState('');
  const [showPeople, setShowPeople] = useState(false);
  const [people, setPeople] = useState<PlatformUser[]>([]);
  const [peopleLoaded, setPeopleLoaded] = useState(false);
  const [peopleFailed, setPeopleFailed] = useState(false);
  const [draft, setDraft] = useState('');
  const [query, setQuery] = useState('');
  const [target, setTarget] = useState<PlatformUser | null>(null);
  const [pendingChallenge, setPendingChallenge] = useState<{ id: string; username?: string } | null>(null);
  const [sendingChallenge, setSendingChallenge] = useState(false);
  const [cancellingChallenge, setCancellingChallenge] = useState(false);
  const [toast, setToast] = useState<{ text: string; bad: boolean } | null>(null);

  const refreshStatus = useCallback(() => {
    if (!isAuthenticated) return;
    setConnection({ state: 'loading' });
    API.platformStatus(token).then((data) => {
      const ogs = data.platforms.find((entry) => entry.platform === 'ogs');
      setConnection(ogs?.connected
        ? { state: 'connected', username: ogs.saved_username?.trim() || null }
        : { state: 'disconnected' });
    }).catch(() => setConnection({ state: 'error' }));
  }, [isAuthenticated, token]);
  useEffect(() => { refreshStatus(); }, [refreshStatus]);

  useEffect(() => {
    if (connection.state !== 'connected') return;
    let cancelled = false;
    setChallengeState({ state: 'loading' });
    API.platformChallenges('ogs', token)
      .then(({ challenges }) => {
        if (!cancelled) setChallengeState({ state: 'ready', challenges });
      })
      .catch(() => {
        if (!cancelled) setChallengeState({ state: 'error' });
      });
    return () => { cancelled = true; };
  }, [connection.state, token, challengeRetry]);

  useEffect(() => {
    if (connection.state !== 'connected') return;
    let cancelled = false;
    let requestNumber = 0;
    const fetchActive = () => {
      const currentRequest = ++requestNumber;
      API.platformActiveGame('ogs', token)
        .then(({ session_id, pending_challenge_id }) => {
          if (!cancelled && currentRequest === requestNumber) {
            setActiveGame({ state: 'ready', sessionId: session_id });
            setPendingChallenge((previous) => pending_challenge_id
              ? previous?.id === pending_challenge_id ? previous : { id: pending_challenge_id }
              : null);
          }
        })
        .catch(() => {
          if (!cancelled && currentRequest === requestNumber) setActiveGame({ state: 'error' });
        });
    };
    setActiveGame({ state: 'loading' });
    fetchActive();
    const interval = window.setInterval(fetchActive, 15000);
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [connection.state, token, activeRetry]);

  const fetchPeople = useCallback(async (q: string) => {
    if (!isAuthenticated) return;
    setPeopleLoaded(false);
    try {
      const result = await API.platformUsers('ogs', token, q || undefined);
      setPeople(Array.isArray(result.users) ? result.users : []);
      setPeopleFailed(false);
    } catch {
      setPeople([]);
      setPeopleFailed(true);
    } finally {
      setPeopleLoaded(true);
    }
  }, [isAuthenticated, token]);
  useEffect(() => { if (showPeople) void fetchPeople(query); }, [showPeople, fetchPeople, query]);

  const input = playInputState(isVisionEnabled, 19);
  void inputTick;
  const challengeRows = challengeState.state === 'ready' ? challengeState.challenges : [];
  const shownChallenges = challengeRows.filter((ch) =>
    (!onlyNineteen || ch.board_size === 19) &&
    ch.from_user.username.toLocaleLowerCase().includes(challengeSearch.trim().toLocaleLowerCase()),
  );

  const sendChallenge = async (user: PlatformUser) => {
    if (sendingChallenge || pendingChallenge) return;
    setSendingChallenge(true);
    try {
      const { challenge_id } = await API.platformSendChallenge('ogs', {
        user_id: user.user_id, board_size: 19, rules: 'chinese', ranked: true,
      }, token);
      if (!challenge_id) throw new Error('OGS 没有返回挑战编号');
      setPendingChallenge({ id: challenge_id, username: user.username });
      setActiveRetry((n) => n + 1);
      setToast({ text: t('platform:challenge_sent', '挑战已发出。对方接受后，这里会出现“继续对局”。'), bad: false });
    } catch (error) {
      setToast({ text: platformErrorMessage(error, t('platform:challenge_failed', '挑战没发出去')), bad: true });
    } finally {
      setTarget(null);
      setSendingChallenge(false);
    }
  };

  const cancelChallenge = async () => {
    if (!pendingChallenge || cancellingChallenge) return;
    setCancellingChallenge(true);
    try {
      await API.platformDeclineChallenge('ogs', pendingChallenge.id, token);
      setPendingChallenge(null);
      setActiveRetry((n) => n + 1);
      setToast({ text: '约战已取消', bad: false });
    } catch (error) {
      setActiveRetry((n) => n + 1);
      setToast({ text: platformErrorMessage(error, '取消约战失败'), bad: true });
    } finally {
      setCancellingChallenge(false);
    }
  };

  const enterGame = (sessionId: string, boardSize: number) => {
    const route = `/kiosk/play/cross-platform/game/${encodeURIComponent(sessionId)}`;
    writeActiveSession({
      kind: 'game', label: 'OGS · 人人对弈', route, ts: Date.now(),
      onBoard: playInputState(isVisionEnabled, boardSize).onBoard,
    });
    navigate(route, { state: backToState(location) });
  };

  const resumeGame = async (sessionId: string) => {
    if (resumingRef.current) return;
    resumingRef.current = true;
    setResuming(true);
    setResumeError(false);
    try {
      const { state } = await API.getState(sessionId, token ?? undefined);
      const size = state?.board_size;
      if (!Array.isArray(size) || size.length !== 2 || size[0] !== size[1]
        || ![9, 13, 19].includes(size[0])) throw new Error('unverified OGS board size');
      enterGame(sessionId, size[0]);
    } catch {
      setResumeError(true);
    } finally {
      resumingRef.current = false;
      setResuming(false);
    }
  };

  const acceptChallenge = async () => {
    if (!acceptTarget || acceptingRef.current) return;
    acceptingRef.current = true;
    setAccepting(true);
    setAcceptError('');
    try {
      const { session_id } = await API.platformAcceptChallenge('ogs', acceptTarget.challenge_id, token);
      if (!session_id) throw new Error('OGS 没有返回对局编号');
      enterGame(session_id, acceptTarget.board_size);
    } catch (error) {
      setAcceptError(platformErrorMessage(error, '接受挑战失败'));
    } finally {
      acceptingRef.current = false;
      setAccepting(false);
    }
  };

  return (
    <div className="kiosk-layout-b ogshome" data-testid="platform-lobby-page">
      <KioskPagebar
        backLabel={t('platform:back_to_play', '返回对弈')}
        onBack={() => navigate('/kiosk/play')}
        title={<span className="ogshome__title"><img src={PLATFORM_MARKS.ogs.src} alt="" /><strong>OGS</strong><small>{connection.state === 'connected' ? <>已连接 · <span>{connection.username ?? '账号名未返回'}</span></> : connection.state === 'disconnected' ? '尚未连接' : connection.state === 'error' ? '连接状态读取失败' : '正在读取账号'}</small></span>}
        status={connection.state === 'connected' ? <span className="ogshome__connected">已连接</span> : undefined}
      />
      <KioskScrollZone className="ogshome__scroll">
        {connection.state === 'error' && <div className="ogshome__status-error" role="alert">没能读取 OGS 账号状态 <button type="button" onClick={refreshStatus}>重试</button></div>}
        {connection.state === 'disconnected' && <p className="ogshome__notice">OGS 尚未连接。请先连接账号。</p>}
        <div className="ogshome__input">
          <span className="ogshome__field">落子</span>
          <div className="ogshome__segment" role="group" aria-label="落子方式">
            <button type="button" aria-pressed={!input.onBoard} onClick={() => { writePlayOnBoard(false); setInputTick((n) => n + 1); }}>屏幕</button>
            <button type="button" aria-pressed={input.onBoard} disabled={!input.available} onClick={() => { writePlayOnBoard(true); setInputTick((n) => n + 1); }}>实体盘</button>
          </div>
          <div className="ogshome__size"><span>路数</span><b>19 路</b><span>{input.available ? '实体盘只下 19 路' : '未接通实体盘'}</span></div>
        </div>

        {connection.state === 'connected' && activeGame.state === 'ready' && activeGame.sessionId && <div className="ogshome__resume">
          <span>OGS 有进行中的对局</span>
          <button type="button" disabled={resuming} onClick={() => { void resumeGame(activeGame.sessionId!); }}>
            {resuming ? '正在读取棋盘…' : '继续对局'}
          </button>
        </div>}
        {connection.state === 'connected' && pendingChallenge && !(activeGame.state === 'ready' && activeGame.sessionId) && <div className="ogshome__resume">
          <span>{pendingChallenge.username ? `等待 ${pendingChallenge.username} 接受挑战` : '等待对方接受挑战'}</span>
          <button type="button" disabled={cancellingChallenge} onClick={() => { void cancelChallenge(); }}>
            {cancellingChallenge ? '正在取消…' : '取消约战'}
          </button>
        </div>}
        {resumeError && <p className="ogshome__status-error" role="alert">没能确认这局的棋盘路数，请重试进入对局</p>}
        {connection.state === 'connected' && activeGame.state === 'error' && <p className="ogshome__status-error">没能读取进行中的 OGS 对局 <button type="button" onClick={() => setActiveRetry((n) => n + 1)}>重试</button></p>}

        <section className="ogshome__section">
          <KioskSecLabel zh="开一局" en="Start" value="胜负记在 OGS 账上" />
          <div className="ogshome__cards">
            <KioskCard title="快速匹配" sub="盒上尚未接通" icon="users" disabled ariaLabel="快速匹配" />
            <KioskCard title="发起挑战" sub="盒上尚未接通" icon="list-numbers" disabled ariaLabel="发起挑战" />
            <KioskCard title="找人下" sub="按用户名直接约战" icon="magnifying-glass" onClick={() => setShowPeople((value) => !value)} ariaLabel="找人下" />
          </div>
        </section>

        <section className="ogshome__section">
          <KioskSecLabel zh="公开挑战" en="Open games" value="段位来自 OGS" />
          <div className="ogshome__filters">
            <div className="ogshome__filter-tabs" role="group" aria-label="棋局筛选">
              <button type="button" aria-pressed={!onlyNineteen} onClick={() => setOnlyNineteen(false)}>全部实时局</button>
              <button type="button" aria-pressed={onlyNineteen} onClick={() => setOnlyNineteen(true)}>19 路</button>
            </div>
            <label className="ogshome__search"><Icon name="magnifying-glass" /><input type="search" aria-label="搜索用户名" placeholder="搜索用户名" value={challengeSearch} onChange={(event) => setChallengeSearch(event.target.value)} /></label>
            <button type="button" className="ogshome__refresh" aria-label="刷新公开挑战" title="刷新公开挑战" disabled={connection.state !== 'connected' || challengeState.state === 'loading'} onClick={() => setChallengeRetry((n) => n + 1)}><Icon name="arrows-clockwise" /></button>
          </div>
          <div className="ogshome__rows">
            {connection.state !== 'connected' ? <p className="ogshome__notice">连接 OGS 后可查看公开挑战</p>
              : challengeState.state === 'loading' ? <p className="ogshome__notice" role="status">正在读取公开挑战…</p>
                : challengeState.state === 'error' ? <p className="ogshome__status-error" role="alert">没能取回公开挑战 <button type="button" onClick={() => setChallengeRetry((n) => n + 1)}>重试</button></p>
                  : shownChallenges.length === 0 ? <p className="ogshome__notice">{challengeSearch || onlyNineteen ? '没有符合条件的公开挑战' : '暂无公开挑战'}</p> : shownChallenges.map((ch) => (
              <div className="ogshome__row" key={ch.challenge_id} data-testid={`platform-challenge-${ch.challenge_id}`}>
                <span className="ogshome__avatar" aria-hidden="true">{ch.from_user.username.slice(0, 1).toUpperCase()}</span>
                <div className="ogshome__row-text"><b>{ch.from_user.username} · {ch.from_user.rank}</b><small>{ch.board_size} 路 · {timeLabel(ch)} · {ch.ranked ? '计等级分' : '不计等级分'}</small></div>
                {input.onBoard && ch.board_size !== 19 ? <span className="ogshome__tag">实体盘只下 19 路</span> : <button type="button" onClick={() => { setAcceptError(''); setAcceptTarget(ch); }}>接受</button>}
              </div>
            ))}
          </div>
        </section>

        {showPeople && <section className="ogshome__section" data-testid="platform-people">
          <KioskSecLabel zh="找人下" en="Players" value="段位来自 OGS" />
          <label className="ogshome__search ogshome__people-search"><Icon name="magnifying-glass" /><input data-testid="platform-search" aria-label="按用户名找人" placeholder="输入用户名后回车" value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') setQuery(draft.trim()); }} /></label>
          {peopleFailed && <p className="ogshome__notice">没能从平台取回名单</p>}
          {!peopleFailed && !peopleLoaded && <p className="ogshome__notice">正在读…</p>}
          {!peopleFailed && peopleLoaded && people.length === 0 && <p className="ogshome__notice">{query ? '那边没有这个人' : '输入用户名回车找人'}</p>}
          {peopleLoaded && people.map((user) => <div className="ogshome__row" key={user.user_id} data-testid="platform-user">
            <span className="ogshome__avatar" aria-hidden="true">{user.username.slice(0, 1).toUpperCase()}</span>
            <div className="ogshome__row-text"><b>{user.username}</b><small>OGS {user.rank} · {user.status === 'playing' ? '对局中' : '空闲'}</small></div>
            {user.status === 'playing' ? <span className="ogshome__tag">对局中</span> : <button type="button" disabled={!!pendingChallenge || sendingChallenge} onClick={() => setTarget(user)}>挑战</button>}
          </div>)}
        </section>}
      </KioskScrollZone>

      {target && <div className="cdlg" data-testid="platform-challenge-confirm"><div className="cdlg__box wdlg" role="dialog" aria-modal="true">
        <h3>向 {target.username} 发起挑战？</h3>
        <p className="wdlg__lead">OGS {target.rank} · 19 路 · 中国规则 · 计分局。<b>发出后可取消；对方接受后可在本页继续对局。</b></p>
        <div className="cdlg__acts"><button type="button" className="ghost" disabled={sendingChallenge} onClick={() => setTarget(null)}>取消</button><button type="button" className="main" disabled={sendingChallenge} onClick={() => { void sendChallenge(target); }}>{sendingChallenge ? '正在发送…' : '发出挑战'}</button></div>
      </div></div>}
      {acceptTarget && <div className="cdlg" data-testid="platform-accept-confirm"><div className="cdlg__box wdlg" role="dialog" aria-modal="true">
        <h3>接受 {acceptTarget.from_user.username} 的公开挑战？</h3>
        <p className="wdlg__lead">{acceptTarget.board_size} 路 · {timeLabel(acceptTarget)}。接受后将在这台盒子上进入对局。</p>
        {acceptError && <p className="ogshome__status-error" role="alert">{acceptError}</p>}
        <div className="cdlg__acts"><button type="button" className="ghost" disabled={accepting} onClick={() => setAcceptTarget(null)}>取消</button><button type="button" className="main" disabled={accepting} onClick={() => { void acceptChallenge(); }}>{acceptError ? '重试接受' : accepting ? '正在接受…' : '确认接受'}</button></div>
      </div></div>}
      <Snackbar open={!!toast} autoHideDuration={4000} onClose={() => setToast(null)}><Alert severity={toast?.bad ? 'error' : 'success'} onClose={() => setToast(null)}>{toast?.text}</Alert></Snackbar>
    </div>
  );
};

export default PlatformLobbyPage;
