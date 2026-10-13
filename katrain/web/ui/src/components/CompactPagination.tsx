import { useRef, useState, type FormEvent } from 'react';
import { useTranslation } from '../hooks/useTranslation';
import './compactPagination.css';

interface Props {
  page: number;
  totalPages: number;
  disabled?: boolean;
  onPageChange: (page: number) => void;
}

/** One bounded page input, shared by the kiosk and Galaxy libraries. */
export default function CompactPagination({ page, totalPages, disabled = false, onPageChange }: Props) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const [invalid, setInvalid] = useState(false);
  const max = Math.max(1, totalPages);
  const go = (next: number) => {
    inputRef.current?.setCustomValidity('');
    inputRef.current?.blur();
    setDraft(null);
    setInvalid(false);
    onPageChange(next);
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (disabled) return;
    const input = event.currentTarget.elements.namedItem('page') as HTMLInputElement;
    const raw = input.value.trim();
    const next = Number(raw);
    if (!/^\d+$/.test(raw) || !Number.isSafeInteger(next) || next < 1 || next > max) {
      input.setCustomValidity(t('kifu:page_range', '请输入 1 到 {max} 之间的整数页码').replace('{max}', String(max)));
      setInvalid(true);
      input.reportValidity();
      return;
    }
    go(next);
  };

  return (
    <form className="compact-pagination" aria-label={t('kifu:pagination', '棋谱分页')} onSubmit={submit}>
      <button type="button" aria-label={t('kifu:prev_page', '上一页')} disabled={disabled || page <= 1} onClick={() => go(page - 1)}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m14 6-6 6 6 6" /></svg>
      </button>
      <label className="compact-pagination__position">
        <input
          ref={inputRef} className="compact-pagination__input" name="page" type="text" inputMode="numeric" enterKeyHint="go" data-enter-label={t('kifu:jump', '跳转')}
          aria-label={t('kifu:jump_page', '跳转页码')} aria-invalid={invalid}
          disabled={disabled} value={draft ?? String(page)} onFocus={(event) => event.currentTarget.select()}
          onChange={(event) => {
            event.currentTarget.setCustomValidity('');
            setInvalid(false);
            setDraft(event.target.value);
          }}
        />
        <span>/{max}</span>
      </label>
      <button className="compact-pagination__jump" type="submit" disabled={disabled}>{t('kifu:jump', '跳转')}</button>
      <button type="button" aria-label={t('kifu:next_page', '下一页')} disabled={disabled || page >= max} onClick={() => go(page + 1)}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m10 6 6 6-6 6" /></svg>
      </button>
    </form>
  );
}
