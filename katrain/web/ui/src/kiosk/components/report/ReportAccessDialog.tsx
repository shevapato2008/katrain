import type { ReportAccessIssue } from '../../../features/report/reportAccessIssue';
import { useMembershipI18n } from '../../../features/membership/useMembershipI18n';

interface Props {
  issue: ReportAccessIssue | null;
  onClose: () => void;
  onAccount: () => void;
}

export function ReportAccessDialog({ issue, onClose, onAccount }: Props) {
  const { t } = useMembershipI18n();
  if (!issue) return null;
  const insufficient = issue === 'insufficient';
  const title = insufficient
    ? t('membership:report_insufficient_title', 'Report allowance insufficient')
    : t('membership:report_verification_title', 'Free report unavailable');
  const body = insufficient
    ? t('membership:report_insufficient_body', 'There is not enough available allowance to start this report. You can review membership benefits or top up points.')
    : t('membership:report_verification_body', 'Free report eligibility is unavailable, so this report has not started. You can check membership and points on your account page.');
  const action = insufficient
    ? t('membership:report_view_membership', 'Membership and top-up')
    : t('membership:report_view_account', 'View account and allowance');
  return <div className="cdlg" role="dialog" aria-modal="true" aria-labelledby="report-access-title" aria-describedby="report-access-body">
    <div className="cdlg__box">
      <h3 id="report-access-title">{title}</h3>
      <p id="report-access-body">{body}</p>
      <div className="cdlg__acts">
        <button type="button" className="ghost" onClick={onClose}>{t('membership:cancel', '取消')}</button>
        <button type="button" className="main" onClick={onAccount}>{action}</button>
      </div>
    </div>
  </div>;
}
