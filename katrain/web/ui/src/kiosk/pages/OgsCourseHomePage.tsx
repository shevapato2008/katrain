import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { OgsCourseIndex } from '../../types/ogsCourse';
import '../tutorial/ogs-course.css';

export default function OgsCourseHomePage() {
  const navigate = useNavigate();
  const [noticeOpen, setNoticeOpen] = useState(false);
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
      <button className="ogs-source-card" onClick={() => setNoticeOpen(true)}>© OGS / Online-Go.com<br />AGPL-3.0-or-later · 来源与许可 ›</button>
    </div></section>
    {noticeOpen && <div className="ogs-notice-backdrop"><section className="ogs-notice" role="dialog" aria-modal="true" aria-label="课程来源与许可">
      <h2>课程来源与许可</h2>
      <p>© OGS / Online-Go.com contributors<br />AGPL-3.0-or-later</p>
      <p>本课程改编自 OGS 围棋教程，保留原始来源版本与全部翻译。2026-10-24 改动：合并重复初始棋子、映射课程目录，将练习转换为独立 SGF 与结构化 JSON。</p>
      <p>源码包含对应课程源数据、原始来源证据、全部翻译、SGF、完整许可证及改动说明。原始项目：<a href="https://github.com/online-go/online-go.com" target="_blank" rel="noreferrer">online-go/online-go.com</a>。</p>
      <a className="ogs-key" href={`${__KIOSK_2D_ONLY__ ? '/api/v1/board/tutorials' : '/api/v1/tutorials'}/ogs-course/source.zip`}>下载源码与许可证</a>
      <button className="ogs-key" onClick={() => setNoticeOpen(false)}>返回课程</button>
    </section></div>}
  </main>;
}
