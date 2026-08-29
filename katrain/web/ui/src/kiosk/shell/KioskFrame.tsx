import { useEffect, useState, type ReactNode } from 'react';
import { calculateKioskScale, KIOSK_CANVAS_H, KIOSK_CANVAS_W } from './kioskScale';

function useKioskScale(): number {
  const [scale, setScale] = useState(() => calculateKioskScale(window.innerWidth, window.innerHeight));
  useEffect(() => {
    const onResize = () => setScale(calculateKioskScale(window.innerWidth, window.innerHeight));
    onResize();
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return scale;
}

/**
 * 全站唯一的外壳。规范 §5:顶栏和 Dock 都是通栏贴边,中间区外框 x16–1008、y70 起,
 * L1 时下缘 504(Dock 在场)、L2/L3 时 586。
 *
 * `.kiosk` 挂在**这一层**(不是各屏各挂)—— tokens.css 整份定义在 `.kiosk {}` 里,
 * 在它外面 var() 静默求空、字体掉回 sans、color-mix 整条作废,而且不报错。
 *
 * @param level 1 = 一级页(有 Dock,中间区 434 高);2 = 二/三级页(无 Dock,516 高)
 * @param dock  一级页传 <KioskDock/>;二/三级页不传
 * @param topbar 顶栏节点(Task 3 之前先传旧 Header,Task 3 起恒传 <KioskTopbar/>)
 * @param extras 盖在整屏之上、但仍跟着画布缩放的东西(弹窗、全局提示)
 */
export function KioskFrame({ level, topbar, dock, extras, children }: {
  level: 1 | 2;
  topbar?: ReactNode;
  dock?: ReactNode;
  extras?: ReactNode;
  children: ReactNode;
}) {
  const scale = useKioskScale();
  return (
    <div
      className="kiosk"
      data-testid="kiosk-frame"
      style={{
        position: 'absolute', top: '50%', left: '50%',
        width: KIOSK_CANVAS_W, height: KIOSK_CANVAS_H,
        transform: `translate(-50%, -50%) scale(${scale})`,
      }}
    >
      {/* data-level 写成字符串:tokens.css 那条选择器是 [data-level="1"],
          它决定 L1 的中间区下缘停在 504 还是 586 —— 写错整屏内容会被 Dock 压住。 */}
      <div className="kiosk-screen" data-level={String(level)}>
        {topbar}
        <div className="kiosk-content">{children}</div>
        {dock}
      </div>
      {extras}
    </div>
  );
}

export default KioskFrame;
