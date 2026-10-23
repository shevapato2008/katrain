import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { OgsCourseIndex } from '../../types/ogsCourse';
import '../tutorial/ogs-course.css';

export default function OgsCourseChapterPage() {
  const navigate = useNavigate();
  const { chapterId } = useParams<{ chapterId: string }>();
  const [course, setCourse] = useState<OgsCourseIndex | null>(null);
  const [error, setError] = useState(false);
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let live = true;
    TutorialReadAPI.getOgsCourse().then((data) => { if (live) { setCourse(data); setError(false); } }).catch(() => { if (live) setError(true); });
    return () => { live = false; };
  }, [reload]);
  const chapter = course?.chapters.find((item) => item.id === chapterId);
  if (!course || !chapter) return <main className="u-ogs ogs-state" data-testid="ogs-chapter-page"><button className="ogs-key" onClick={() => navigate('/kiosk/tutorial')}>‹ 课程</button><h1>{error ? '章节暂不可用' : course ? '没有找到这一章' : '正在读取章节'}</h1>{error && <button className="ogs-key" onClick={() => { setError(false); setReload((n) => n + 1); }}>重试</button>}</main>;
  const lessons = course.lessons.filter((item) => item.chapter_id === chapter.id).sort((a, b) => a.order - b.order);
  return <main className="u-ogs ogs-lesson-layout" data-testid="ogs-chapter-page">
    <aside className="ogs-card ogs-chapter-rail"><div className="ogs-rail-head">{course.chapters.length}章学习路径</div><div className="ogs-chapter-tabs">{course.chapters.map((item) => <button key={item.id} className={`ogs-chapter-tab ${item.id === chapterId ? 'is-current' : ''}`} aria-current={item.id === chapterId ? 'page' : undefined} onClick={() => navigate(`/kiosk/tutorial/chapter/${encodeURIComponent(item.id)}`)}><strong>{String(item.number).padStart(2, '0')}</strong>{item.title}</button>)}</div></aside>
    <section className="ogs-lesson-main"><div className="ogs-lesson-head"><button className="ogs-key" onClick={() => navigate('/kiosk/tutorial')}>‹ 课程</button><h2>{chapter.title}</h2><span className="ogs-meta">第 {chapter.number} 章 / 共 {course.chapters.length} 章</span></div><div className="ogs-lesson-sub"><span>按顺序学习，也可以点选任意课目</span><span>{chapter.lesson_count} 课 · {chapter.step_count} 步</span></div><div className="ogs-lesson-list">{lessons.map((lesson) => <button key={lesson.id} className="ogs-lesson" onClick={() => navigate(`/kiosk/tutorial/lesson/${encodeURIComponent(lesson.id)}`)}><span className="ogs-lesson-number">{String(lesson.order).padStart(2, '0')}</span><span className="ogs-lesson-copy"><strong>{lesson.title}</strong><span>{lesson.subtext || `${lesson.step_count} 步互动练习`}</span></span><span aria-hidden="true">›</span></button>)}</div></section>
  </main>;
}
