import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { OgsCourseIndex } from '../../types/ogsCourse';
import { useOgsLocale } from '../tutorial/useOgsLocale';
import '../tutorial/ogs-course.css';

export default function OgsCourseHomePage() {
  const navigate = useNavigate();
  const { language, text } = useOgsLocale();
  const [noticeOpen, setNoticeOpen] = useState(false);
  const [course, setCourse] = useState<OgsCourseIndex | null>(null);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let live = true;
    TutorialReadAPI.getOgsCourse(language).then((data) => { if (live) { setCourse(data); setError(false); } })
      .catch(() => { if (live) setError(true); });
    return () => { live = false; };
  }, [language, reload]);
  const retry = () => { setError(false); setReload(n => n + 1); };
  if (!course) return <main className="u-ogs ogs-state" data-testid="ogs-course-home"><h1>{text(error ? 'courseUnavailable' : 'courseLoading')}</h1>{error && <><p>{text('courseError')}</p><button className="ogs-key" onClick={retry}>{text('retry')}</button></>}<button className="ogs-key" onClick={() => navigate('/kiosk/tutorial/library')}>{text('otherBooks')}</button></main>;
  const first = course.chapters[0];
  return <main className="u-ogs ogs-home" data-testid="ogs-course-home">
    <section className="ogs-card ogs-hero">
      <span className="ogs-kicker">{text('interactive')}</span>
      <h1>{text('intro')}</h1><h2>OGS / Online-Go.com</h2>
      <p>{text('introNote')}</p>
      <div className="ogs-metrics"><span><strong>{course.counts.chapters}</strong>{text('chapters')}</span><span><strong>{course.counts.lessons}</strong>{text('lessons')}</span><span><strong>{course.counts.steps}</strong>{text('steps')}</span></div>
      <button className="ogs-key ogs-key-primary" disabled={!first} onClick={() => navigate(`/kiosk/tutorial/chapter/${encodeURIComponent(first.id)}`)}>{text('start')} ›</button>
      <button className="ogs-library-link" onClick={() => navigate('/kiosk/tutorial/library')}>{text('otherBooks')} ›</button>
      {error && <p role="alert">{text('courseError')} <button className="ogs-key" onClick={retry}>{text('retry')}</button></p>}
    </section>
    <section className="ogs-home-right"><div className="ogs-section-head"><h2>{text('contents')}</h2><span>{text('pickChapter')}</span></div><div className="ogs-chapter-grid">
      {course.chapters.map((chapter) => <button key={chapter.id} className="ogs-chapter" onClick={() => navigate(`/kiosk/tutorial/chapter/${encodeURIComponent(chapter.id)}`)}><span className="ogs-chapter-no">{String(chapter.number).padStart(2, '0')}</span><span className="ogs-chapter-copy"><strong>{chapter.title}</strong><em>{text('lessonSteps', { lessons: chapter.lesson_count, steps: chapter.step_count })}</em></span><span className="ogs-chapter-next" aria-hidden="true">›</span></button>)}
      <button className="ogs-source-card" onClick={() => setNoticeOpen(true)}>© OGS / Online-Go.com<br />AGPL-3.0-or-later · {text('source')} ›</button>
    </div></section>
    {noticeOpen && <div className="ogs-notice-backdrop"><section className="ogs-notice" role="dialog" aria-modal="true" aria-label={text('license')}>
      <h2>{text('license')}</h2><p>© OGS / Online-Go.com contributors<br />AGPL-3.0-or-later</p>
      <p>{text('sourceNote')}</p><p>{text('sourceArchive')} <a href="https://github.com/online-go/online-go.com" target="_blank" rel="noreferrer">online-go/online-go.com</a>.</p>
      <a className="ogs-key" href={`${__KIOSK_2D_ONLY__ ? '/api/v1/board/tutorials' : '/api/v1/tutorials'}/ogs-course/source.zip`}>{text('downloadSource')}</a>
      <button className="ogs-key" onClick={() => setNoticeOpen(false)}>{text('backCourse')}</button>
    </section></div>}
  </main>;
}
