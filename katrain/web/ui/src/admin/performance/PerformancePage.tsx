import { Activity, ExternalLink, Info, Link2 } from 'lucide-react';
import './PerformancePage.css';

type Props = { previewState: 'unconnected' | 'connected' };

export default function PerformancePage({ previewState }: Props) {
  const connected = previewState === 'connected';
  return <main className="performance-page" data-preview-state={previewState}>
    <div className="performance-heading">
      <div><h1>性能监控</h1><p>查看当前环境的主机与容器运行状态</p></div>
      <div className="performance-heading-note"><Info aria-hidden="true" />监控服务独立于管理后台</div>
    </div>
    <div className="performance-content">
      <p className="performance-demo-note">Fixture 预览 · 两种状态仅供视觉比较，不连接真实监控服务</p>
      <section className="performance-status" aria-labelledby="performance-status-title">
        <div className="performance-status-leading"><div className="performance-status-mark"><Activity aria-hidden="true" /></div><div>
          <div className="performance-eyebrow">监控来源</div>
          <h2 id="performance-status-title">{connected ? 'Netdata 面板已配置' : '尚未接入'}</h2>
          <p>{connected ? '设计示例 · 此处不代表真实服务在线' : '尚未验证当前环境是否部署监控服务'}</p>
        </div></div>
        <span className="performance-status-pill">{connected ? <Link2 aria-hidden="true" /> : <Info aria-hidden="true" />}{connected ? '仅示意配置' : '状态未知'}</span>
      </section>
      <div className="performance-body-grid">
        <section className="performance-monitor" aria-labelledby="performance-monitor-title">
          <div className="performance-panel-head"><h2 id="performance-monitor-title">监控面板</h2><span>主机 · 容器 · 存储</span></div>
          <div className="performance-monitor-body">
            {connected ? <div className="performance-placeholder performance-verified">
              <h3><Activity aria-hidden="true" />在独立面板查看实时指标</h3>
              <p>主机 CPU、内存、磁盘和容器曲线由监控服务显示；后台不复制其登录态，也不展示未经采集验证的数字。</p>
              <button className="performance-button primary" type="button" disabled><ExternalLink aria-hidden="true" />打开 Netdata 面板</button>
              <small>设计示例：按钮在真实地址和访问控制验证后才启用</small>
            </div> : <div className="performance-placeholder performance-empty">
              <Info aria-hidden="true" /><h3>暂无性能数据</h3>
              <p>目前没有可确认的监控端点。接入并核实服务后，才会开放当前环境的监控入口。</p>
              <button className="performance-button" type="button" disabled>打开监控面板</button>
            </div>}
          </div>
        </section>
        <aside className="performance-aside" aria-label="访问与安全信息">
          <h2>访问方式</h2>
          <dl className="performance-facts">
            <div><dt>当前环境</dt><dd>测试环境</dd></div>
            <div><dt>监控服务</dt><dd className={connected ? '' : 'muted'}>{connected ? 'Netdata（示例）' : '尚未配置'}</dd></div>
            <div><dt>本机入口</dt><dd className={connected ? '' : 'muted'}>{connected ? '127.0.0.1:19999（示例）' : '待确认'}</dd></div>
            <div><dt>最近验证</dt><dd className={connected ? '' : 'muted'}>{connected ? '尚未实际验证' : '尚无验证记录'}</dd></div>
          </dl>
          <div className="performance-aside-foot"><Info aria-hidden="true" />监控端口只允许经 SSH 隧道访问；不向监控页面传递后台登录令牌。</div>
        </aside>
      </div>
    </div>
  </main>;
}
