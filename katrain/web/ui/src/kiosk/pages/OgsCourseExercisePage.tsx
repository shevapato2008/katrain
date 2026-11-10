import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { OgsCourseIndex, OgsStep, OgsPoint } from '../../types/ogsCourse';
import { actOgsExercise, chooseOgsAnswer, createOgsExercise, playOgsPoint, retryOgsExercise, type OgsExerciseState } from '../tutorial/ogsExercise';
import { OgsCourseBoard } from '../tutorial/OgsCourseBoard';
import { useOgsLocale } from '../tutorial/useOgsLocale';
import { useOgsPhysicalBoard } from '../tutorial/useOgsPhysicalBoard';
import { PhysicalBoardIcon } from '../shell/PhysicalBoardIcon';
import { backToState } from '../hooks/useBackTo';
import '../tutorial/ogs-course.css';

export default function OgsCourseExercisePage() {
  const navigate = useNavigate();
  const { language, text } = useOgsLocale();
  const location = useLocation();
  const { lessonId } = useParams<{ lessonId: string }>();
  const [course, setCourse] = useState<OgsCourseIndex | null>(null);
  const [courseError, setCourseError] = useState(false);
  const [courseReload, setCourseReload] = useState(0);
  const [index, setIndex] = useState(0);
  const [step, setStep] = useState<OgsStep | null>(null);
  const stepRef = useRef<OgsStep | null>(null);
  const [presentation, setPresentation] = useState<OgsStep | null>(null);
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
    TutorialReadAPI.getOgsCourse(language).then((data) => { if (live) { setCourse(data); setCourseError(false); } }).catch(() => { if (live) setCourseError(true); });
    return () => { live = false; };
  }, [language, courseReload]);
  useEffect(() => {
    if (expectedPage == null) return;
    let live = true;
    TutorialReadAPI.getOgsStep(expectedPage, language, 'kiosk19').then((data) => {
      if (!live) return;
      if (data.lesson_id !== lessonId || data.page !== expectedPage) { setStepError(true); return; }
      setPresentation(data); setStepError(false);
      // Translation refreshes update presentation only. Keep the judge tree,
      // current answer and physical-board machine anchored to the original step.
      if (stepRef.current?.page === data.page && stepRef.current.lesson_id === data.lesson_id) return;
      stepRef.current = data;
      setStep(data);
      const initial = createOgsExercise(data);
      answerRef.current = initial; setAnswer(initial); wrongBeforeRef.current = null;
    }).catch(() => { if (live) setStepError(true); });
    return () => { live = false; };
  }, [expectedPage, lessonId, language, stepReload]);
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
  const switchStep = (value: number) => { setPhysicalMode(false); stepRef.current = null; setStep(null); setPresentation(null); setAnswer(null); answerRef.current = null; setIndex(value); setRevision((n) => n + 1); };
  const back = () => navigate(chapter ? `/kiosk/tutorial/chapter/${encodeURIComponent(chapter.id)}` : '/kiosk/tutorial');
  if (!lesson || !chapter) return <main className="u-ogs ogs-state" data-testid="ogs-exercise-page"><button className="ogs-key" onClick={back}>‹ {text('course')}</button><h1>{text(courseError ? 'courseUnavailable' : course ? 'lessonMissing' : 'lessonLoading')}</h1>{courseError && <button className="ogs-key" onClick={() => { setCourseError(false); setCourseReload((n) => n + 1); }}>{text('retry')}</button>}</main>;
  if (!currentStep || !currentAnswer) return <main className="u-ogs ogs-state" data-testid="ogs-exercise-page"><button className="ogs-key" onClick={back}>‹ {text('lesson')}</button><h1>{text(stepError ? 'stepUnavailable' : 'stepLoading')}</h1>{stepError && <button className="ogs-key" onClick={() => { setStepError(false); setStepReload((n) => n + 1); }}>{text('retry')}</button>}</main>;
  const kind = currentStep.exercise.kind;
  const status = currentAnswer.status;
  const choose = (value: string) => { const next = chooseOgsAnswer(currentAnswer, value); answerRef.current = next; setAnswer(next); };
  const act = (action: 'pass' | 'finish') => { const next = actOgsExercise(currentAnswer, action); answerRef.current = next; setAnswer(next); };
  const phase = physical.physical.phase;
  const physicalBusy = physical.active && phase !== 'ready' && phase !== 'solved';
  const next = () => { if (status !== 'correct' || physicalBusy) return; if (index + 1 < lesson.step_count) switchStep(index + 1); else back(); };
  const extraCount = physical.physical.extra.length;
  const missingCount = physical.physical.missing.length;
  const physicalMessage = physical.active ? phase === 'clearing'
    ? text('clearBoard') + (extraCount ? text('remaining', { count: extraCount }) : '')
    : phase === 'setup' ? text('placeBoard', { player: text(physical.physical.stage === 'white' ? 'white' : 'black'), matched: physical.physical.stageMatched, total: physical.physical.stageTotal }) + (extraCount ? text('extra', { count: extraCount }) : '')
    : phase === 'replying' ? text('replyBoard')
    : phase === 'removing' ? text('wrongBoard', { count: extraCount }) + (missingCount ? text('restoreCaptured', { count: missingCount }) : '')
    : text(phase === 'restoring' ? 'restoreBoard' : phase === 'ready' ? 'readyBoard' : phase === 'solved' ? 'solvedBoard' : 'connectingBoard')
    : physical.reason || text('physicalHint');
  const displayedStep = presentation?.page === currentStep.page && presentation.lesson_id === currentStep.lesson_id ? presentation : currentStep;
  return <main className="u-ogs ogs-exercise" data-testid="ogs-exercise-page">
    <OgsCourseBoard step={currentStep} state={currentAnswer} onPoint={handleBoardPoint} disabled={physical.active && phase !== 'ready'} extra={physical.extra} />
    <section className="ogs-exercise-rail"><div className="ogs-exercise-title"><button className="ogs-key" onClick={back}>‹ {text('lesson')}</button><h2>{lesson.title}</h2></div>
      <div className="ogs-breadcrumb"><span>{text('breadcrumb', { chapter: chapter.number, lesson: lesson.order })}</span><span>{text('stepProgress', { step: index + 1, count: lesson.step_count })}</span></div>
      <div className="ogs-progress">{Array.from({ length: Math.min(lesson.step_count, 20) }, (_, i) => <i key={i} className={Math.floor(index * Math.min(lesson.step_count, 20) / lesson.step_count) === i ? 'is-current' : ''} />)}</div>
      {(stepError || courseError) && <p role="alert">{text('courseError')} <button className="ogs-key" onClick={() => { setStepReload(n => n + 1); setCourseReload(n => n + 1); }}>{text('retry')}</button></p>}
      <section className="ogs-card ogs-instruction"><span className="ogs-instruction-label">{text('thisExercise')}{currentStep.board_variant?.status === 'adapted' ? text('adapted', { size: currentStep.board_variant.source_size }) : ''}</span><p>{displayedStep.locale.text.instruction || displayedStep.locale.text.title}</p>{currentStep.board_variant?.status === 'unavailable' && <p data-testid="ogs-original-board-reason">{text('original', { size: currentStep.board_variant.source_size, reason: language === 'zh-cn' ? currentStep.board_variant.reason : text('originalReason') })}</p>}</section>
      <section className={`ogs-card ogs-interaction ${!physicalBusy && status === 'correct' ? 'is-success' : status === 'wrong' ? 'is-error' : ''}`}>
        <strong>{text(physicalBusy ? phase === 'clearing' || phase === 'setup' ? 'prepareBoard' : phase === 'replying' ? 'syncBoard' : phase === 'removing' ? 'removeWrong' : 'checkBoard' : status === 'correct' ? 'correct' : status === 'wrong' ? 'tryAgain' : kind === 'choice' ? 'choose' : kind === 'remove' ? 'remove' : kind === 'pass' ? 'passPrompt' : kind === 'finish' ? 'finishPrompt' : 'yourTurn')}</strong>
        {kind === 'choice' && status === 'active' && <div className="ogs-choice-row">{currentStep.exercise.kind === 'choice' && currentStep.exercise.choices.map((choice) => <button key={choice.value} className="ogs-key" onClick={() => choose(choice.value)}>{displayedStep.locale.text.choices?.[choice.value] ?? choice.label_key ?? choice.value}</button>)}</div>}
        {kind === 'pass' && status === 'active' && <button className="ogs-key ogs-inline-action" onClick={() => act('pass')}>{text('pass')}</button>}
        {kind === 'finish' && status === 'active' && <button className="ogs-key ogs-inline-action" onClick={() => act('finish')}>{text('finish')}</button>}
        {physicalBusy && <span>{physicalMessage}</span>}
        {status === 'wrong' && !physicalBusy && <button className="ogs-key ogs-inline-action" onClick={retry}>{text('retry')}</button>}
        {status === 'correct' && !physicalBusy && <span>{text(index + 1 >= lesson.step_count ? 'lessonDone' : 'continue')}</span>}
        {status === 'active' && kind === 'puzzle' && !physicalBusy && <span>{text('playPoint', { player: text(currentAnswer.player === 'B' ? 'black' : 'white') })}</span>}
        {status === 'active' && kind === 'remove' && <span>{text('removeNote')}</span>}
      </section>
      <div className="ogs-physical-hint" data-testid="ogs-physical-hint">{physical.active ? text('physicalEnabled') : physicalMessage}{physical.calibrate && <button className="ogs-calibrate" onClick={() => navigate('/kiosk/vision/setup', { state: backToState(location) })}>{text('calibrate')}</button>}{physical.active && !physical.physical.ledOk && <span>{text('ledOffline')}</span>}</div>
      <div className="ogs-exercise-actions"><button className="ogs-key" disabled={index === 0} onClick={() => switchStep(index - 1)}>‹ {text('previous')}</button><button className={`ogs-key ${physicalMode ? 'is-physical' : ''}`} aria-pressed={physicalMode} disabled={!physicalMode && !physical.available} onClick={() => setPhysicalMode((value) => !value)}><PhysicalBoardIcon />{text('physicalBoard')}</button><button className="ogs-key ogs-key-primary" disabled={status !== 'correct' || physicalBusy} onClick={next}>{text(index + 1 >= lesson.step_count ? 'complete' : 'next')} ›</button></div>
    </section>
  </main>;
}
