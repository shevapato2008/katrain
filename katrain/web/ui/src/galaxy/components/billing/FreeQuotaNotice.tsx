import { useCallback, useEffect, useState } from 'react';
import { Box, Button, Typography } from '@mui/material';
import { API, type BillingQuota } from '../../../api';
import { useAuth } from '../../../context/AuthContext';
import { i18n } from '../../../i18n';
import { useTranslation } from '../../../hooks/useTranslation';
import BindPhoneDialog from '../auth/BindPhoneDialog';

/** 复盘页的免费额度提示。
 *
 *  **判据取自服务端的 `blocked_reason`，不取本地的 `user.phone_bound`**：额度归属是服务端的
 *  事实，本地那格只是它的一份缓存。本地拿来当**刷新触发器**用（绑定成功 → refreshUser →
 *  phone_bound 翻面 → 这里重新取数），不当判据。
 *
 *  文案一律写「普通复盘」：`endpoints/billing.py:99-102` 明写 `free_weekly` 只描述
 *  `report_type="normal"`，深度复盘对谁都不免费，**前端不得把它显示在深度复盘按钮旁边**。
 *  而这一行下面紧跟的列表里，每张卡都带「普通/深度」两个按钮 —— 不写明就是在替深度报免费。 */
const FreeQuotaNotice = () => {
  useTranslation();
  const { user, phoneLoginEnabled } = useAuth();
  const [quota, setQuota] = useState<BillingQuota | null>(null);
  const [failed, setFailed] = useState(false);
  const [bindOpen, setBindOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      setQuota(await API.getBillingQuota());
      setFailed(false);
    } catch {
      // 取不到就说取不到。装成 0 次会让用户等到下周，装成有额度会让他在生成时才撞墙。
      setQuota(null);
      setFailed(true);
    }
  }, []);

  // 先取出来再进依赖数组：react-hooks 的 exhaustive-deps 对可选链表达式会报
  // "complex expression in dependency array"。
  const phoneBound = user?.phone_bound;
  useEffect(() => { void load(); }, [load, phoneBound]);

  if (failed) {
    return (
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
        {i18n.t('report:free_quota_unavailable', '免费额度信息暂时取不到')}
      </Typography>
    );
  }
  if (!quota) return null;

  const { used, allowance, blocked_reason: blocked } = quota.free_weekly;
  const remaining = Math.max(0, allowance - used);

  /* 这台服务器没有手机功能时，`phone_required` 这条提示是个**死胡同**：
     绑号的门在这台机器上不存在（四个手机端点一律 404），告诉用户"绑了就有免费额度"
     等于指着一扇没有的门。整条提示收掉，不退回下面那两句 ——
     `allowance` 此时是 0，"本周已用完"会把"没资格"说成"额度耗尽"，
     用户会去等下周（spec §3.1 状态诚实）。 */
  if (blocked === 'phone_required' && !phoneLoginEnabled) return null;

  return (
    <Box sx={{ mb: 1.5, display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
      <Typography variant="body2" color="text.secondary">
        {blocked === 'phone_required'
          ? i18n.t('report:free_quota_phone_required', '绑定手机号后可享每周免费普通复盘')
          : remaining > 0
            ? `${i18n.t('report:free_quota_remaining_prefix', '本周剩余')} ${remaining} ${i18n.t('report:free_quota_remaining_suffix', '次免费普通复盘')}`
            : i18n.t('report:free_quota_used_up', '本周免费普通复盘次数已用完')}
      </Typography>
      {blocked === 'phone_required' && (
        <Button size="small" variant="outlined" onClick={() => setBindOpen(true)}>
          {i18n.t('auth:bind_phone', '绑定手机号')}
        </Button>
      )}
      <BindPhoneDialog open={bindOpen} onClose={() => setBindOpen(false)} />
    </Box>
  );
};

export default FreeQuotaNotice;
