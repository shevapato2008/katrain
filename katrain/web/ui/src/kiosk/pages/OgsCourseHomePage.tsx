import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { OgsCourseIndex } from '../../types/ogsCourse';
import '../tutorial/ogs-course.css';

export default function OgsCourseHomePage() {
  const navigate = useNavigate();
  const [course, setCourse] = useState<OgsCourseIndex | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let live = true;
    TutorialReadAPI.getOgsCourse().then((data) => { if (live) { setCourse(data); setError(null); } })
      .catch((cause: unknown) => { if (live) setError(cause instanceof Error ? cause.message : String(cause)); });
    return () => { live = false; };
  }, [reload]);
  if (!course) return <main className="u-ogs ogs-state" data-testid="ogs-course-home"><h1>{error ? '课程暂不可用' : '正在读取课程'}</h1>{error && <><p>目前无法读取 OGS 教程，请稍后重试。</p><button className="ogs-key" onClick={() => { setError(null); setReload((n) => n + 1); }}>重试</button></>}<button className="ogs-key" onClick={() => navigate('/kiosk/tutorial/library')}>其他教材</button></main>;
  const first = course.chapters[0];
  return <main className="u-ogs ogs-home" data-testid="ogs-course-home">
    <section className="ogs-card ogs-hero">
      <span className="ogs-kicker">边学边下 · 互动教程</span>
      <h1>围棋入门</h1><h2>{course.title}</h2>
      <p>从第一手落子开始，逐章掌握规则与基本技巧。</p>
      <div className="ogs-metrics"><span><strong>{course.counts.chapters.toLocaleString('zh-CN')}</strong>章节</span><span><strong>{course.counts.lessons.toLocaleString('zh-CN')}</strong>课目</span><span><strong>{course.counts.steps.toLocaleString('zh-CN')}</strong>练习步骤</span></div>
      <button className="ogs-key ogs-key-primary" disabled={!first} onClick={() => navigate(`/kiosk/tutorial/chapter/${encodeURIComponent(first.id)}`)}>开始第一章 ›</button>
      <button className="ogs-library-link" onClick={() => navigate('/kiosk/tutorial/library')}>其他教材 ›</button>
    </section>
    <section className="ogs-home-right"><div className="ogs-section-head"><h2>课程目录</h2><span>选一章开始</span></div><div className="ogs-chapter-grid">
      {course.chapters.map((chapter) => <button key={chapter.id} className="ogs-chapter" onClick={() => navigate(`/kiosk/tutorial/chapter/${encodeURIComponent(chapter.id)}`)}><span className="ogs-chapter-no">{String(chapter.number).padStart(2, '0')}</span><span className="ogs-chapter-copy"><strong>{chapter.title}</strong><em>{chapter.lesson_count.toLocaleString('zh-CN')} 课 · {chapter.step_count.toLocaleString('zh-CN')} 步</em></span><span className="ogs-chapter-next" aria-hidden="true">›</span></button>)}
    </div></section>
  </main>;
}
