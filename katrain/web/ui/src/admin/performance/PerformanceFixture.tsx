import { useState } from 'react';
import { Activity, BookOpen, Clock3 } from 'lucide-react';
import galaxyLogo from '../../../../../img/logo-white.png';
import PerformancePage from './PerformancePage';
import '../AdminApp.css';
import './PerformanceFixture.css';

const params = new URLSearchParams(window.location.search);

export default function PerformanceFixture() {
  const [previewState, setPreviewState] = useState<'unconnected' | 'connected'>(
    params.get('state') === 'connected' ? 'connected' : 'unconnected',
  );
  const [theme, setTheme] = useState<'dark' | 'light'>(params.get('theme') === 'light' ? 'light' : 'dark');
  const capture = params.get('capture') === 'true';

  return <div className="admin-app admin-app-cron admin-performance-fixture" data-testid="performance-fixture" data-theme={theme}>
    <header className="admin-top">
      <div className="admin-brand" aria-label="KaTrain 管理后台"><img src={galaxyLogo} alt="" /><span className="admin-brand-cn">智星盒</span><span className="admin-brand-en">StellaBox</span><span className="admin-brand-admin">管理后台</span></div>
      <div className="admin-topright"><span className="admin-env" data-env="test">测试环境</span><span>admin:fan</span><span className="performance-fixture-signout">退出</span></div>
    </header>
    <div className="admin-wrap">
      <aside className="admin-side" aria-label="管理导航"><div className="admin-sidehead">内容与服务</div>
        <span className="admin-nav"><BookOpen aria-hidden="true" />教程管理</span>
        <span className="admin-nav"><Clock3 aria-hidden="true" />定时任务</span>
        <span className="admin-nav active"><Activity aria-hidden="true" />性能监控</span>
        <div className="admin-sidefoot">当前环境：测试环境<br />只读页面，不修改配置。</div>
      </aside>
      <PerformancePage previewState={previewState} />
    </div>
    {!capture && <div className="performance-fixture-tweaks" aria-label="Fixture 预览选项">
      <span>预览</span>
      <button type="button" onClick={() => setPreviewState((state) => state === 'connected' ? 'unconnected' : 'connected')}>{previewState === 'connected' ? '未接入状态' : '已配置示意'}</button>
      <button type="button" onClick={() => setTheme((value) => value === 'dark' ? 'light' : 'dark')}>{theme === 'dark' ? '白天版本' : '夜间版本'}</button>
    </div>}
  </div>;
}
