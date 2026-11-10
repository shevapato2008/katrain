import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { OgsCourseIndex } from '../../types/ogsCourse';
import { useOgsLocale } from '../tutorial/useOgsLocale';
import '../tutorial/ogs-course.css';

export default function OgsCourseChapterPage() {
  const navigate = useNavigate();
  const { language, text } = useOgsLocale();
  const { chapterId } = useParams<{ chapterId: string }>();
  const [course, setCourse] = useState<OgsCourseIndex | null>(null);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let live = true;
    TutorialReadAPI.getOgsCourse(language).then((data) => { if (live) { setCourse(data); setError(false); } }).catch(() => { if (live) setError(true); });
    return () => { live = false; };
  }, [language, reload]);
  const retry = () => { setError(false); setReload(n => n + 1); };
  const chapter = course?.chapters.find((item) => item.id === chapterId);
  if (!course || !chapter) return <main className="u-ogs ogs-state" data-testid="ogs-chapter-page"><button className="ogs-key" onClick={() => navigate('/kiosk/tutorial')}>‹ {text('course')}</button><h1>{text(error ? 'chapterUnavailable' : course ? 'chapterMissing' : 'chapterLoading')}</h1>{error && <button className="ogs-key" onClick={retry}>{text('retry')}</button>}</main>;
  const lessons = course.lessons.filter((item) => item.chapter_id === chapter.id).sort((a, b) => a.order - b.order);
  return <main className="u-ogs ogs-lesson-layout" data-testid="ogs-chapter-page">
    <aside className="ogs-card ogs-chapter-rail"><div className="ogs-rail-head">{text('chapterPath', { count: course.chapters.length })}</div><div className="ogs-chapter-tabs">{course.chapters.map((item) => <button key={item.id} className={`ogs-chapter-tab ${item.id === chapterId ? 'is-current' : ''}`} aria-current={item.id === chapterId ? 'page' : undefined} onClick={() => navigate(`/kiosk/tutorial/chapter/${encodeURIComponent(item.id)}`)}><strong>{String(item.number).padStart(2, '0')}</strong>{item.title}</button>)}</div></aside>
    <section className="ogs-lesson-main"><div className="ogs-lesson-head"><button className="ogs-key" onClick={() => navigate('/kiosk/tutorial')}>‹ {text('course')}</button><h2>{chapter.title}</h2><span className="ogs-meta">{text('chapterProgress', { chapter: chapter.number, count: course.chapters.length })}</span></div><div className="ogs-lesson-sub"><span>{text('chapterNote')}</span><span>{text('lessonSteps', { lessons: chapter.lesson_count, steps: chapter.step_count })}</span></div>
      {error && <p role="alert">{text('courseError')} <button className="ogs-key" onClick={retry}>{text('retry')}</button></p>}
      <div className="ogs-lesson-list">{lessons.map((lesson) => <button key={lesson.id} className="ogs-lesson" onClick={() => navigate(`/kiosk/tutorial/lesson/${encodeURIComponent(lesson.id)}`)}><span className="ogs-lesson-number">{String(lesson.order).padStart(2, '0')}</span><span className="ogs-lesson-copy"><strong>{lesson.title}</strong><span>{lesson.subtext || text('practiceSteps', { count: lesson.step_count })}</span></span><span className="ogs-lesson-next" aria-hidden="true">›</span></button>)}</div></section>
  </main>;
}
