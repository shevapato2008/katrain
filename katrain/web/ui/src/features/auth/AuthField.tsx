import { useId, useState, type InputHTMLAttributes, type ReactNode } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { useTranslation } from '../../hooks/useTranslation';

type Props = InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string; action?: ReactNode };
export default function AuthField({ label, error, action, type, ...input }: Props) {
  const id = useId();
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);
  return <div className={`named-auth-field${error ? ' invalid' : ''}`}>
    <label htmlFor={id}>{label}</label>
    <div className="named-auth-control">
      <div className={`named-auth-input-shell${type === 'password' ? ' with-eye' : ''}`}>
        <input {...input} id={id} type={type === 'password' && visible ? 'text' : type} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : undefined} />
        {type === 'password' && <button type="button" className="named-auth-eye" onClick={() => setVisible(!visible)} aria-label={visible ? t('auth:hide_password', '隐藏密码') : t('auth:show_password', '显示密码')}>
          {visible ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
        </button>}
      </div>
      {action}
    </div>
    {error && <p id={`${id}-error`} className="named-auth-error" role="alert">{error}</p>}
  </div>;
}
