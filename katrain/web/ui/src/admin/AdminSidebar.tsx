import { Activity, BookOpen, CircleCheck, Cpu, Database, TriangleAlert, ShieldCheck, Users, Camera, ChevronRight, Clock3 } from 'lucide-react';
import { isLabPage, type AdminPage } from './adminPages';

const LAB: { id: AdminPage; label: string }[] = [
  { id: 'capture', label: '采集与数据集' },
  { id: 'training', label: '训练与模型' },
  { id: 'diagnostics', label: '本机部署与诊断' },
];
const FOOT: Record<AdminPage, string> = {
  tutorial: '修改会写入该环境的教程数据',
  cron: '暂停、恢复与立即运行会写入审计。',
  performance: '只读页面，不修改配置。',
  users: '调整积分与生成兑换码会写入该环境的主库。',
  audit: '只读页面。',
  health: '只读页面，不修改配置。',
  errors: '标记已解决会写入审计。',
  devices: '批准与拒绝会写入审计。',
  artifacts: '发布、撤回与下载链接会写入审计。',
  capture: '相机、指示灯与训练帧只在 Mac 本机使用。',
  training: '训练运行在测试机；本页不会暗中连接远端。',
  diagnostics: 'viewer 只读观察，不提交棋步、不驱动指示灯。',
};

type Props = {
  attention?: { errors: number; config: number } | null;
  page: AdminPage; labOpen: boolean; environmentLabel: string;
  onPage: (page: AdminPage) => void; onToggleLab: () => void;
};
export default function AdminSidebar({ attention, page, labOpen, environmentLabel, onPage, onToggleLab }: Props) {
  const inLab = isLabPage(page);
  const nav = (id: AdminPage, Icon: typeof BookOpen, text: string, badge = 0) => (
    <button type="button" className={`admin-nav ${page === id ? 'active' : ''}`} aria-current={page === id ? 'page' : undefined} onClick={() => onPage(id)}><Icon aria-hidden="true" />{text}{badge > 0 && <span className="admin-nav-badge" aria-label={`${badge} 项需要关注`}>{badge}</span>}</button>
  );
  return <aside className="admin-side" aria-label="管理导航">
    <div className="admin-sidehead">内容与服务</div>
    {nav('tutorial', BookOpen, '教程管理')}
    {nav('cron', Clock3, '定时任务')}
    {nav('performance', Activity, '性能监控')}
    {nav('users', Users, '用户与计费')}
    {nav('audit', ShieldCheck, '审计日志')}
    {nav('health', CircleCheck, '配置体检', attention?.config)}
    {nav('devices', Cpu, '盒子设备')}
    {nav('artifacts', Database, '金镜像')}
    {nav('errors', TriangleAlert, '报错追踪', attention?.errors)}
    <button type="button" className={`admin-nav ${inLab && !labOpen ? 'active' : ''}`} aria-expanded={labOpen} aria-controls="admin-lab-subnav" onClick={onToggleLab}><Camera aria-hidden="true" />视觉实验室<ChevronRight className="admin-nav-chev" aria-hidden="true" /></button>
    {labOpen && <div className="admin-subnav" id="admin-lab-subnav">
      {LAB.map((item, index) => <button key={item.id} type="button" aria-current={page === item.id ? 'page' : undefined} onClick={() => onPage(item.id)}><b>{index + 1}</b>{item.label}</button>)}
    </div>}
    <div className="admin-sidefoot">当前环境：{environmentLabel}<br />{FOOT[page]}</div>
  </aside>;
}
