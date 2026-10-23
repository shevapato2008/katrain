import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { OgsCourseIndex, OgsStep, OgsPoint } from '../../types/ogsCourse';
import { actOgsExercise, chooseOgsAnswer, createOgsExercise, playOgsPoint, retryOgsExercise, type OgsExerciseState } from '../tutorial/ogsExercise';
import { OgsCourseBoard } from '../tutorial/OgsCourseBoard';
import { useOgsPhysicalBoard } from '../tutorial/useOgsPhysicalBoard';
import { PhysicalBoardIcon } from '../shell/PhysicalBoardIcon';
import { backToState } from '../hooks/useBackTo';
import '../tutorial/ogs-course.css';

export default function OgsCourseExercisePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { lessonId } = useParams<{ lessonId: string }>();
  const [course, setCourse] = useState<OgsCourseIndex | null>(null);
  const [courseError, setCourseError] = useState(false);
  const [courseReload, setCourseReload] = useState(0);
  const [index, setIndex] = useState(0);
  const [step, setStep] = useState<OgsStep | null>(null);
  const [stepError, setStepError] = useState(false);
  const [stepReload, setStepReload] = useState(0);
  const [answer, setAnswer] = useState<OgsExerciseState | null>(null);
  const answerRef = useRef<OgsExerciseState | null>(null);
  const wrongBeforeRef = useRef<OgsExerciseState | null>(null);
  const [physicalMode, setPhysicalMode] = useState(false);
  const [revision, setRevision] = useState(0);
  const lesson = course?.lessons.find((item) => item.id === lessonId);
  const chapter = course?.chapters.find((item) => item.id === lesson?.chapter_id);
  const expectedPage = lesson ? lesson.first_page + index : null;
  const currentStep = step?.page === expectedPage && step.lesson_id === lessonId ? step : null;
  const currentAnswer = currentStep && answer?.step === currentStep ? answer : null;
  useEffect(() => {
    let live = true;
    TutorialReadAPI.getOgsCourse().then((data) => { if (live) { setCourse(data); setCourseError(false); } }).catch(() => { if (live) setCourseError(true); });
    return () => { live = false; };
  }, [courseReload]);
  useEffect(() => {
    if (expectedPage == null) return;
    let live = true;
    TutorialReadAPI.getOgsStep(expectedPage).then((data) => {
      if (!live) return;
      if (data.lesson_id !== lessonId || data.page !== expectedPage) { setStepError(true); return; }
      setStep(data); setStepError(false);
      const initial = createOgsExercise(data);
      answerRef.current = initial; setAnswer(initial); wrongBeforeRef.current = null;
    }).catch(() => { if (live) setStepError(true); });
    return () => { live = false; };
  }, [expectedPage, lessonId, stepReload]);
  const playPoint = useCallback((point: OgsPoint) => {
    const previous = answerRef.current;
    if (!previous) return null;
    const next = playOgsPoint(previous, point);
    if (next === previous) return null;
    answerRef.current = next; setAnswer(next);
    if (next.status === 'wrong') wrongBeforeRef.current = previous;
    return { next, previous };
  }, []);
  const undoWrong = useCallback(() => {
    if (wrongBeforeRef.current) { answerRef.current = wrongBeforeRef.current; setAnswer(wrongBeforeRef.current); wrongBeforeRef.current = null; }
  }, []);
  const physical = useOgsPhysicalBoard({ step: currentStep, state: currentAnswer, enabled: physicalMode, revision, playPoint, undoWrong });
  const handleBoardPoint = (point: OgsPoint) => {
    if (physical.active && physical.physical.phase !== 'ready') return;
    const result = playPoint(point);
    if (result) physical.onScreenMove(result.next, result.previous);
  };
  const retry = () => {
    if (!answerRef.current) return;
    const fresh = retryOgsExercise(answerRef.current);
    answerRef.current = fresh; setAnswer(fresh); wrongBeforeRef.current = null; setRevision((n) => n + 1);
  };
  const switchStep = (value: number) => { setPhysicalMode(false); setStep(null); setAnswer(null); answerRef.current = null; setIndex(value); setRevision((n) => n + 1); };
  const back = () => navigate(chapter ? `/kiosk/tutorial/chapter/${encodeURIComponent(chapter.id)}` : '/kiosk/tutorial');
  if (!lesson || !chapter) return <main className="u-ogs ogs-state" data-testid="ogs-exercise-page"><button className="ogs-key" onClick={back}>‹ 课程</button><h1>{courseError ? '课程暂不可用' : course ? '没有找到这一课' : '正在读取课目'}</h1>{courseError && <button className="ogs-key" onClick={() => { setCourseError(false); setCourseReload((n) => n + 1); }}>重试</button>}</main>;
  if (!currentStep || !currentAnswer) return <main className="u-ogs ogs-state" data-testid="ogs-exercise-page"><button className="ogs-key" onClick={back}>‹ 课目</button><h1>{stepError ? '这一题暂不可用' : '正在读取练习'}</h1>{stepError && <button className="ogs-key" onClick={() => { setStepError(false); setStepReload((n) => n + 1); }}>重试</button>}</main>;
  const kind = currentStep.exercise.kind;
  const status = currentAnswer.status;
  const choose = (value: string) => { const next = chooseOgsAnswer(currentAnswer, value); answerRef.current = next; setAnswer(next); };
  const act = (action: 'pass' | 'finish') => { const next = actOgsExercise(currentAnswer, action); answerRef.current = next; setAnswer(next); };
  const phase = physical.physical.phase;
  const physicalBusy = physical.active && phase !== 'ready' && phase !== 'solved';
  const next = () => { if (status !== 'correct' || physicalBusy) return; if (index + 1 < lesson.step_count) switchStep(index + 1); else back(); };
  const physicalMessage = physical.active ? phase === 'clearing' ? `请先清空实体棋盘${physical.physical.extra.length ? ` · 还剩 ${physical.physical.extra.length} 颗` : ''}` : phase === 'setup' ? `请摆放${physical.physical.stage === 'white' ? '白棋' : '黑棋'} · 已匹配 ${physical.physical.stageMatched}/${physical.physical.stageTotal} 颗${physical.physical.extra.length ? ` · 多余 ${physical.physical.extra.length} 颗` : ''}` : phase === 'replying' ? '请按棋盘灯光补摆应手并拿除被提的棋子' : phase === 'removing' ? `答错了：请取回 ${physical.physical.extra.length} 颗棋子${physical.physical.missing.length ? `，并放回被提的 ${physical.physical.missing.length} 颗` : ''}` : phase === 'restoring' ? '请按灯光将实体盘恢复到屏幕局面' : phase === 'ready' ? '实体盘已就绪 · 屏幕点击与实体落子均可' : phase === 'solved' ? '实体盘答对' : '正在连接实体盘' : physical.reason || '也可以在实体盘上练习';
  return <main className="u-ogs ogs-exercise" data-testid="ogs-exercise-page">
    <OgsCourseBoard step={currentStep} state={currentAnswer} onPoint={handleBoardPoint} disabled={physical.active && phase !== 'ready'} extra={physical.extra} />
    <section className="ogs-exercise-rail"><div className="ogs-exercise-title"><button className="ogs-key" onClick={back}>‹ 课目</button><h2>{lesson.title}</h2></div>
      <div className="ogs-breadcrumb"><span>第 {chapter.number} 章 · 第 {lesson.order} 课</span><span>第 {index + 1} / {lesson.step_count} 步</span></div>
      <div className="ogs-progress">{Array.from({ length: Math.min(lesson.step_count, 20) }, (_, i) => <i key={i} className={Math.floor(index * Math.min(lesson.step_count, 20) / lesson.step_count) === i ? 'is-current' : ''} />)}</div>
      <section className="ogs-card ogs-instruction"><span className="ogs-instruction-label">这一题</span><p>{currentStep.locale.text.instruction || currentStep.locale.text.title}</p></section>
      <section className={`ogs-card ogs-interaction ${!physicalBusy && status === 'correct' ? 'is-success' : status === 'wrong' ? 'is-error' : ''}`}>
        <strong>{physicalBusy ? phase === 'clearing' || phase === 'setup' ? '准备实体盘' : phase === 'replying' ? '同步实体盘' : phase === 'removing' ? '拿除错子' : '核对实体盘' : status === 'correct' ? '回答正确' : status === 'wrong' ? '再试一次' : kind === 'choice' ? '选出答案' : kind === 'remove' ? '点选要拿除的棋块' : kind === 'pass' ? '请弃手' : kind === 'finish' ? '请确认终局' : '轮到你落子'}</strong>
        {kind === 'choice' && status === 'active' && <div className="ogs-choice-row">{currentStep.exercise.kind === 'choice' && currentStep.exercise.choices.map((choice) => <button key={choice.value} className="ogs-key" onClick={() => choose(choice.value)}>{currentStep.locale.text.choices?.[choice.value] ?? choice.label_key ?? choice.value}</button>)}</div>}
        {kind === 'pass' && status === 'active' && <button className="ogs-key ogs-inline-action" onClick={() => act('pass')}>弃手</button>}
        {kind === 'finish' && status === 'active' && <button className="ogs-key ogs-inline-action" onClick={() => act('finish')}>确认终局</button>}
        {physicalBusy && <span>{physicalMessage}</span>}
        {status === 'wrong' && !physicalBusy && <button className="ogs-key ogs-inline-action" onClick={retry}>重试</button>}
        {status === 'correct' && !physicalBusy && <span>{index + 1 >= lesson.step_count ? '这一课已完成。' : '继续进入下一步。'}</span>}
        {status === 'active' && kind === 'puzzle' && !physicalBusy && <span>{`${currentAnswer.player === 'B' ? '黑棋' : '白棋'}行棋 · 点按棋盘交叉点。`}</span>}
        {status === 'active' && kind === 'remove' && <span>点按棋盘上的棋块，再核对拿除目标。</span>}
      </section>
      <div className="ogs-physical-hint" data-testid="ogs-physical-hint">{physical.active ? '实体盘已开启 · 请按设备指引摆局' : physicalMessage}{physical.calibrate && <button className="ogs-calibrate" onClick={() => navigate('/kiosk/vision/setup', { state: backToState(location) })}>去标定</button>}{physical.active && !physical.physical.ledOk && <span> · LED 没连上，请按屏幕提示操作</span>}</div>
      <div className="ogs-exercise-actions"><button className="ogs-key" disabled={index === 0} onClick={() => switchStep(index - 1)}>‹ 上一步</button><button className={`ogs-key ${physicalMode ? 'is-physical' : ''}`} aria-pressed={physicalMode} disabled={!physicalMode && !physical.available} onClick={() => setPhysicalMode((value) => !value)}><PhysicalBoardIcon />实体盘</button><button className="ogs-key ogs-key-primary" disabled={status !== 'correct' || physicalBusy} onClick={next}>{index + 1 >= lesson.step_count ? '完成本课' : '下一步'} ›</button></div>
    </section>
  </main>;
}
