import { useState } from 'react';
import { Activity, AlertTriangle, ExternalLink, Info, RefreshCw } from 'lucide-react';
import type { PerformanceConfig } from '../api/client';
import '../vision/lab.css';
import './PerformancePage.css';

type Props = { config: PerformanceConfig | null; environmentLabel: string; busy: boolean; error: string; onRetry: () => void };

// Grafana keeps its own login; the admin token is never handed to the frame.
const SANDBOX = 'allow-scripts allow-same-origin allow-forms allow-popups';

export default function PerformancePage({ config, environmentLabel, busy, error, onRetry }: Props) {
  const [selected, setSelected] = useState('0');
  const configured = config?.state === 'configured';
  const dashboard = configured ? config.dashboards.find((item) => item.id === selected) ?? config.dashboards[0] : undefined;
  const heading = !config ? (busy ? '读取配置' : '配置未读取') : configured ? `已配置 ${config.dashboards.length} 个看板` : config.state === 'invalid' ? '配置无效' : '尚未接入';
  const detail = !config ? (busy ? '正在读取本环境的看板配置' : '无法确认本环境是否配置了 Grafana')
    : configured ? '本页不探测 Grafana；看板能否显示以下方画面为准'
      : config.state === 'invalid' ? '看板配置有误，本页不嵌入任何地址' : '本环境没有配置 Grafana 看板';
  return <main className="lab-page pf-page">
    <div className="lab-heading"><div><h1>性能监控</h1><p>在后台内查看主机与容器运行状态</p></div><span className="lab-status"><Info aria-hidden="true" />Grafana 嵌入看板</span></div>
    <div className="lab-content">
      {error && <div className="lab-banner bad" role="alert"><AlertTriangle aria-hidden="true" /><span>读取看板配置失败：{error}</span><button className="lab-btn small" type="button" onClick={onRetry} disabled={busy}><RefreshCw aria-hidden="true" />重试</button></div>}
      <section className="lab-panel pf-status" aria-labelledby="pf-status-title">
        <div className="pf-lead"><div className={`pf-mark ${config?.state === 'invalid' ? 'bad' : ''}`}><Activity aria-hidden="true" /></div><div>
          <div className="lab-note">Grafana 看板</div><h2 id="pf-status-title">{heading}</h2><p>{detail}</p>
        </div></div>
        <span className={`lab-chip ${config?.state === 'invalid' ? 'bad' : 'info'}`}>{configured ? '已配置 · 未探测在线' : config?.state === 'invalid' ? '配置无效' : '状态未知'}</span>
      </section>
      <div className="pf-grid">
        <section className="lab-panel pf-monitor" aria-labelledby="pf-monitor-title">
          <div className="lab-panel-head"><h2 id="pf-monitor-title">内嵌监控看板</h2><small>主机 · 容器 · 存储</small></div>
          <div className="pf-board">
            {configured && dashboard ? <div className="pf-embed">
              <div className="pf-embed-top">
                <label><Activity aria-hidden="true" />Grafana ／<select aria-label="选择看板" value={dashboard.id} onChange={(event) => setSelected(event.target.value)}>{config.dashboards.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>
                <a className="lab-btn small" href={dashboard.url} target="_blank" rel="noreferrer noopener"><ExternalLink aria-hidden="true" />新标签打开</a>
              </div>
              <iframe key={dashboard.id} className="pf-frame" title={`Grafana 看板：${dashboard.title}`} src={dashboard.url} sandbox={SANDBOX} referrerPolicy="no-referrer" />
            </div> : <div className="pf-empty">
              {config?.state === 'invalid' ? <AlertTriangle className="bad" aria-hidden="true" /> : <Info aria-hidden="true" />}
              <h3>{config?.state === 'invalid' ? '看板配置无效' : '暂无性能数据'}</h3>
              {config?.state === 'invalid' ? <p className="pf-error">{config.error}</p>
                : <p>{config ? '在后台进程的环境里设置 KATRAIN_ADMIN_GRAFANA_DASHBOARDS（看板标题与地址的 JSON 列表）后重启，实时看板会直接显示在此处。' : '配置读取成功后，这里会显示看板或接入说明。'}</p>}
            </div>}
          </div>
        </section>
        <aside className="lab-panel pf-aside" aria-label="接入信息">
          <div className="lab-panel-head"><h2>接入信息</h2></div>
          <dl className="pf-facts">
            <div><dt>当前环境</dt><dd>{environmentLabel}</dd></div>
            <div><dt>监控服务</dt><dd className={configured ? '' : 'muted'}>{configured ? 'Grafana' : '未配置'}</dd></div>
            <div><dt>嵌入来源</dt><dd className={configured ? 'mono' : 'muted'}>{configured ? config.origin : '—'}</dd></div>
            <div><dt>在线状态</dt><dd className="muted">本页不探测，以看板画面为准</dd></div>
          </dl>
          <p className="lab-note pf-foot"><Info aria-hidden="true" />只允许嵌入配置里的这一个来源。Grafana 需开启 allow_embedding 并保留自身登录；后台令牌不会传给 Grafana。</p>
        </aside>
      </div>
    </div>
  </main>;
}
