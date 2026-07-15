import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import { Button, Menu, MenuItem } from '@mui/material';
import { useState, type MouseEvent } from 'react';

import { useTranslation } from '../../../hooks/useTranslation';

interface ReportImportMenuProps {
  onImportLocal: () => void;
  onImportLibrary: () => void;
}

export default function ReportImportMenu({ onImportLocal, onImportLibrary }: ReportImportMenuProps) {
  const { t } = useTranslation();
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const openMenu = (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
  };
  const choose = (event: MouseEvent<HTMLElement>, action: () => void) => {
    event.stopPropagation();
    setAnchorEl(null);
    action();
  };

  return (
    <>
      <Button
        aria-haspopup="menu"
        aria-expanded={Boolean(anchorEl)}
        variant="contained"
        endIcon={<ArrowDropDownIcon />}
        onClick={openMenu}
        sx={{ minWidth: 48, minHeight: 48, whiteSpace: 'normal' }}
      >
        {t('report:import', '导入棋谱')}
      </Button>
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
          {t('report:import_local', '导入本地 SGF')}
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
