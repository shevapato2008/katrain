import { MenuItem, TextField } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';

/** 区号短名单。**不引第三方国家库**（与后端「零新增依赖」同一条约束）：
 *  我们只需要拼出 E.164，真正的号段合法性由运营商说了算，
 *  后端 `normalize_e164` 还会再判一次。
 *
 *  ⚠️ 国家名今天是写死的中文，**没有进 i18n**。这是本 Task 有意划出去的范围
 *  （10 个国家 × 11 种语言 = 110 条翻译），不是漏掉：日/韩/英文用户会在这个
 *  下拉里看到中文国家名。记在 plan.md 收尾里等排期，别当成已完成。 */
export const COMMON_COUNTRY_CODES: { cc: string; label: string }[] = [
  { cc: '+86', label: '中国大陆' }, { cc: '+852', label: '中国香港' },
  { cc: '+853', label: '中国澳门' }, { cc: '+886', label: '中国台湾' },
  { cc: '+1', label: '美国/加拿大' }, { cc: '+81', label: '日本' },
  { cc: '+82', label: '韩国' }, { cc: '+65', label: '新加坡' },
  { cc: '+44', label: '英国' }, { cc: '+61', label: '澳大利亚' },
];

interface Props { value: string; onChange: (cc: string) => void; disabled?: boolean }

/** 用 `<TextField select>` 而不是 `FormControl + InputLabel + Select`：前者自己把
 *  `labelId` 接上，`getByRole('combobox', { name })` 直接解析得出可访问名。
 *  仓里 `galaxy/pages/AiSetupPage.tsx` 用的是后者，它的测试因此被迫按
 *  `.MuiFormControl-root` 这个 class 绕路取元素（AiSetupPage.test.tsx:140-148）——
 *  那是把判据挪到了实现细节上，这里不重复。 */
const CountryCodeSelect = ({ value, onChange, disabled }: Props) => {
  const { t } = useTranslation();   // 订阅语言切换，切了当场重渲染
  return (
    <TextField
      select
      margin="dense"
      label={t('auth:country_code', '国家/地区')}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      sx={{ minWidth: 150, flex: 'none' }}
    >
      {COMMON_COUNTRY_CODES.map((c) => (
        <MenuItem key={c.cc} value={c.cc}>{`${c.cc} ${c.label}`}</MenuItem>
      ))}
    </TextField>
  );
};

export default CountryCodeSelect;
