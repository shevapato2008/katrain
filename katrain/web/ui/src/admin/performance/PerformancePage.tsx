import { Activity, Info, Link2 } from 'lucide-react';
import './PerformancePage.css';

type Props = { previewState: 'unconnected' | 'connected' };

const previewPanels = ['CPU', '内存', '磁盘', '容器'];

export default function PerformancePage({ previewState }: Props) {
  const connected = previewState === 'connected';
  return <main className="performance-page" data-preview-state={previewState}>
    <div className="performance-heading">
      <div><h1>性能监控</h1><p>在后台内查看主机与容器运行状态</p></div>
      <div className="performance-heading-note"><Info aria-hidden="true" />Grafana 嵌入看板</div>
    </div>
    <div className="performance-content">
      <p className="performance-demo-note">Fixture 预览 · 两种状态仅供视觉比较，不连接真实监控服务</p>
      <section className="performance-status" aria-labelledby="performance-status-title">
        <div className="performance-status-leading"><div className="performance-status-mark"><Activity aria-hidden="true" /></div><div>
          <div className="performance-eyebrow">Grafana 看板</div>
          <h2 id="performance-status-title">{connected ? '嵌入布局预览' : '尚未接入'}</h2>
          <p>{connected ? '设计示例 · 不是实时画面，也不代表服务在线' : '尚未验证当前环境是否部署 Grafana 服务'}</p>
        </div></div>
        <span className="performance-status-pill">{connected ? <Link2 aria-hidden="true" /> : <Info aria-hidden="true" />}{connected ? '仅设计示意' : '状态未知'}</span>
      </section>
      <div className="performance-body-grid">
        <section className="performance-monitor" aria-labelledby="performance-monitor-title">
          <div className="performance-panel-head"><h2 id="performance-monitor-title">内嵌监控看板</h2><span>主机 · 容器 · 存储</span></div>
          <div className="performance-monitor-body">
            {connected ? <div className="performance-embedded" aria-label="Grafana 嵌入布局设计示意；无实时数据">
              <div className="performance-embedded-top"><div className="performance-embedded-brand"><Activity aria-hidden="true" />Grafana <span>／ 主机概览</span></div><span>时间范围与刷新控件由 Grafana 提供</span></div>
              <div className="performance-embedded-canvas">{previewPanels.map((name) => <div className="performance-embedded-panel" key={name}><strong>{name}</strong><span>暂无实时数据 · 设计占位</span></div>)}</div>
              <div className="performance-embedded-caption">本图仅展示 Grafana 在后台内的位置，不是实际 Grafana 页面</div>
            </div> : <div className="performance-placeholder">
              <Info aria-hidden="true" /><h3>暂无性能数据</h3>
              <p>目前没有可确认的 Grafana 端点。完成服务与访问控制核实后，实时看板会直接显示在此处。</p>
            </div>}
          </div>
        </section>
        <aside className="performance-aside" aria-label="访问与安全信息">
          <h2>接入信息</h2>
          <dl className="performance-facts">
            <div><dt>当前环境</dt><dd>测试环境</dd></div>
            <div><dt>监控服务</dt><dd className={connected ? '' : 'muted'}>{connected ? 'Grafana（设计示意）' : '尚未核实'}</dd></div>
            <div><dt>嵌入地址</dt><dd className={connected ? '' : 'muted'}>{connected ? '待服务核实后配置' : '待确认'}</dd></div>
            <div><dt>最近验证</dt><dd className={connected ? '' : 'muted'}>{connected ? '尚未实际验证' : '尚无验证记录'}</dd></div>
          </dl>
          <div className="performance-aside-foot"><Info aria-hidden="true" />实际嵌入需先核实 Grafana 鉴权与浏览器策略；后台令牌不会传给 Grafana。</div>
        </aside>
      </div>
    </div>
  </main>;
}
