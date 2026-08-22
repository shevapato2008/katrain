import { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Collapse from '@mui/material/Collapse';
import ButtonBase from '@mui/material/ButtonBase';
import Chip from '@mui/material/Chip';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { TutorialAPI } from '../../api/tutorialApi';
import type { RecognitionDebug } from '../../../types/tutorial';

interface Props {
  debug: RecognitionDebug;
}

function Section({ title, step, defaultOpen, children }: {
  title: string; step: string; defaultOpen?: boolean; children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  return (
    <Box sx={{ mb: 1, border: '1px solid #e0e0e0', borderRadius: 1, overflow: 'hidden' }}>
      {/* 这一行原来是**挂 onClick 的 div**，里面再套一个既没有 onClick 也没有名字的
          IconButton —— 它能用只是因为点击冒泡到了外面那个 div。于是：键盘到不了，
          读屏念不出，控件账本把这五步整整记成五个空按钮。
          改成真的按钮（名字取小节标题，展开态用 aria-expanded 报告），
          右侧的箭头降级成纯图标（按钮里不能再嵌按钮）。 */}
      <ButtonBase
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label={title}
        sx={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 1, px: 1.5, py: 0.75,
          bgcolor: '#f5f5f5', textAlign: 'left', '&:hover': { bgcolor: '#eeeeee' },
        }}
      >
        <Chip label={step} size="small" variant="outlined" sx={{ fontFamily: 'monospace', fontSize: 11, color: '#333', borderColor: '#999' }} />
        <Typography variant="body2" sx={{ flex: 1, fontWeight: 500, color: '#333' }}>{title}</Typography>
        <Box sx={{ display: 'flex', color: '#555' }}>
          {open ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
        </Box>
      </ButtonBase>
      <Collapse in={open}>
        <Box sx={{ p: 1.5 }}>{children}</Box>
      </Collapse>
    </Box>
  );
}

function DebugImage({ path, alt }: { path?: string; alt: string }) {
  if (!path) return <Typography variant="caption" color="text.secondary">No debug image</Typography>;
  return (
    <Box
      component="img"
      src={TutorialAPI.assetUrl(path)}
      alt={alt}
      sx={{ width: '100%', borderRadius: 0.5, border: '1px solid #ddd' }}
    />
  );
}

function KV({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Box sx={{ display: 'flex', gap: 1, mb: 0.25 }}>
      <Typography variant="caption" color="text.secondary" sx={{ minWidth: 80 }}>{label}:</Typography>
      <Typography variant="caption">{value}</Typography>
    </Box>
  );
}

export default function RecognitionDebugPanel({ debug }: Props) {
  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="subtitle2" sx={{ mb: 1, color: 'text.secondary' }}>
        识别流程 Recognition Pipeline
      </Typography>

      {/* Step 0: Bbox detection */}
      <Section title="S0 画框检测 — 识别页面中每张棋谱图的位置" step="S0">
        <DebugImage path={debug.bbox?.debug_image} alt="bbox detection" />
        {debug.bbox && (
          <Box mt={0.5}>
            <KV label="Method" value={debug.bbox.method} />
            {debug.bbox.bbox && (
              <KV label="Bbox" value={`[${debug.bbox.bbox.join(', ')}]`} />
            )}
          </Box>
        )}
      </Section>

      {/* Step 1: Deskew + Grid detection */}
      <Section title="S1 纠偏与网格 — 扫描纠偏 + 检测到的网格线" step="S1" defaultOpen>
        <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
          <Box sx={{ flex: '1 1 45%', minWidth: 200 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              原图 + 网格线（验证纠偏效果）
            </Typography>
            <DebugImage path={debug.deskew?.debug_image} alt="grid lines on original crop" />
          </Box>
          <Box sx={{ flex: '1 1 45%', minWidth: 200 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              纠偏后 + 网格线（验证网格匹配）
            </Typography>
            <DebugImage path={debug.deskew?.grid_image} alt="grid lines on deskewed crop" />
          </Box>
        </Box>
        <Box mt={0.5}>
          {debug.deskew && (
            <KV label="纠偏角度" value={debug.deskew.angle !== 0 ? `${debug.deskew.angle.toFixed(2)}°` : '无需纠偏'} />
          )}
        </Box>
      </Section>

      {/* Step 2: Occupied intersection detection */}
      <Section title="S2 落子检测 — 检测到的落子点标注" step="S2">
        <DebugImage path={debug.cv_detection?.debug_image} alt="occupied detection" />
        {debug.cv_detection && (
          <Box mt={0.5}>
            <KV label="Spacing" value={`${debug.cv_detection.spacing?.toFixed(1)}px`} />
            <KV label="Occupied" value={
              `${debug.cv_detection.total_occupied} total (${debug.cv_detection.confident_count} confident, ${debug.cv_detection.ambiguous_count} ambiguous)`
            } />
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              绿色=CV高置信, 黄色=需要VLLM确认
            </Typography>
          </Box>
        )}
      </Section>

      {/* Step 3: Region calibration */}
      <Section title="S3 棋盘定位 — 确定棋谱在19×19棋盘中的区域" step="S3">
        {debug.crop_image && <DebugImage path={debug.crop_image} alt="board crop" />}
        {debug.region && (
          <Box mt={0.5}>
            <KV label="Method" value={debug.region.method} />
            <KV label="Position" value={`col_start=${debug.region.col_start}, row_start=${debug.region.row_start}`} />
            <KV label="Grid" value={`${debug.region.grid_cols}×${debug.region.grid_rows}`} />
            {debug.region.confidence !== undefined && (
              <KV label="Confidence" value={`${(debug.region.confidence * 100).toFixed(0)}%`} />
            )}
            {debug.region.evidence && (
              <KV label="Evidence" value={debug.region.evidence.join(', ')} />
            )}
          </Box>
        )}
      </Section>

      {/* Step 4: VLLM classification */}
      <Section title="S4 落子识别 — 识别每个落子点的黑白、手数、标记" step="S4" defaultOpen>
        <DebugImage path={debug.classification?.annotated_crop ?? debug.classification?.contact_sheet} alt="annotated crop" />
        {debug.classification?.classifications && (
          <Box mt={1} sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {Object.entries(debug.classification.classifications).map(([label, cls]) => {
              const cvResult = debug.classification?.cv_preclass?.[label] ?? debug.classification?.confident_cv?.[label];
              const isCV = cvResult && cvResult !== 'ambiguous';
              const patchPath = debug.classification?.patch_images?.[label];
              const color = cls === 'empty' ? 'default'
                : cls.startsWith('black') ? 'info'
                : cls.startsWith('white') ? 'warning'
                : 'secondary';
              return (
                <Box key={label} sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 0.25, minWidth: 56 }}>
                  {patchPath ? (
                    <Box
                      component="img"
                      src={TutorialAPI.assetUrl(patchPath)}
                      alt={`patch ${label}`}
                      sx={{ width: 48, height: 48, objectFit: 'contain', borderRadius: 0.5, border: '1px solid #ccc' }}
                    />
                  ) : (
                    <Box sx={{ width: 48, height: 48, bgcolor: '#f0f0f0', borderRadius: 0.5, border: '1px solid #ddd' }} />
                  )}
                  {cvResult && (
                    <Typography variant="caption" sx={{ fontSize: 9, color: isCV ? '#4caf50' : '#999', fontFamily: 'monospace' }}>
                      CV:{cvResult}
                    </Typography>
                  )}
                  <Chip
                    label={`${label}: ${cls}`}
                    size="small"
                    color={color}
                    variant={isCV ? 'filled' : 'outlined'}
                    sx={{ fontFamily: 'monospace', fontSize: 10 }}
                  />
                </Box>
              );
            })}
          </Box>
        )}
        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
          CV:black/white=CV直接判定, CV:ambiguous=需Haiku判定; 实心chip=CV结果, 空心chip=Haiku结果
        </Typography>
      </Section>
    </Box>
  );
}
