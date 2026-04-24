import { Button, Menu, MenuItem } from '@mui/material';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import { useState } from 'react';
import { useTranslation } from '../../../hooks/useTranslation';

interface ReportImportMenuProps {
  onImportLocal: () => void;
  onImportLibrary: () => void;
}

export default function ReportImportMenu({ onImportLocal, onImportLibrary }: ReportImportMenuProps) {
  const { t } = useTranslation();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  return (
    <>
      <Button
        variant="outlined"
        fullWidth
        endIcon={<ArrowDropDownIcon />}
        onClick={(event) => setAnchorEl(event.currentTarget)}
      >
        {t('report:import', 'Import game')}
      </Button>
      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
        <MenuItem
          onClick={() => {
            setAnchorEl(null);
            onImportLocal();
          }}
        >
          {t('report:import_local', 'Import local SGF')}
        </MenuItem>
        <MenuItem
          onClick={() => {
            setAnchorEl(null);
            onImportLibrary();
          }}
        >
          {t('report:import_library', 'Import from library')}
        </MenuItem>
      </Menu>
    </>
  );
}
