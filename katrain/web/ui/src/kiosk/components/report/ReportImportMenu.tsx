import { useTranslation } from '../../../hooks/useTranslation';
import { KioskCard } from '../../shell/KioskCard';

interface ReportImportMenuProps {
  onImportLibrary: () => void;
}

/** Open the searchable professional library directly; local SGF stays in that dialog. */
export default function ReportImportMenu({ onImportLibrary }: ReportImportMenuProps) {
  const { t } = useTranslation();

  return (
    <KioskCard
      title={t('review:import_card', '导入棋谱复盘')}
      sub={t('report:import_library', '从棋谱库导入')}
      icon="upload-simple"
      onClick={(event) => { event.stopPropagation(); onImportLibrary(); }}
    />
  );
}
