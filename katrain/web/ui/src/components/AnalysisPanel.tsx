import React, { useState } from 'react';
import { 
  Box, Typography, Paper, Table, TableBody, TableCell, 
  TableContainer, TableHead, TableRow, IconButton, Tooltip, Tabs, Tab 
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import ContentCutIcon from '@mui/icons-material/ContentCut';
import CallMergeIcon from '@mui/icons-material/CallMerge';
import UnfoldLessIcon from '@mui/icons-material/UnfoldLess';
import { type GameState } from '../api';
import { useTranslation } from '../hooks/useTranslation';

interface AnalysisPanelProps {
  gameState: GameState | null;
  onNodeAction?: (action: string) => void;
  onShowPV?: (pv: string) => void;
  onClearPV?: () => void;
}

const AnalysisPanel: React.FC<AnalysisPanelProps> = ({ gameState, onNodeAction, onShowPV, onClearPV }) => {
  const [tabValue, setTabValue] = useState(0);
  const { t } = useTranslation();

  if (!gameState) return null;

  const analysis = gameState.analysis;
  const topMoves = analysis?.moves || [];
  
  // Get point loss for current node
  const currentStone = gameState.stones.find(s => s[1] && gameState.last_move && s[1][0] === gameState.last_move[0] && s[1][1] === gameState.last_move[1]);
  const pointsLost = currentStone ? currentStone[2] : null;

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  const renderRichText = (text: string) => {
    if (!text) return null;
    
    // Simple parser for [b], [i], [u], [color=...], [ref=...]
    const parts = text.split(/(\[.*?\])/g);
    let key = 0;
    const elements: React.ReactNode[] = [];
    const stack: { type: string, props?: any }[] = [];

    parts.forEach(part => {
      if (part.startsWith('[') && part.endsWith(']')) {
        const tag = part.slice(1, -1);
        if (tag.startsWith('/')) {
          stack.pop();
        } else {
          const [name, val] = tag.split('=');
          stack.push({ type: name, props: val });
        }
      } else if (part) {
        let element: React.ReactNode = part;
        [...stack].reverse().forEach(style => {
          if (style.type === 'u') element = <u key={key++}>{element}</u>;
          if (style.type === 'b') element = <strong key={key++}>{element}</strong>;
          if (style.type === 'i') element = <em key={key++}>{element}</em>;
          if (style.type === 'color') element = <span key={key++} style={{ color: style.props }}>{element}</span>;
          if (style.type === 'ref') {
             element = (
               <Typography 
                 component="span" 
                 key={key++} 
                 sx={{ 
                   cursor: 'pointer', 
                   color: 'primary.main', 
                   textDecoration: 'underline',
                   fontSize: 'inherit',
                   '&:hover': { color: 'primary.dark' }
                 }}
                 onMouseEnter={() => onShowPV?.(style.props)}
                 onMouseLeave={() => onClearPV?.()}
                 onClick={() => onShowPV?.(style.props)}
               >
                 {element}
               </Typography>
             );
          }
        });
        elements.push(<React.Fragment key={key++}>{element}</React.Fragment>);
      }
    });

    return <Typography variant="body2" component="div" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.8rem' }}>{elements}</Typography>;
  };

  const iconButtonStyles = {
    color: '#b8b5b0',
    '&:hover': {
      bgcolor: 'rgba(255, 255, 255, 0.05)',
      color: '#f5f3f0',
    },
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', bgcolor: '#1a1a1a' }}>
      <Box sx={{
        p: 1,
        bgcolor: '#252525',
        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
        display: 'flex',
        justifyContent: 'flex-end',
        alignItems: 'center'
      }}>
        <Box sx={{ display: 'flex', gap: 0.5 }}>
          <Tooltip title={t("Delete Node")}>
            <IconButton size="small" onClick={() => onNodeAction?.('delete')} sx={iconButtonStyles}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={t("Prune Branch")}>
            <IconButton size="small" onClick={() => onNodeAction?.('prune')} sx={iconButtonStyles}>
              <ContentCutIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={t("Make Main Branch")}>
            <IconButton size="small" onClick={() => onNodeAction?.('make-main')} sx={iconButtonStyles}>
              <CallMergeIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={t("Collapse/Expand Branch")}>
            <IconButton size="small" onClick={() => onNodeAction?.('toggle-collapse')} sx={iconButtonStyles}>
              <UnfoldLessIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <Box sx={{
        p: 1.5,
        bgcolor: '#2a2a2a',
        borderBottom: '1px solid rgba(255, 255, 255, 0.05)'
      }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography
              variant="caption"
              sx={{
                color: '#7a7772',
                fontSize: '0.7rem',
                fontWeight: 500,
                letterSpacing: '0.5px',
                textTransform: 'uppercase'
              }}
            >
              {t("stats:winrate")}
            </Typography>
            <Typography
              variant="body2"
              fontWeight={600}
              sx={{
                color: '#4a6b5c',
                fontSize: '0.875rem',
                fontFamily: 'var(--font-mono)'
              }}
            >
              {analysis ? `${(analysis.winrate * 100).toFixed(1)}%` : '--'}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography
              variant="caption"
              sx={{
                color: '#7a7772',
                fontSize: '0.7rem',
                fontWeight: 500,
                letterSpacing: '0.5px',
                textTransform: 'uppercase'
              }}
            >
              {t("stats:score")}
            </Typography>
            <Typography
              variant="body2"
              fontWeight={600}
              sx={{
                color: '#5d8270',
                fontSize: '0.875rem',
                fontFamily: 'var(--font-mono)'
              }}
            >
              {analysis ? (analysis.score >= 0 ? `B+${analysis.score.toFixed(1)}` : `W+${Math.abs(analysis.score).toFixed(1)}`) : '--'}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography
              variant="caption"
              sx={{
                color: '#7a7772',
                fontSize: '0.7rem',
                fontWeight: 500,
                letterSpacing: '0.5px',
                textTransform: 'uppercase'
              }}
            >
              {t("stats:pointslost")}
            </Typography>
            <Typography
              variant="body2"
              fontWeight={600}
              sx={{
                color: pointsLost && pointsLost > 2 ? '#e16b5c' : '#d4a574',
                fontSize: '0.875rem',
                fontFamily: 'var(--font-mono)'
              }}
            >
              {pointsLost !== null ? pointsLost.toFixed(1) : '--'}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography
              variant="caption"
              sx={{
                color: '#7a7772',
                fontSize: '0.7rem',
                fontWeight: 500,
                letterSpacing: '0.5px',
                textTransform: 'uppercase'
              }}
            >
              {t("Visits")}
            </Typography>
            <Typography
              variant="body2"
              fontWeight={600}
              sx={{
                color: '#b8b5b0',
                fontSize: '0.875rem',
                fontFamily: 'var(--font-mono)'
              }}
            >
              {analysis ? analysis.visits : '--'}
            </Typography>
          </Box>
        </Box>
      </Box>

      <Box sx={{
        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
        bgcolor: '#252525'
      }}>
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          variant="fullWidth"
          sx={{
            minHeight: 40,
            '& .MuiTabs-indicator': {
              backgroundColor: '#4a6b5c',
              height: 2,
            }
          }}
        >
          <Tab
            label={t("Info")}
            sx={{
              py: 1,
              minHeight: 40,
              fontSize: '0.8rem',
              color: '#7a7772',
              fontWeight: 500,
              '&.Mui-selected': {
                color: '#f5f3f0',
                fontWeight: 600,
              },
              '&:hover': {
                color: '#b8b5b0',
                bgcolor: 'rgba(255, 255, 255, 0.02)',
              },
              transition: 'all 200ms',
            }}
          />
          <Tab
            label={t("Details")}
            sx={{
              py: 1,
              minHeight: 40,
              fontSize: '0.8rem',
              color: '#7a7772',
              fontWeight: 500,
              '&.Mui-selected': {
                color: '#f5f3f0',
                fontWeight: 600,
              },
              '&:hover': {
                color: '#b8b5b0',
                bgcolor: 'rgba(255, 255, 255, 0.02)',
              },
              transition: 'all 200ms',
            }}
          />
          <Tab
            label={t("Notes")}
            sx={{
              py: 1,
              minHeight: 40,
              fontSize: '0.8rem',
              color: '#7a7772',
              fontWeight: 500,
              '&.Mui-selected': {
                color: '#f5f3f0',
                fontWeight: 600,
              },
              '&:hover': {
                color: '#b8b5b0',
                bgcolor: 'rgba(255, 255, 255, 0.02)',
              },
              transition: 'all 200ms',
            }}
          />
        </Tabs>
      </Box>

      <Box sx={{ flexGrow: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {tabValue === 0 && (
          <Box sx={{ flexGrow: 1, overflow: 'auto', bgcolor: '#1a1a1a' }}>
            {analysis ? (
              <TableContainer
                component={Paper}
                elevation={0}
                sx={{
                  borderRadius: 0,
                  bgcolor: '#1a1a1a',
                  '& .MuiTable-root': {
                    '& .MuiTableCell-root': {
                      borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                    }
                  }
                }}
              >
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell
                        sx={{
                          fontSize: '0.7rem',
                          py: 1,
                          fontWeight: 600,
                          bgcolor: '#252525',
                          color: '#7a7772',
                          letterSpacing: '0.5px',
                          textTransform: 'uppercase',
                          fontFamily: 'var(--font-sans)',
                        }}
                      >
                        {t("Move")}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          fontSize: '0.7rem',
                          py: 1,
                          fontWeight: 600,
                          bgcolor: '#252525',
                          color: '#7a7772',
                          letterSpacing: '0.5px',
                          textTransform: 'uppercase',
                          fontFamily: 'var(--font-sans)',
                        }}
                      >
                        {t("Loss")}
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          fontSize: '0.7rem',
                          py: 1,
                          fontWeight: 600,
                          bgcolor: '#252525',
                          color: '#7a7772',
                          letterSpacing: '0.5px',
                          textTransform: 'uppercase',
                          fontFamily: 'var(--font-sans)',
                        }}
                      >
                        Win%
                      </TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          fontSize: '0.7rem',
                          py: 1,
                          fontWeight: 600,
                          bgcolor: '#252525',
                          color: '#7a7772',
                          letterSpacing: '0.5px',
                          textTransform: 'uppercase',
                          fontFamily: 'var(--font-sans)',
                        }}
                      >
                        {t("Visits")}
                      </TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {topMoves.slice(0, 20).map((move: any, index: number) => (
                      <TableRow
                        key={index}
                        sx={{
                          '&:hover': {
                            bgcolor: 'rgba(255, 255, 255, 0.02)',
                          },
                          transition: 'background-color 150ms',
                        }}
                      >
                        <TableCell
                          sx={{
                            fontSize: '0.75rem',
                            py: 0.75,
                            color: '#f5f3f0',
                            fontFamily: 'var(--font-mono)',
                            fontWeight: 600,
                          }}
                        >
                          {move.move}
                        </TableCell>
                        <TableCell
                          align="right"
                          sx={{
                            fontSize: '0.75rem',
                            py: 0.75,
                            color: move.scoreLoss > 2 ? '#e16b5c' : move.scoreLoss > 1 ? '#d4a574' : '#b8b5b0',
                            fontFamily: 'var(--font-mono)',
                            fontWeight: 500,
                          }}
                        >
                          {move.scoreLoss.toFixed(1)}
                        </TableCell>
                        <TableCell
                          align="right"
                          sx={{
                            fontSize: '0.75rem',
                            py: 0.75,
                            color: '#b8b5b0',
                            fontFamily: 'var(--font-mono)',
                            fontWeight: 500,
                          }}
                        >
                          {(move.winrate * 100).toFixed(1)}%
                        </TableCell>
                        <TableCell
                          align="right"
                          sx={{
                            fontSize: '0.75rem',
                            py: 0.75,
                            color: '#7a7772',
                            fontFamily: 'var(--font-mono)',
                            fontWeight: 400,
                          }}
                        >
                          {move.visits}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : (
              <Box sx={{ p: 3, textAlign: 'center' }}>
                <Typography
                  variant="caption"
                  sx={{
                    color: '#7a7772',
                    fontSize: '0.8rem',
                    fontStyle: 'italic'
                  }}
                >
                  {t("Analyzing move...")}
                </Typography>
              </Box>
            )}
          </Box>
        )}

        {tabValue === 1 && (
          <Box sx={{
            p: 2,
            overflow: 'auto',
            bgcolor: '#1a1a1a',
            color: '#f5f3f0',
            '& strong': { color: '#f5f3f0', fontWeight: 600 },
            '& em': { color: '#b8b5b0' },
            '& u': { textDecoration: 'underline', textDecorationColor: '#4a6b5c' },
          }}>
            {renderRichText(gameState.commentary)}
          </Box>
        )}

        {tabValue === 2 && (
          <Box sx={{ p: 1, flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#1a1a1a' }}>
            <textarea
              style={{
                flexGrow: 1,
                width: '100%',
                padding: '12px',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '4px',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.8rem',
                resize: 'none',
                backgroundColor: '#2a2a2a',
                color: '#f5f3f0',
                outline: 'none',
              }}
              placeholder={t("Your SGF notes for this position here.")}
              value={gameState.note || ''}
              readOnly
            />
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default AnalysisPanel;
