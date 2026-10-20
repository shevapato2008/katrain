import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { CATEGORY_META, categoryRank, levelChinese, loadErrorCopy, readLastLevel, readPracticeResume } from './tsumegoUnits';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import './trainingReviewed.css';

interface LevelInfo {
  level: string;
  categories: Record<string, number>;
  total: number;
}

/** Real level counts drive the bounded, pointer-operated training carousel. */
const TsumegoPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [levels, setLevels] = useState<LevelInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const resume = readPracticeResume();
  const lastLevel = readLastLevel();
  const [group, setGroup] = useState(0);
  const [index, setIndex] = useState(0);
  const [drag, setDrag] = useState(0);
  const pointer = useRef<{ x: number; moved: boolean } | null>(null);
  const suppressClick = useRef(false);
  const groups = [[], [], [], []] as LevelInfo[][];
  (levels ?? []).forEach(level => {
    const rank = Number.parseInt(level.level, 10);
    const bucket = /d/i.test(level.level) ? 3 : rank > 10 ? 0 : rank > 5 ? 1 : 2;
    groups[bucket].push(level);
  });
  const cards = groups[group];
  const choose = (next: number) => setIndex(Math.max(0, Math.min(cards.length - 1, next)));


  const load = useCallback(() => {
    setLevels(null);
    setError(null);
    fetch('/api/v1/tsumego/levels')
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: LevelInfo[]) => { setLevels(data); const first = data[0]; if (first) { const rank = Number.parseInt(first.level, 10); setGroup(/d/i.test(first.level) ? 3 : rank > 10 ? 0 : rank > 5 ? 1 : 2); setIndex(0); } })
      .catch((err: Error) => setError(err.message));
  }, []);

  useEffect(load, [load]);

  // 问候行是**一条**可翻译的句子,重点词用 `{what}` 占位标出来 —— 照现有的 `{n}` 惯例
  // (`'数子要下满 {n} 手'`)。拆成两个 msgid 会让译者看不到整句,而中英之间该不该有空格
  // 恰恰在整句里才定得下来(中文没有,英文有)。
  const [greetHead, greetTail] = t('Today we practice {what}', '今天练点{what}').split('{what}');
  const greet = (
    <div className="kiosk-greet">
      <b>{greetHead}<i>{t('what', '什么')}</i>{greetTail}</b>
      {/* 稿子写「题在实体盘上摆好，落子即判」—— 实体做题开关默认关,无摄像头的盒子根本没有实体盘,
          那句只在一种情况下成立(N26③)。换成屏幕 / 实体盘 / 有无摄像头都成立的一句。 */}
      <span>{t('tsumego:greetSub', '落子即判，走错当场退回')}</span>
    </div>
  );

  const resumeBar = resume && (
    <div className="kiosk-resume" data-testid="tsumego-resume-card">
      <span className="bar" />
      <div>
        <h4>{t('Continue practicing', '接着上次')}</h4>
        <p>{resume.label}</p>
      </div>
      <button
        type="button"
        className="kiosk-btn kiosk-btn--pill pill"
        onClick={() => navigate(resume.route)}
      >
        {t('Continue', '继续')}
      </button>
    </div>
  );

  // 三态各说各的话,一态都不许冒充另一态,更不许冒充「加载完了、就是没有」。
  if (levels === null || error || levels.length === 0) {
    return (
      <KioskScrollZone>
        {greet}
        {resumeBar}
        {error ? (
          <div className="empty" data-testid="tsumego-error">
            <h4>{loadErrorCopy(t, error).title}</h4>
            <p>{loadErrorCopy(t, error).body}</p>
            <button type="button" className="kiosk-btn kiosk-btn--pill pill" onClick={load}>
              {t('Retry', '重试')}
            </button>
          </div>
        ) : levels === null ? (
          <div className="empty" data-testid="tsumego-loading">
            <h4>{t('Loading problem set…', '正在读题库…')}</h4>
          </div>
        ) : (
          <div className="empty" data-testid="tsumego-empty">
            {/* 接口真回了空。**不说「随云端同步下来」**:盒上题库是在线直读的,没有同步这回事(N9)。 */}
            <h4>{t('tsumego:bankEmpty', '题库里还没有题')}</h4>
          </div>
        )}
      </KioskScrollZone>
    );
  }

  const colors = ['#6bc78a', '#dfb561', '#6cabc9', '#aa8cc8', '#cd8276', '#86b99e'];
  return (
    <section className="u-train-carousel-home" aria-label="训练营">
      <div className="u-train-carousel-heading"><div><strong>{t('Training', '训练营')}</strong><span>左右滑动卡片，选择棋力</span></div>
        <div className="u-train-carousel-groups" role="tablist" aria-label="棋力范围">
          {['15–11 级', '10–6 级', '5–1 级', '1–7 段'].map((label, i) => <button key={label} role="tab" aria-selected={group === i} disabled={!groups[i].length} onClick={() => { setGroup(i); setIndex(0); }}>{label}</button>)}
        </div>
      </div>
      <div className={`u-train-carousel-deck${pointer.current ? ' is-dragging' : ''}`} tabIndex={0} role="region" aria-label="棋力卡片轮播"
        onKeyDown={event => { if (event.key === 'ArrowRight') choose(index + 1); if (event.key === 'ArrowLeft') choose(index - 1); }}
        onPointerDown={event => { if (event.button !== 0) return; pointer.current = { x: event.clientX, moved: false }; suppressClick.current = false; }}
        onPointerMove={event => { if (!pointer.current) return; const distance = event.clientX - pointer.current.x; if (Math.abs(distance) > 8) { pointer.current.moved = true; event.currentTarget.setPointerCapture?.(event.pointerId); } setDrag(distance); }}
        onPointerUp={event => { if (!pointer.current) return; const distance = event.clientX - pointer.current.x; suppressClick.current = pointer.current.moved; if (Math.abs(distance) > 45) choose(index + (distance < 0 ? 1 : -1)); pointer.current = null; setDrag(0); }}
        onPointerCancel={() => { pointer.current = null; suppressClick.current = true; setDrag(0); }}
        onClickCapture={event => { if (suppressClick.current) { event.preventDefault(); event.stopPropagation(); suppressClick.current = false; } }}>
        {cards.map((level, i) => {
          const delta = i - index + drag / 300;
          const categories = Object.entries(level.categories ?? {}).filter(([, count]) => Number.isFinite(count) && count >= 0).sort(([a], [b]) => categoryRank(a) - categoryRank(b));
          const sum = categories.reduce((total, [, count]) => total + count, 0);
          let cumulative = 0;
          const stops = categories.map(([, count], j) => { const start = cumulative; cumulative += count / sum * 100; return `${colors[j % colors.length]} ${start}% ${cumulative}%`; });
          return <article key={level.level} className={`u-train-carousel-card${i === index ? ' is-center' : ''}${!sum ? ' is-unknown' : ''}`} style={{ transform: `translate(calc(-50% + ${delta * 360}px), calc(-50% + ${Math.min(Math.abs(delta), 1) * 35}px)) scale(${1 - Math.min(Math.abs(delta), 1) * .56}) rotateY(${-delta * 4}deg)`, opacity: Math.abs(delta) > 2 ? 0 : 1, zIndex: 20 - Math.round(Math.abs(delta) * 5), pointerEvents: Math.abs(delta) > 2 ? 'none' : undefined, transition: drag ? 'none' : undefined }} onClick={() => { if (i !== index) choose(i); }}>
            <div className="u-train-carousel-card-head"><strong>{levelChinese(level.level)}</strong><span>{level.total} 题{level.level === lastLevel ? ' · 你的水平' : ''}</span></div>
            <div className="u-train-carousel-card-body"><div className="u-train-carousel-pie" style={{ '--u-train-pie': sum ? `conic-gradient(${stops.join(',')})` : undefined } as CSSProperties} role="img" aria-label={sum ? categories.map(([name, count]) => `${CATEGORY_META[name]?.zh ?? name} ${count}题`).join('，') : '题型构成暂不可用'}><div><strong>{sum || '—'}</strong><span>道题</span></div></div>
              {sum ? <div className="u-train-carousel-legend">{categories.map(([name, count], j) => <div key={name} style={{ '--u-train-swatch': colors[j % colors.length] } as CSSProperties}><i /><span>{t(`tsumego:${name}`, CATEGORY_META[name]?.zh ?? name)}</span><b>{(count / sum * 100).toFixed(1)}%</b><small>{count}题</small></div>)}</div> : <div className="u-train-carousel-unavailable">题型构成暂不可用</div>}
            </div>
            <button tabIndex={i === index ? 0 : -1} className="u-train-carousel-enter" onClick={() => { if (i === index) navigate(`/kiosk/tsumego/${level.level}`); }}>进入 {levelChinese(level.level)} 题型</button>
          </article>;
        })}
      </div>
      <button className="u-train-carousel-nav is-prev" aria-label="上一棋力" disabled={index === 0} onClick={() => choose(index - 1)}>‹</button><button className="u-train-carousel-nav is-next" aria-label="下一棋力" disabled={index >= cards.length - 1} onClick={() => choose(index + 1)}>›</button>
      <div className="u-train-carousel-foot"><span>{index + 1} / {cards.length}</span><div>{cards.map((level, i) => <i key={level.level} className={i === index ? 'is-active' : ''} />)}</div><span>手指拖动 · 松手吸附</span></div>
    </section>
  );
};

export default TsumegoPage;
