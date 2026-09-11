import { Box, Checkbox, FormControlLabel, Link, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { PRIVACY_PATH } from '../../../legal/privacy';

/** 手机号收集的告知与**单独**同意。
 *
 * 「单独」的操作含义：不与「同意服务条款」打包成一个勾选，且**默认不勾**。
 * 打包或默认勾上的同意在合规上等于没取得。
 *
 * 只给一份政策链接不算告知 —— **由谁收、收什么、干什么用**要写在眼前这一行里。
 *
 * ⚠️ 主体名写「北京万智星科技有限公司」，不是「万智星」也不是「智星盒」：
 * PIPL 十七条要告知的是**个人信息处理者的名称**。仓里唯一有文书依据的全称来自
 * `galaxy/components/layout/icpFiling.ts:1`（京ICP备2026047949号的备案主办单位）；
 * 「万智星」只是它的简称，且同轨道手册判定它作为**短信签名**很可能报不过、属待裁项 ——
 * 那是阿里云签名审核的规则，不是 PIPL 的规则，两套要的东西不同。
 * **上线前仍需 Fan 按营业执照核一次**，见 plan.md 收尾。
 *
 * ⚠️ Checkbox 不配 `inputProps={{'aria-label': …}}`：FormControlLabel 的 <label> 本来就包住
 * input，隐式关联已经成立；加了反而把可访问名从整句同意语**截短**成链接那四个字 ——
 * 一个同意勾选框丢掉的恰好是「同意」那半句。
 */
interface Props { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }

const PhoneConsent = ({ checked, onChange, disabled }: Props) => {
  const { t } = useTranslation();
  return (
    <Box data-testid="phone-consent" sx={{ mt: 1 }}>
      <FormControlLabel
        sx={{ alignItems: 'flex-start', mr: 0 }}
        control={
          <Checkbox
            size="small"
            checked={checked}
            onChange={(e) => onChange(e.target.checked)}
            disabled={disabled}
            sx={{ pt: 0.25 }}
          />
        }
        label={
          <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.6 }}>
            {t('auth:phone_consent',
              '我同意「智星盒」的运营方北京万智星科技有限公司收集我的手机号，仅用于身份验证与登录。')}
            {' '}
            {/* 新开一页：同一页跳走会把填了一半的手机号与验证码连同弹窗一起冲掉。
                MUI Link 传 href 时渲染的是原生 <a>，不走 react-router。 */}
            <Link href={PRIVACY_PATH} target="_blank" rel="noopener noreferrer">
              {t('auth:privacy_policy', '《隐私策略》')}
            </Link>
          </Typography>
        }
      />
    </Box>
  );
};

export default PhoneConsent;
