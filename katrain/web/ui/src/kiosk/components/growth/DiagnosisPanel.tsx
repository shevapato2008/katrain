import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../../hooks/useTranslation';
import {
  DIAGNOSIS_THIN_MOVES,
  DIAGNOSIS_THIN_REPORTS,
  diagnosisLines,
  type GrowthDiagnosis,
} from '../../api/growthApi';

const pct = (v: number) => `${Math.round(v * 100)}%`;

/** 复盘屏那套词(`grade:phase_*`,.po 里就是这三个字)。默认值必须是中文:译文没加载到时
 *  屏上会原样露出默认值 —— 复盘屏那处拿 id 当默认值,断网时显示的是「midgame」。 */
const PHASE_ZH = { opening: '布局', midgame: '中盘', endgame: '官子' } as const;

/**
 * 屏 22 右栏「能力诊断」。构造照国象样稿 14 屏:一段一行「段名 + 细条」,底部一句样本量。
 *
 * **口径**:最近几份已完成报告里**你执的那一方**的手,按布局 / 中盘 / 官子(复盘屏同一套词、
 * 同一份 `move_grade.yaml` 边界)数问题手 —— 报告七档里的小亏 · 失误 · 恶手。
 * 右边写成 `问题手 15 / 150`:分子分母都摆出来,每一段自己的样本量就在那一行上。
 *
 * **四种「没有数」是四句话**,不许合成一句:
 *  · 读失败 —— 「诊断没读到」,不是「还没有报告」;
 *  · 一份报告都没有 —— 给「去复盘」的出口;
 *  · 有报告、但那几局没记下你执哪一方 —— 说这件事,**不说「还没有报告」**(那是撒谎);
 *  · 有报告、但里面没有评过级的手 —— 同样照实说。
 * 外加一种:盒子退回本机缓存时的「0 份」是「这会儿没连上云端」(报告在云端),也不说「还没有报告」。
 */
const DiagnosisPanel = ({ diag, failed }: { diag: GrowthDiagnosis | null; failed: boolean }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const goReport = (
    <button
      type="button"
      className="kiosk-btn kiosk-btn--pill pill"
      data-testid="diag-go-report"
      onClick={() => navigate('/kiosk/report')}
    >
      {t('growth:diag_go_report', '去复盘')}
    </button>
  );

  let body;
  if (failed) {
    body = (
      <div className="empty" data-testid="diag-error">
        <h4>{t('growth:diag_failed', '诊断没读到')}</h4>
        <p>{t('growth:diag_failed_p', '不是「还没有报告」。稍后再看一次。')}</p>
      </div>
    );
  } else if (diag === null) {
    body = (
      <div className="empty" data-testid="diag-loading">
        <h4>{t('growth:diag_loading', '正在读…')}</h4>
      </div>
    );
  } else if (diag.reports === 0 && diag.authority === 'local_cache') {
    // 盒子上报告在云端,本机库里没有逐手数据 ⇒ 这里的「0 份」是「这会儿没连上云端」,
    // 不是「你还没有报告」。
    body = (
      <div className="empty" data-testid="diag-offline">
        <h4>{t('growth:diag_offline', '这会儿读不到云端的报告')}</h4>
        <p>{t('growth:diag_offline_p', '报告存在云端，盒子上这一份里没有。联网后再看一次。')}</p>
      </div>
    );
  } else if (diag.reports === 0 && diag.skipped_without_color > 0) {
    body = (
      <div className="empty" data-testid="diag-empty">
        <h4>{t('growth:diag_no_seat', '这几份报告还算不进来')}</h4>
        <p>
          {t('growth:diag_no_seat_a', '你有 ')}
          <b>{diag.skipped_without_color}</b>
          {t('growth:diag_no_seat_b', ' 份报告，但那几局下的时候还没记下你执黑还是执白，分不出哪些手是你下的。再下一局、跑一份报告，这里就有数了。')}
        </p>
        {goReport}
      </div>
    );
  } else if (diag.reports === 0) {
    body = (
      <div className="empty" data-testid="diag-empty">
        <h4>{t('growth:diag_no_report', '还没有复盘报告')}</h4>
        <p>{t('growth:diag_no_report_p', '诊断拿跑过报告的对局算：下完一局，在复盘里生成一份报告，这里就有数了。')}</p>
        {goReport}
      </div>
    );
  } else {
    const lines = diagnosisLines(diag);
    const thin = diag.graded_moves < DIAGNOSIS_THIN_MOVES || diag.reports < DIAGNOSIS_THIN_REPORTS;
    body = lines.length === 0 ? (
      <div className="empty" data-testid="diag-ungraded">
        <h4>{t('growth:diag_ungraded', '报告里还没有评过级的手')}</h4>
        <p>{t('growth:diag_ungraded_p', '搜索量不够的手不评级。报告跑完整之后，这里就有数了。')}</p>
      </div>
    ) : (
      <>
        <div className="gdlines">
          {lines.map((row) => (
            <div className="gmetric gdline" key={row.phase} data-testid="diag-row" data-phase={row.phase}>
              <span {...(row.weakest ? { 'data-testid': 'diag-weakest' } : {})}>
                <b>
                  {t(`grade:phase_${row.phase}`, PHASE_ZH[row.phase])}
                  {row.weakest && <em className="gdweak">{t('growth:diag_weakest', '最弱')}</em>}
                </b>
                <i>
                  {t('growth:diag_bad_count', '问题手 {m} / {n}')
                    .replace('{m}', String(row.bad))
                    .replace('{n}', String(row.graded))}
                </i>
              </span>
              {/* 细条是问题手的**比例**,满格 = 这一段手手都是问题手。不按三段里最大的那段归一化 ——
                  那样会把 10% 对 12% 画成半格对满格,是在放大噪声。 */}
              <div className="gbar is-bad"><span style={{ width: pct(Math.min(1, row.rate)) }} /></div>
            </div>
          ))}
        </div>
        {/* 样本量、「另有 N 份没算进来」、「样本还少」并成**一段** —— 日历加进右栏之后,诊断块只剩
            两百来像素高,三句分开摆会把最后一句挤出框(真浏览器实测溢出 94px)。 */}
        <p className="setnote gdnote" data-testid="diag-sample">
          {t('growth:diag_sample_a', '只看跑过报告的对局：最近 ')}
          <b>{diag.reports}</b>
          {t('growth:diag_sample_b', ' 份里你下的 ')}
          <b>{diag.graded_moves}</b>
          {t('growth:diag_sample_c', ' 手。')}
          {diag.skipped_without_color > 0 && (
            <>
              {t('growth:diag_skipped_a', '另有 ')}
              <b>{diag.skipped_without_color}</b>
              {t('growth:diag_skipped_b', ' 份没记执色。')}
            </>
          )}
          {diag.authority === 'local_cache' && (
            <>
              {t('growth:diag_local_a', '这是')}
              <b>{t('growth:local_note_b', '本机记录')}</b>
              {t('growth:diag_local_b', '，可能少几份。')}
            </>
          )}
          {thin && (
            <b data-testid="diag-thin">{t('growth:diag_thin', '样本还少，结论会抖。')}</b>
          )}
        </p>
      </>
    );
  }

  return (
    <div className="panel gsec" data-testid="growth-diagnosis">
      <h3>{t('growth:diag_title', '能力诊断')}</h3>
      {body}
    </div>
  );
};

export default DiagnosisPanel;
