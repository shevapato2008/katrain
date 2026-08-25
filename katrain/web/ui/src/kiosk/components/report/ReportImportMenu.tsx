import { Menu, MenuItem } from '@mui/material';
import { useState, type MouseEvent } from 'react';

import { useTranslation } from '../../../hooks/useTranslation';
import { KioskCard } from '../../shell/KioskCard';

interface ReportImportMenuProps {
  onImportLocal: () => void;
  onImportLibrary: () => void;
}

/**
 * 屏 19「生成报告」那一组的第三张卡。
 *
 * ⚠️ **稿子把这张卡画成了 `is-soon`「接口还没有 · 即将上线」,那是稿子写错了。**
 * 两条导入路真的在跑:`ReportLocalImportDialog`(贴一份 SGF 进来)和
 * `ReportLibraryImportDialog`(从云端名局棋谱库拉一局进来),都落到
 * `POST /api/v1/user-games`。挂「即将上线」= 把能用的功能说成没有,
 * 比缺一张卡坏 —— 已登记,该提上游改稿。
 *
 * 一张卡两条路,所以点开是个二选一。**触发器是 `.kiosk-card` 不是 MUI 按钮** ——
 * 这一组三张卡必须一样大(「同一屏上的卡不许有第二种尺寸」,国象 2026-07-28 拍板)。
 */
export default function ReportImportMenu({ onImportLocal, onImportLibrary }: ReportImportMenuProps) {
  const { t } = useTranslation();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const choose = (event: MouseEvent<HTMLElement>, action: () => void) => {
    event.stopPropagation();
    setAnchorEl(null);
    action();
  };

  return (
    <>
      <KioskCard
        title={t('review:import_card', '导入棋谱复盘')}
        sub={t('review:import_card_sub', '本地 SGF 或棋谱库')}
        icon="upload-simple"
        onClick={(event) => { event.stopPropagation(); setAnchorEl(event.currentTarget); }}
      />
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={() => setAnchorEl(null)}
        slotProps={{
          list: {
            'aria-label': t('report:import_options', '导入方式'),
            sx: { '& .MuiMenuItem-root': { minHeight: 48 } },
          },
        }}
      >
        <MenuItem
          onClick={(event) => choose(event, onImportLocal)}
          sx={{ minWidth: 48, minHeight: 48 }}
        >
          {t('report:import_local', '从本地导入 SGF')}
        </MenuItem>
        <MenuItem
          onClick={(event) => choose(event, onImportLibrary)}
          sx={{ minWidth: 48, minHeight: 48 }}
        >
          {t('report:import_library', '从棋谱库导入')}
        </MenuItem>
      </Menu>
    </>
  );
}
