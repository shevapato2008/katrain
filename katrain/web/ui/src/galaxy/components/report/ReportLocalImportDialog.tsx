import { useMemo, useState, type ChangeEvent } from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import UploadFileIcon from '@mui/icons-material/UploadFile';

import { sgfToMoves } from '../../../utils/sgfSerializer';
import { useTranslation } from '../../../hooks/useTranslation';

export interface LocalImportPayload {
  title?: string;
  sgfContent: string;
  boardSize: number;
  rules: string;
  komi: number;
  moveCount: number;
  playerBlack?: string;
  playerWhite?: string;
  blackRank?: string;
  whiteRank?: string;
  result?: string;
}

interface ReportLocalImportDialogProps {
  open: boolean;
  loading?: boolean;
  onClose: () => void;
  onSubmit: (payload: LocalImportPayload, reportType?: 'normal' | 'deep') => void;
}

export default function ReportLocalImportDialog({
  open,
  loading = false,
  onClose,
  onSubmit,
}: ReportLocalImportDialogProps) {
  const { t } = useTranslation();
  const [title, setTitle] = useState('');
  const [sgfContent, setSgfContent] = useState('');

  const parsed = useMemo(() => {
    if (!sgfContent.trim()) return null;
    try {
      return sgfToMoves(sgfContent);
    } catch {
      return null;
    }
  }, [sgfContent]);

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const content = await file.text();
    setSgfContent(content);
    if (!title) {
      setTitle(file.name.replace(/\.sgf$/i, ''));
    }
    event.target.value = '';
  };

  const payload = parsed
    ? {
        title: title.trim() || undefined,
        sgfContent: sgfContent.trim(),
        boardSize: parsed.metadata.boardSize || 19,
        rules: parsed.metadata.rules || 'chinese',
        komi: parsed.metadata.komi || 7.5,
        // 摆子不是着手 —— 后端的 total_moves 只数着手,这里跟着收口径。
        moveCount: parsed.moves.length - parsed.setupCount,
        playerBlack: parsed.metadata.playerBlack || undefined,
        playerWhite: parsed.metadata.playerWhite || undefined,
        blackRank: parsed.metadata.blackRank || undefined,
        whiteRank: parsed.metadata.whiteRank || undefined,
        result: parsed.metadata.result || undefined,
      }
    : null;

  return (
    <Dialog open={open} onClose={() => !loading && onClose()} maxWidth="md" fullWidth>
      <DialogTitle>{t('report:import_local', 'Import local SGF')}</DialogTitle>
      <DialogContent>
        <Stack spacing={2} sx={{ pt: 1 }}>
          <TextField
            label={t('report:title_label', 'Title')}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder={t('report:optional', 'Optional')}
            fullWidth
          />
          <Stack direction="row" spacing={1} alignItems="center">
            <Button component="label" variant="outlined" startIcon={<UploadFileIcon />}>
              {t('report:choose_file', 'Choose local file')}
              <input hidden type="file" accept=".sgf,.txt" onChange={handleFileChange} />
            </Button>
            <Typography variant="body2" color="text.secondary">
              {t('report:choose_file_hint', 'Select a local SGF file, or paste SGF content directly.')}
            </Typography>
          </Stack>
          <Divider />
          <TextField
            label="SGF Content"
            value={sgfContent}
            onChange={(event) => setSgfContent(event.target.value)}
            multiline
            minRows={12}
            fullWidth
            placeholder="(;FF[4]GM[1]SZ[19];B[pd];W[dd])"
          />
          {payload && (
            <Stack direction="row" spacing={2} flexWrap="wrap">
              <Typography variant="body2" color="text.secondary">{t('report:board_size', 'Board')}: {payload.boardSize} {t('report:board_size_unit', '×')}</Typography>
              <Typography variant="body2" color="text.secondary">{t('report:rules_label', 'Rules')}: {payload.rules}</Typography>
              <Typography variant="body2" color="text.secondary">{t('report:komi_label', 'Komi')}: {payload.komi}</Typography>
              <Typography variant="body2" color="text.secondary">{t('report:move_numbers', 'Move #')}: {payload.moveCount}</Typography>
            </Stack>
          )}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={loading}>{t('report:cancel', 'Cancel')}</Button>
        <Button disabled={loading || !payload} onClick={() => payload && onSubmit(payload)}>
          {loading ? t('report:importing', 'Importing...') : t('report:import_only', 'Import only')}
        </Button>
        <Button
          variant="contained"
          disabled={loading || !payload}
          onClick={() => payload && onSubmit(payload, 'normal')}
        >
          {t('report:import_and_normal', 'Import & generate normal report')}
        </Button>
        <Button
          variant="outlined"
          disabled={loading || !payload}
          onClick={() => payload && onSubmit(payload, 'deep')}
        >
          {t('report:import_and_deep', 'Import & generate deep report')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
