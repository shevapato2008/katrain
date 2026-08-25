import UploadFileIcon from '@mui/icons-material/UploadFile';
import {
  Alert,
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
import { useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react';

import type { ReportType } from '../../../api/reportApi';
import type { LocalReportImportPayload } from '../../../features/report/reportModel';
import { useTranslation } from '../../../hooks/useTranslation';
import { sgfToMoves } from '../../../utils/sgfSerializer';

export type LocalImportPayload = LocalReportImportPayload;

interface ReportLocalImportDialogProps {
  open: boolean;
  loading?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (payload: LocalReportImportPayload, reportType?: ReportType) => void;
}

const actionButtonSx = {
  minWidth: 48,
  minHeight: 48,
  px: 1,
  whiteSpace: 'normal',
  overflowWrap: 'anywhere',
  lineHeight: 1.15,
};

interface SgfProperty {
  id: string;
  values: string[];
}

interface SgfTreeFrame {
  hasNode: boolean;
  variationsStarted: boolean;
}

function parseSgfProperties(content: string): SgfProperty[] | null {
  const trimmed = content.trim();
  if (!/^\(\s*;/.test(trimmed) || !/\)\s*$/.test(trimmed)) return null;

  const properties: SgfProperty[] = [];
  let index = 0;
  let topLevelTrees = 0;
  let canReadProperty = false;
  let sawNode = false;
  const treeStack: SgfTreeFrame[] = [];
  const skipWhitespace = () => {
    while (index < trimmed.length && /\s/.test(trimmed[index])) index += 1;
  };

  while (index < trimmed.length) {
    skipWhitespace();
    const token = trimmed[index];
    if (token === '(') {
      const parentTree = treeStack.at(-1);
      if (parentTree) {
        if (!parentTree.hasNode) return null;
        parentTree.variationsStarted = true;
      } else {
        topLevelTrees += 1;
      }
      treeStack.push({ hasNode: false, variationsStarted: false });
      canReadProperty = false;
      index += 1;
      continue;
    }
    if (token === ')') {
      const completedTree = treeStack.pop();
      if (!completedTree?.hasNode) return null;
      canReadProperty = false;
      index += 1;
      continue;
    }
    if (token === ';') {
      const currentTree = treeStack.at(-1);
      if (!currentTree || currentTree.variationsStarted) return null;
      currentTree.hasNode = true;
      sawNode = true;
      canReadProperty = true;
      index += 1;
      continue;
    }
    if (token && /[A-Z]/.test(token)) {
      if (!canReadProperty) return null;
      const idStart = index;
      while (index < trimmed.length && /[A-Z]/.test(trimmed[index])) index += 1;
      const id = trimmed.slice(idStart, index);
      skipWhitespace();
      const values: string[] = [];
      while (trimmed[index] === '[') {
        index += 1;
        let value = '';
        let closed = false;
        while (index < trimmed.length) {
          const character = trimmed[index];
          if (character === '\\') {
            index += 1;
            if (index >= trimmed.length) return null;
            value += trimmed[index];
            index += 1;
          } else if (character === ']') {
            index += 1;
            closed = true;
            break;
          } else {
            value += character;
            index += 1;
          }
        }
        if (!closed) return null;
        values.push(value);
        skipWhitespace();
      }
      if (values.length === 0) return null;
      properties.push({ id, values });
      continue;
    }
    return null;
  }

  return treeStack.length === 0 && topLevelTrees === 1 && sawNode ? properties : null;
}

function isValidCoordinate(value: string, boardSize: number, allowPass: boolean): boolean {
  if (allowPass && (value === '' || (value === 'tt' && boardSize <= 19))) return true;
  if (!/^[a-z]{2}$/.test(value)) return false;
  const x = value.charCodeAt(0) - 97;
  const y = value.charCodeAt(1) - 97;
  return x >= 0 && x < boardSize && y >= 0 && y < boardSize;
}

function isValidReportSgf(content: string): boolean {
  const properties = parseSgfProperties(content);
  if (!properties) return false;

  const gameTypes = properties.filter(({ id }) => id === 'GM').flatMap(({ values }) => values);
  if (gameTypes.some((value) => value.trim() !== '1')) return false;

  const sizes = properties.filter(({ id }) => id === 'SZ').flatMap(({ values }) => values);
  if (sizes.length > 1 || sizes.some((value) => !['9', '13', '19'].includes(value.trim()))) return false;
  const boardSize = sizes.length === 1 ? Number(sizes[0].trim()) : 19;

  return properties.every(({ id, values }) => {
    if (id === 'B' || id === 'W') {
      return values.length === 1 && isValidCoordinate(values[0], boardSize, true);
    }
    if (id === 'AB' || id === 'AW') {
      return values.every((value) => isValidCoordinate(value, boardSize, false));
    }
    return true;
  });
}

function readFile(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '');
    reader.onerror = () => reject(reader.error ?? new Error('Unable to read file'));
    reader.readAsText(file);
  });
}

export default function ReportLocalImportDialog({
  open,
  loading = false,
  error = null,
  onClose,
  onSubmit,
}: ReportLocalImportDialogProps) {
  const { t } = useTranslation();
  const [title, setTitle] = useState('');
  const [sgfContent, setSgfContent] = useState('');
  const [fileReadError, setFileReadError] = useState(false);
  const [fileReading, setFileReading] = useState(false);
  const fileReadGenerationRef = useRef(0);

  useEffect(() => {
    if (!open) {
      fileReadGenerationRef.current += 1;
      setFileReading(false);
    }
    return () => { fileReadGenerationRef.current += 1; };
  }, [open]);

  const parsed = useMemo(() => {
    if (!isValidReportSgf(sgfContent)) return null;
    try {
      const result = sgfToMoves(sgfContent);
      const boardSize = result.metadata.boardSize ?? 19;
      return [9, 13, 19].includes(boardSize) ? result : null;
    } catch {
      return null;
    }
  }, [sgfContent]);

  const payload: LocalReportImportPayload | null = parsed ? {
    title: title.trim() || undefined,
    sgfContent: sgfContent.trim(),
    boardSize: parsed.metadata.boardSize ?? 19,
    rules: parsed.metadata.rules || 'chinese',
    komi: parsed.metadata.komi ?? 7.5,
    // 摆子不是着手 —— 后端的 total_moves 只数着手,这里跟着收口径。
    moveCount: parsed.moves.length - parsed.setupCount,
    playerBlack: parsed.metadata.playerBlack || undefined,
    playerWhite: parsed.metadata.playerWhite || undefined,
    blackRank: parsed.metadata.blackRank || undefined,
    whiteRank: parsed.metadata.whiteRank || undefined,
    result: parsed.metadata.result || undefined,
  } : null;

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const input = event.currentTarget;
    const generation = ++fileReadGenerationRef.current;
    setFileReadError(false);
    setFileReading(true);
    try {
      const content = await readFile(file);
      if (generation !== fileReadGenerationRef.current) return;
      setSgfContent(content);
      setTitle((current) => current || file.name.replace(/\.sgf$/i, ''));
    } catch {
      if (generation === fileReadGenerationRef.current) setFileReadError(true);
    } finally {
      if (generation === fileReadGenerationRef.current) setFileReading(false);
      input.value = '';
    }
  };
  const submit = (reportType?: ReportType) => {
    if (!payload || loading || fileReading) return;
    if (reportType) onSubmit(payload, reportType);
    else onSubmit(payload);
  };

  return (
    <Dialog
      open={open}
      onClose={() => { if (!loading) onClose(); }}
      fullWidth
      maxWidth={false}
      slotProps={{
        paper: {
          sx: {
            width: 'calc(100vw - 24px)',
            maxWidth: '960px',
            height: 'calc(100dvh - 24px)',
            maxHeight: '576px',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          },
        },
      }}
    >
      <DialogTitle sx={{ flexShrink: 0, py: 1.5 }}>
        {t('report:import_local', '导入本地 SGF')}
      </DialogTitle>
      <DialogContent
        data-testid="report-local-import-content"
        dividers
        sx={{ minWidth: 0, minHeight: 0, overflowY: 'auto', overflowX: 'hidden', py: 1.5 }}
      >
        <Stack spacing={1.5}>
          {error && <Alert severity="error">{error}</Alert>}
          <TextField
            label={t('report:title_optional', '标题（可选）')}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            disabled={loading || fileReading}
            fullWidth
            slotProps={{
              htmlInput: { style: { minHeight: 48, minWidth: 48, boxSizing: 'border-box' } },
              input: { sx: { minHeight: 48, minWidth: 48 } },
            }}
          />
          <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
            <Button
              component="label"
              variant="outlined"
              startIcon={<UploadFileIcon />}
              disabled={loading}
              sx={actionButtonSx}
            >
              {t('report:choose_file', '选择本地文件')}
              <input
                hidden
                type="file"
                accept=".sgf,.txt,application/x-go-sgf,text/plain"
                aria-label={t('report:choose_file', '选择本地文件')}
                onChange={(event) => { void handleFileChange(event); }}
                disabled={loading}
              />
            </Button>
            <Typography variant="body2" color="text.secondary" sx={{ minWidth: 0, overflowWrap: 'anywhere' }}>
              {t('report:choose_file_hint', '可选择文件，也可直接粘贴 SGF 内容。')}
            </Typography>
          </Stack>
          <Divider />
          <TextField
            label={t('report:sgf_content', 'SGF 内容')}
            value={sgfContent}
            onChange={(event) => {
              setFileReadError(false);
              setSgfContent(event.target.value);
            }}
            disabled={loading || fileReading}
            multiline
            minRows={5}
            fullWidth
            slotProps={{
              htmlInput: { style: { minHeight: 48, minWidth: 48, boxSizing: 'border-box' } },
              input: { sx: { minHeight: 48, minWidth: 48 } },
            }}
            placeholder="(;FF[4]GM[1]SZ[19];B[pd];W[dd])"
          />
          {fileReadError && (
            <Typography role="alert" color="error.main" variant="body2">
              {t('report:file_read_failed', '读取文件失败，请重试。')}
            </Typography>
          )}
          {!fileReadError && sgfContent.trim() && !payload && (
            <Typography role="alert" color="error.main" variant="body2">
              {t('report:invalid_sgf', '无法解析 SGF，请检查内容。')}
            </Typography>
          )}
          {payload && (
            <Stack
              data-testid="local-import-metadata"
              direction="row"
              gap={2}
              flexWrap="wrap"
              sx={{ minWidth: 0 }}
            >
              <Typography variant="body2" color="text.secondary">{payload.boardSize} × {payload.boardSize}</Typography>
              <Typography variant="body2" color="text.secondary">{t('report:rules_label', '规则')}：{payload.rules}</Typography>
              <Typography variant="body2" color="text.secondary">{t('report:komi_label', '贴目')}：{payload.komi}</Typography>
              <Typography variant="body2" color="text.secondary">{payload.moveCount} {t('report:moves_unit', '手')}</Typography>
            </Stack>
          )}
        </Stack>
      </DialogContent>
      <DialogActions
        data-testid="report-local-import-actions"
        sx={{
          flexShrink: 0,
          overflowX: 'hidden',
          display: 'grid',
          gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
          gap: 1,
          p: 1.5,
          '& > :not(style) ~ :not(style)': { ml: 0 },
        }}
      >
        <Button disabled={loading} onClick={onClose} sx={actionButtonSx}>{t('common:cancel', '取消')}</Button>
        <Button disabled={loading || fileReading || !payload} onClick={() => submit()} sx={actionButtonSx}>
          {loading ? t('report:importing', '正在导入…') : t('report:import_only', '仅导入')}
        </Button>
        <Button variant="contained" disabled={loading || fileReading || !payload} onClick={() => submit('normal')} sx={actionButtonSx}>
          {t('report:import_and_normal', '导入并生成普通复盘')}
        </Button>
        <Button variant="outlined" disabled={loading || fileReading || !payload} onClick={() => submit('deep')} sx={actionButtonSx}>
          {t('report:import_and_deep', '导入并生成深度复盘')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
