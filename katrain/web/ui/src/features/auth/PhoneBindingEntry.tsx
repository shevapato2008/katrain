import { useEffect, useRef, useState } from 'react';
import { Box, Button, Typography } from '@mui/material';
import { API, type PhoneBindingStatus } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { isStrictBoxKiosk as strictBuild, leaveToLauncher } from '../../kiosk/shell/boxUrls';
import PhoneBindDialog, { canBindPhone } from './PhoneBindDialog';

export default function PhoneBindingEntry({ kiosk = false }: { kiosk?: boolean }) {
  const { user, isGuest, isStrictBoxKiosk, identityKey, token } = useAuth();
  const { t } = useTranslation();
  const eligible = canBindPhone(user, isGuest);
  const strict = isStrictBoxKiosk || strictBuild;
  const currentIdentity = useRef({ identityKey, token }); currentIdentity.current = { identityKey, token };
  const [snapshot, setSnapshot] = useState<{ identityKey: string | null; token: string | null; status: PhoneBindingStatus | null; error: boolean } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [open, setOpen] = useState(false);
  const [container, setContainer] = useState<HTMLElement | null>(null);
  useEffect(() => {
    setOpen(false); setSnapshot(null);
    if (!eligible || strict) return;
    const request = new AbortController(); const captured = { identityKey, token };
    const current = () => !request.signal.aborted && currentIdentity.current.identityKey === captured.identityKey && currentIdentity.current.token === captured.token;
    void API.phoneStatus(token, request.signal).then(status => {
      if (current()) setSnapshot({ ...captured, status, error: false });
    }).catch(() => { if (current()) setSnapshot({ ...captured, status: null, error: true }); });
    return () => request.abort();
  }, [eligible, strict, identityKey, token, attempt]);
  if (!eligible) return null;
  const owned = snapshot?.identityKey === identityKey && snapshot?.token === token ? snapshot : null;
  const mask = owned?.status?.bound ? owned.status.masked_phone : null;
  const label = strict ? t('auth:bind_manage_at_home', '在主页管理手机号') : owned?.error ? t('auth:bind_retry', '重试') : t('auth:bind_title', '绑定手机号');
  const action = (event: React.MouseEvent<HTMLElement>) => {
    if (strict) { leaveToLauncher(); return; }
    if (owned?.error) { setAttempt(value => value + 1); return; }
    setContainer(kiosk ? event.currentTarget.closest<HTMLElement>('.kiosk') : null); setOpen(true);
  };
  const content = <>
    {owned?.error && <Typography variant="body2" color="text.secondary">{t('auth:bind_load_error', '暂时无法读取手机号绑定状态')}</Typography>}
    {mask ? <Typography variant="body2" color="text.secondary">{t('auth:bind_bound_label', '已绑定手机号')} {mask}</Typography>
      : kiosk ? <button type="button" className="km-phone-binding-action" disabled={!strict && !owned} onClick={action}>{!strict && !owned ? t('auth:bind_loading', '正在核对绑定状态…') : label}</button>
      : <Button fullWidth variant="text" disabled={!strict && !owned} onClick={action} sx={{ minHeight: 44, color: 'text.secondary', justifyContent: 'flex-start', px: 1.5 }}>{!strict && !owned ? t('auth:bind_loading', '正在核对绑定状态…') : label}</Button>}
  </>;
  return <>
    {kiosk ? <div className="km-phone-binding">{content}</div> : <Box sx={{ mt: 1, minWidth: 0 }}>{content}</Box>}
    <PhoneBindDialog open={open} onClose={() => setOpen(false)} kiosk={kiosk} container={container} onBound={status => {
      if (currentIdentity.current.identityKey === identityKey && currentIdentity.current.token === token) setSnapshot({ identityKey, token, status, error: false });
    }} />
  </>;
}
