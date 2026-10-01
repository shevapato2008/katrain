import { useState } from 'react';
import { AlertTriangle, Info, Ticket, Users } from 'lucide-react';
import type { createAdminApi } from '../api/client';
import CodesTab from './CodesTab';
import UsersTab from './UsersTab';
import '../vision/lab.css';
import './UsersPage.css';

type Props = { api: ReturnType<typeof createAdminApi>; environment: string; environmentLabel: string; onUnauthorized: () => void };

export default function UsersBillingPage({ api, environment, environmentLabel, onUnauthorized }: Props) {
  const [tab, setTab] = useState<'users' | 'codes'>('users');
  const production = environment === 'prod';
  return <main className="lab-page ub-page">
    <div className="lab-heading"><div><h1>用户与计费</h1><p>查看账户与积分账本，调整余额、生成兑换码；每次写入都记审计</p></div>
      <span className={`lab-status ${production ? 'bad' : ''}`}>{production ? <AlertTriangle aria-hidden="true" /> : <Info aria-hidden="true" />}{production ? '生产环境 · 写入即真实生效' : `${environmentLabel} · 写入会改这个环境的库`}</span></div>
    <div className="lab-content">
      <div className="lab-panel"><div className="lab-tabs" role="tablist">
        <button className="lab-tab" type="button" role="tab" aria-selected={tab === 'users'} onClick={() => setTab('users')}><Users aria-hidden="true" />用户</button>
        <button className="lab-tab" type="button" role="tab" aria-selected={tab === 'codes'} onClick={() => setTab('codes')}><Ticket aria-hidden="true" />兑换码</button>
      </div></div>
      {tab === 'users' ? <UsersTab api={api} production={production} onUnauthorized={onUnauthorized} /> : <CodesTab api={api} production={production} onUnauthorized={onUnauthorized} />}
    </div>
  </main>;
}
