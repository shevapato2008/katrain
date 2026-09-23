import { useCallback, useEffect, useRef, useState } from 'react';
import QRCode from 'qrcode';
import { useTranslation } from '../../../hooks/useTranslation';
import { useAuth } from '../../../context/AuthContext';
import { API } from '../../../api';
import { platformErrorMessage } from '../../utils/platformErrorMessage';

/**
 * 星阵扫码登录面板(屏 07a,设计源 `go-kiosk.tmpl.html:1361-1372`,`.xpqr` 一段)。
 * 挂在 `PlatformLoginPage` 里,`mode === 'scan'` 时取代账号/密码那两个 `.igrow`。
 *
 * 星阵没有「给我一张二维码图片」的接口 —— 后端 `scan/start` 只给一个 `payload` 字符串
 * (`golaxy_url&&&<uuid>`),图必须本地画,所以这里用 `qrcode` 库把它渲成内联 SVG。
 * 前端只认后端发的 `scan_id`,不碰星阵的 uuid(那串 uuid 只活在 `payload` 里,
 * 前端不解析它、也不单独存)。
 *
 * ## 那条硬要求:取不到 scan_id 不许摆一张扫不动的假码
 *
 * `start()` 的 try 块里,`scan_id`/二维码 SVG 和「进入可轮询状态」是同一步的三件事 ——
 * 三件事必须同生同灭。`scan/start` 一失败就落进 catch,只置 `unavailable`,**不**碰
 * `scanId`/`qrSvg`/`timerRef`,所以画码和起轮询两件事都不会发生。变成「先试着画」
 * 再在别处补一个「万一没有就……」的检查,会把这条同生共死的关系拆成两处,
 * 后面改代码的人容易漏改其中一处。
 *
 * ## 轮询:每秒一次,终态即停,组件卸载也停
 *
 * `confirmed`/`expired`/`cancelled` 是终态(`confirmed` 额外要打一次 `scan/confirm`);
 * `unknown` **不是**终态,继续轮询(后端 `platforms.py` 对同一批终态也做了短路,
 * 前端这里停轮询省的是「短路之后还在每秒白打一次 HTTP」)。`aliveRef` 挡的是
 * 组件已卸载但上一次 await 还没回来时的 setState-after-unmount。
 */

type ScanState = 'waiting' | 'scanned' | 'confirmed' | 'expired' | 'cancelled' | 'unknown';

const STATUS_TEXT: Record<ScanState, { key: string; zh: string }> = {
  waiting: { key: 'platform:scan_state_waiting', zh: '等待扫描' },
  scanned: { key: 'platform:scan_state_scanned', zh: '已扫描，请在手机上确认' },
  confirmed: { key: 'platform:scan_state_confirmed', zh: '已确认，正在登录…' },
  expired: { key: 'platform:scan_state_expired', zh: '二维码已失效' },
  cancelled: { key: 'platform:scan_state_cancelled', zh: '手机上取消了登录' },
  unknown: { key: 'platform:scan_state_waiting', zh: '等待扫描' },
};

const TERMINAL_STATES: ReadonlySet<ScanState> = new Set(['confirmed', 'expired', 'cancelled']);

interface GolaxyScanPanelProps {
  platform: string;
  onDone: () => void;
}

export function GolaxyScanPanel({ platform, onDone }: GolaxyScanPanelProps) {
  const { t } = useTranslation();
  const { token } = useAuth();

  const [scanId, setScanId] = useState<string | null>(null);
  const [qrSvg, setQrSvg] = useState('');
  const [scanState, setScanState] = useState<ScanState>('waiting');
  const [unavailable, setUnavailable] = useState(false);
  const [confirmError, setConfirmError] = useState('');

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const aliveRef = useRef(true);

  const stopPolling = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const confirm = useCallback(async (id: string) => {
    try {
      await API.platformScanConfirm(platform, id, token);
      if (aliveRef.current) onDone();
    } catch (e) {
      if (aliveRef.current) {
        setConfirmError(platformErrorMessage(e, t('platform:scan_confirm_failed', '确认登录失败')));
      }
    }
  }, [platform, token, onDone, t]);

  const poll = useCallback(async (id: string) => {
    let state: ScanState;
    try {
      const res = await API.platformScanState(platform, id, token);
      state = (res.state as ScanState) ?? 'unknown';
    } catch {
      // 轮询本身的网络抖动:不是「拿不到 scan_id」那条硬要求管的场景,静默重试下一秒。
      return;
    }
    if (!aliveRef.current) return;
    setScanState(state);
    if (TERMINAL_STATES.has(state)) {
      stopPolling();
      if (state === 'confirmed') void confirm(id);
    }
  }, [platform, token, confirm]);

  const start = useCallback(async () => {
    stopPolling();
    setUnavailable(false);
    setConfirmError('');
    setScanState('waiting');
    setQrSvg('');
    setScanId(null);
    try {
      const res = await API.platformScanStart(platform, token);
      const svg = await QRCode.toString(res.payload, { type: 'svg', margin: 0 });
      if (!aliveRef.current) return;
      setScanId(res.scan_id);
      setQrSvg(svg);
      timerRef.current = setInterval(() => { void poll(res.scan_id); }, 1000);
    } catch {
      if (aliveRef.current) setUnavailable(true);
    }
  }, [platform, token, poll]);

  useEffect(() => {
    aliveRef.current = true;
    void start();
    return () => {
      aliveRef.current = false;
      stopPolling();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [platform, token]);

  if (unavailable) {
    return (
      <div className="xpqr">
        <div className="qrbox qrbox--unavailable" data-testid="scan-unavailable" />
        <div className="xpqr__side">
          <h4>{t('platform:scan_unavailable_title', '连不上星阵')}</h4>
          <p>{t('platform:scan_unavailable_body', '检查网络')}</p>
          <button
            type="button"
            className="kiosk-btn kiosk-btn--secondary"
            data-testid="scan-retry"
            onClick={() => { void start(); }}
          >
            {t('platform:scan_retry', '重试')}
          </button>
        </div>
      </div>
    );
  }

  const status = STATUS_TEXT[scanState];

  return (
    <div className="xpqr">
      <div className="qrbox">
        {qrSvg && (
          <span
            className="qrimg"
            data-testid="scan-qr"
            aria-label={t('platform:scan_qr_alt', '星阵登录二维码')}
            dangerouslySetInnerHTML={{ __html: qrSvg }}
          />
        )}
      </div>
      <div className="xpqr__side">
        <h4>{t('platform:scan_title', '打开星阵 APP 扫一扫')}</h4>
        <p>{t('platform:scan_body', '扫完在手机上点确认，密码不经过这台盒子。')}</p>
        <span className="xpstat" data-testid="scan-status">
          <i className="led" aria-hidden="true" />
          {t(status.key, status.zh)}
        </span>
        {confirmError && <p className="loginerr" data-testid="scan-confirm-error">{confirmError}</p>}
        {scanId && (
          <button
            type="button"
            className="kiosk-btn kiosk-btn--secondary"
            data-testid="scan-refresh"
            onClick={() => { void start(); }}
          >
            {t('platform:scan_refresh', '换一张')}
          </button>
        )}
      </div>
    </div>
  );
}

export default GolaxyScanPanel;
