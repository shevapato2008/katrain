/**
 * Read-only status panel for physical-board tsumego (Phase D). NO emoji — SBC ships no
 * emoji font; celebration uses the EmojiEvents trophy SVG.
 *
 * Consumes the REAL hook's `PhysicalTsumegoState` (see .superpowers/sdd/phase-D-real-contract.md,
 * "Panel (D1.2)"). Everything visual is DERIVED from `state.phase` — there is no
 * `state.ledIntent` / `state.removalList` / `state.setupProgress` on the real (or stub) shape.
 */

import type { ComponentType } from 'react';
import { Box, Chip, IconButton, Typography } from '@mui/material';
import { keyframes } from '@mui/system';
import type { SvgIconProps } from '@mui/material';
import { PanTool, TouchApp, Reply, DeleteSweep, EmojiEvents, Close } from '@mui/icons-material';
import { LED_HEX, LED_LABEL, type LedIntent } from '../../constants/ledColors';
import type { PhysicalTsumegoState, PhysicalPhase } from '../../hooks/usePhysicalTsumego';

interface PhysicalStatePanelProps {
  state: PhysicalTsumegoState;
  onDismiss?: () => void;
}

interface PhaseVisual {
  icon: ComponentType<SvgIconProps>;
  titleZh: string;
  intent: LedIntent | null;
  testid: string;
}

/** Phase -> visual-state map (A-E), matching tsumego-states.html. Everything is derived
 *  from `phase` alone — no invented fields on the real hook's state. */
function phaseVisual(phase: PhysicalPhase): PhaseVisual | null {
  switch (phase) {
    case 'setup': // A 摆放黑棋
      return { icon: PanTool, titleZh: '摆放黑棋', intent: 'black', testid: 'phase-setup' };
    case 'ready': // B 做题中 (dual-input: screen click + physical placement)
      return { icon: TouchApp, titleZh: '做题中', intent: null, testid: 'phase-ready' };
    case 'replying': // C 应手
      return { icon: Reply, titleZh: '应手', intent: 'white', testid: 'phase-replying' };
    case 'removing': // D 答错拿除
      return { icon: DeleteSweep, titleZh: '答错拿除', intent: 'remove', testid: 'phase-removing' };
    case 'solved': // E 答对
      return { icon: EmojiEvents, titleZh: '答对', intent: 'hint', testid: 'phase-solved' };
    case 'off':
    case 'clearing':
    case 'clearing_next':
    case 'restoring':
    default:
      return null;
  }
}

/** Small inline LED advisory chip: dot + label, colours read from LED_HEX/LED_LABEL only. */
const LedChip = ({ intent }: { intent: LedIntent }) => (
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
    <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: LED_HEX[intent] }} />
    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
      {LED_LABEL[intent]}
    </Typography>
  </Box>
);

// State-E celebration: white double-blink mirroring the real machine's LED double-flash
// cadence (opacity 1 -> 0.2 -> 1, twice, ~350ms each).
const doubleBlink = keyframes`
  0%   { opacity: 1; }
  25%  { opacity: 0.2; }
  50%  { opacity: 1; }
  75%  { opacity: 0.2; }
  100% { opacity: 1; }
`;

const PhysicalStatePanel = ({ state, onDismiss }: PhysicalStatePanelProps) => {
  const visual = phaseVisual(state.phase);
  if (!visual) return null;

  const { icon: Icon, titleZh, intent, testid } = visual;
  const isSolved = state.phase === 'solved';

  return (
    <Box
      data-testid="physical-state-panel"
      data-phase={state.phase}
      sx={{
        bgcolor: 'var(--raise2)',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        p: 1.5,
      }}
    >
      {/* `testid` on the row (not the icon) so MUI's own auto `{Name}Icon` data-testid
          (from @mui/icons-material's createSvgIcon) stays intact for icon assertions. */}
      <Box data-testid={testid} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Icon
          sx={{
            // Non-LED phases (currently just 'ready' / 进行中) get the single amber
            // accent token — never a local hex — instead of an LED colour.
            color: intent ? LED_HEX[intent] : 'warning.main',
            animation: isSolved ? `${doubleBlink} 0.7s ease-in-out 2` : undefined,
          }}
        />
        <Typography variant="subtitle1" sx={{ flex: 1 }}>
          {titleZh}
        </Typography>
        {intent && <LedChip intent={intent} />}
        {onDismiss && (
          <IconButton onClick={onDismiss} data-testid="physical-state-dismiss" size="small">
            <Close fontSize="small" />
          </IconButton>
        )}
      </Box>

      {state.phase === 'ready' && (
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.5 }}>
          屏幕点击 + 实体落子
        </Typography>
      )}

      {state.phase === 'setup' && (
        <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mt: 0.5 }}>
          {state.stageMatched ?? 0} / {state.stageTotal ?? 0}
        </Typography>
      )}

      {state.phase === 'removing' && (state.extra ?? []).length > 0 && (
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 1 }}>
          {/* voice-cue slot: real track wires speak('wrong_remove') here — stub silent */}
          {(state.extra ?? []).map(([row, col], i) => (
            <Chip
              key={`${row}-${col}-${i}`}
              data-testid="removal-item"
              size="small"
              label={`拿除 (${row},${col})`}
              sx={{ bgcolor: LED_HEX.remove, color: 'common.white' }}
            />
          ))}
        </Box>
      )}
    </Box>
  );
};

export default PhysicalStatePanel;
