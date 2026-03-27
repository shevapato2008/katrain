import { useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import Chip from '@mui/material/Chip';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import { TutorialAPI } from '../../api/tutorialApi';
import type { RecognitionDebug } from '../../types/tutorial';

interface Props {
  debug: RecognitionDebug;
}

function Section({ title, step, defaultOpen, children }: {
  title: string; step: string; defaultOpen?: boolean; children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen ?? false);
  return (
    <Box sx={{ mb: 1, border: '1px solid #e0e0e0', borderRadius: 1, overflow: 'hidden' }}>
      <Box
        onClick={() => setOpen(!open)}
        sx={{
          display: 'flex', alignItems: 'center', gap: 1, px: 1.5, py: 0.75,
          bgcolor: '#f5f5f5', cursor: 'pointer', '&:hover': { bgcolor: '#eeeeee' },
        }}
      >
        <Chip label={step} size="small" variant="outlined" sx={{ fontFamily: 'monospace', fontSize: 11 }} />
        <Typography variant="body2" sx={{ flex: 1, fontWeight: 500 }}>{title}</Typography>
        <IconButton size="small">{open ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}</IconButton>
      </Box>
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
        Recognition Pipeline
      </Typography>

      {/* Step 0: Bbox detection */}
      <Section title="Bbox Detection" step="S0">
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

      {/* Step 1: Region identification */}
      <Section title="Region (col_start, row_start)" step="S1">
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

      {/* Step 2-3: Grid + Occupied detection */}
      <Section title="Grid + Occupied Detection" step="S2-3" defaultOpen>
        <DebugImage path={debug.cv_detection?.debug_image} alt="grid detection" />
        {debug.cv_detection && (
          <Box mt={0.5}>
            <KV label="Spacing" value={`${debug.cv_detection.spacing?.toFixed(1)}px`} />
            <KV label="Occupied" value={
              `${debug.cv_detection.total_occupied} total (${debug.cv_detection.confident_count} confident, ${debug.cv_detection.ambiguous_count} ambiguous)`
            } />
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              Green = CV-confident, Yellow = needs VLLM
            </Typography>
          </Box>
        )}
      </Section>

      {/* Step 4: VLLM classification */}
      <Section title="VLLM Classification" step="S4" defaultOpen>
        <DebugImage path={debug.classification?.annotated_crop ?? debug.classification?.contact_sheet} alt="annotated crop" />
        {debug.classification?.classifications && (
          <Box mt={1} sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {Object.entries(debug.classification.classifications).map(([label, cls]) => {
              const isConfidentCV = debug.classification?.confident_cv?.[label];
              const color = cls === 'empty' ? 'default'
                : cls.startsWith('black') ? 'info'
                : cls.startsWith('white') ? 'warning'
                : 'secondary';
              return (
                <Chip
                  key={label}
                  label={`${label}: ${cls}`}
                  size="small"
                  color={color}
                  variant={isConfidentCV ? 'filled' : 'outlined'}
                  sx={{ fontFamily: 'monospace', fontSize: 10 }}
                />
              );
            })}
          </Box>
        )}
        {debug.classification?.confident_cv && Object.keys(debug.classification.confident_cv).length > 0 && (
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
            Filled chips = CV pre-classified, Outlined = VLLM classified
          </Typography>
        )}
      </Section>
    </Box>
  );
}
