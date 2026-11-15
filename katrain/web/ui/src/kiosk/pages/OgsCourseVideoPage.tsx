import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { TutorialReadAPI } from '../../api/tutorialApi';
import type { OgsCourseIndex } from '../../types/ogsCourse';
import { videosForLesson } from '../../types/ogsVideo';
import { useOgsLocale } from '../tutorial/useOgsLocale';
import { useOgsVideos } from '../tutorial/useOgsVideos';
import '../tutorial/ogs-course.css';

export default function OgsCourseVideoPage() {
  const { lessonId } = useParams<{ lessonId: string }>();
  return <LessonVideos key={lessonId} lessonId={lessonId} />;
}

function LessonVideos({ lessonId }: { lessonId?: string }) {
  const navigate = useNavigate();
  const { language, text } = useOgsLocale();
  const videos = useOgsVideos();
  const [course, setCourse] = useState<OgsCourseIndex | null>(null);
  const [courseError, setCourseError] = useState(false);
  const [courseRevision, setCourseRevision] = useState(0);
  const [index, setIndex] = useState(0);
  const [playbackError, setPlaybackError] = useState(false);
  const [finished, setFinished] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [playerRevision, setPlayerRevision] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const playerRef = useRef<HTMLElement>(null);
  const clips = videosForLesson(videos.manifest, lessonId);
  const clip = clips[index] ?? clips[0];
  const lesson = course?.lessons.find(item => item.id === lessonId);
  const selectClip = (nextIndex: number) => {
    setIndex(nextIndex); setPlaybackError(false); setFinished(false);
  };
  const back = () => navigate(lesson
    ? `/kiosk/tutorial/chapter/${encodeURIComponent(lesson.chapter_id)}` : '/kiosk/tutorial');
  const practice = () => {
    videoRef.current?.pause();
    if (lesson) navigate(`/kiosk/tutorial/lesson/${encodeURIComponent(lesson.id)}`);
  };
  const fullscreen = () => {
    setExpanded(true);
    void playerRef.current?.requestFullscreen?.().catch(() => undefined);
    void videoRef.current?.play().catch(() => setPlaybackError(true));
  };
  const exitFullscreen = () => {
    setExpanded(false);
    if (document.fullscreenElement === playerRef.current) void document.exitFullscreen().catch(() => undefined);
  };
  const ended = () => {
    if (index + 1 < clips.length) selectClip(index + 1);
    else {
      setFinished(true);
      exitFullscreen();
    }
  };
  useEffect(() => {
    let live = true;
    TutorialReadAPI.getOgsCourse(language).then(data => {
      if (live) { setCourse(data); setCourseError(false); }
    }).catch(() => { if (live) setCourseError(true); });
    return () => { live = false; };
  }, [language, courseRevision]);
  useEffect(() => {
    const element = videoRef.current;
    return () => { element?.pause(); };
  }, [clip?.id, playerRevision, lesson?.id]);
  if (!lesson) return <main className="u-ogs ogs-state">
    <button className="ogs-key" onClick={back}>‹ {text('course')}</button>
    <h1>{text(courseError ? 'courseUnavailable' : course ? 'lessonMissing' : 'lessonLoading')}</h1>
    {courseError && <button className="ogs-key" onClick={() => { setCourseError(false); setCourseRevision(n => n + 1); }}>{text('retry')}</button>}
  </main>;
  return <main className="u-ogs ogs-video-page" data-testid="ogs-video-page">
    <header className="ogs-video-header">
      <button className="ogs-key" onClick={back}>‹ {text('videoBack')}</button>
      <h2>{lesson.title} · {text('videoLesson')}</h2>
      <button className="ogs-key ogs-key-primary" onClick={practice}>{text('videoPractice')}</button>
    </header>
    {videos.loading ? <section className="ogs-video-state" role="status">{text('videoLoading')}</section>
      : videos.error ? <section className="ogs-video-state" role="alert">
        <p>{text('videoCatalogError')}</p><button className="ogs-key" onClick={videos.retry}>{text('videoCatalogRetry')}</button>
      </section>
      : !clip ? <section className="ogs-video-state">{text('videoMissing')}</section>
      : <>
        <section className={`ogs-video-player${expanded ? ' is-expanded' : ''}`} ref={playerRef}>
          <button className="ogs-key ogs-video-exit" onClick={exitFullscreen}>{text('videoExitFullscreen')}</button>
          <video key={`${clip.id}-${playerRevision}`} ref={videoRef} data-testid="ogs-lesson-video"
            aria-label={clip.title} src={clip.profiles['kiosk-7-v1'].url} poster={clip.poster_url}
            controls playsInline preload="metadata" autoPlay={index > 0}
            onError={() => setPlaybackError(true)}
            onEnded={ended} />
          {playbackError && <div className="ogs-video-notice" role="alert">
            <p>{text('videoPlaybackError')}</p>
            <button className="ogs-key" onClick={() => { setPlaybackError(false); setPlayerRevision(n => n + 1); }}>{text('videoPlaybackRetry')}</button>
            <button className="ogs-key ogs-key-primary" onClick={practice}>{text('videoPractice')}</button>
          </div>}
        </section>
        <div className="ogs-video-source">{clip.book} · PDF {clip.page} · {text('videoMandarin')}</div>
        <footer className="ogs-video-controls">
          <button className="ogs-key" disabled={index === 0} onClick={() => selectClip(index - 1)}>‹ {text('videoPrevious')}</button>
          <label className="ogs-video-picker"><span>{text('videoSelect')}</span>
            <select aria-label={text('videoSelect')} value={clip.id} onChange={event => selectClip(clips.findIndex(item => item.id === Number(event.target.value)))}>
              {clips.map((item, i) => <option key={item.id} value={item.id}>{i + 1}/{clips.length} · {item.title}</option>)}
            </select>
          </label>
          <button className="ogs-key" onClick={fullscreen}>{text('videoFullscreen')}</button>
          <button className="ogs-key" disabled={index + 1 >= clips.length} onClick={() => selectClip(index + 1)}>{text('videoNext')} ›</button>
        </footer>
        <div className="ogs-video-status" role="status">{finished ? text('videoFinished') : clip.title}</div>
      </>}
  </main>;
}
