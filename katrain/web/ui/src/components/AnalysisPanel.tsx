import React, { useState } from 'react';
import { 
  Box, Typography, Divider, Paper, Table, TableBody, TableCell, 
  TableContainer, TableHead, TableRow, IconButton, Tooltip, Tabs, Tab 
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import ContentCutIcon from '@mui/icons-material/ContentCut';
import CallMergeIcon from '@mui/icons-material/CallMerge';
import UnfoldLessIcon from '@mui/icons-material/UnfoldLess';
import { type GameState } from '../api';

interface AnalysisPanelProps {
  gameState: GameState | null;
  onNodeAction?: (action: string) => void;
}

const AnalysisPanel: React.FC<AnalysisPanelProps> = ({ gameState, onNodeAction }) => {
  const [tabValue, setTabValue] = useState(0);

  if (!gameState) return null;

  const analysis = gameState.analysis;
  const topMoves = analysis?.moves || [];
  
  // Get point loss for current node
  const currentNodeId = gameState.current_node_id;
  const currentNode = gameState.history.find(h => h.node_id === currentNodeId);
  // Actually stones array in state has score_loss
  const currentStone = gameState.stones.find(s => s[1] && gameState.last_move && s[1][0] === gameState.last_move[0] && s[1][1] === gameState.last_move[1]);
  const pointsLost = currentStone ? currentStone[2] : null;

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', bgcolor: '#f5f5f5' }}>
      <Box sx={{ p: 0.5, bgcolor: '#e0e0e0', display: 'flex', justifyContent: 'flex-end', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', gap: 0 }}>
          <Tooltip title="Delete Node">
            <IconButton size="small" onClick={() => onNodeAction?.('delete')}><DeleteIcon fontSize="small" /></IconButton>
          </Tooltip>
          <Tooltip title="Prune Branch">
            <IconButton size="small" onClick={() => onNodeAction?.('prune')}><ContentCutIcon fontSize="small" /></IconButton>
          </Tooltip>
          <Tooltip title="Make Main Branch">
            <IconButton size="small" onClick={() => onNodeAction?.('make-main')}><CallMergeIcon fontSize="small" /></IconButton>
          </Tooltip>
          <Tooltip title="Collapse/Expand Branch">
            <IconButton size="small" onClick={() => onNodeAction?.('toggle-collapse')}><UnfoldLessIcon fontSize="small" /></IconButton>
          </Tooltip>
        </Box>
      </Box>
      
      <Box sx={{ p: 1, bgcolor: '#fff', borderBottom: '1px solid #ddd' }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="caption" color="textSecondary">Win Rate</Typography>
            <Typography variant="body2" fontWeight="bold" sx={{ color: '#2e7d32' }}>
              {analysis ? `${(analysis.winrate * 100).toFixed(1)}%` : '--'}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="caption" color="textSecondary">Estimated Score</Typography>
            <Typography variant="body2" fontWeight="bold" sx={{ color: '#0288d1' }}>
              {analysis ? (analysis.score >= 0 ? `B+${analysis.score.toFixed(1)}` : `W+${Math.abs(analysis.score).toFixed(1)}`) : '--'}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="caption" color="textSecondary">Points Lost</Typography>
            <Typography variant="body2" fontWeight="bold" sx={{ color: pointsLost && pointsLost > 2 ? '#d32f2f' : '#fbc02d' }}>
              {pointsLost !== null ? pointsLost.toFixed(1) : '--'}
            </Typography>
          </Box>
        </Box>
      </Box>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', bgcolor: '#fff' }}>
        <Tabs value={tabValue} onChange={handleTabChange} variant="fullWidth" size="small" sx={{ minHeight: 32 }}>
          <Tab label="Info" sx={{ py: 0.5, minHeight: 32, fontSize: '0.75rem' }} />
          <Tab label="Details" sx={{ py: 0.5, minHeight: 32, fontSize: '0.75rem' }} />
          <Tab label="Notes" sx={{ py: 0.5, minHeight: 32, fontSize: '0.75rem' }} />
        </Tabs>
      </Box>

      <Box sx={{ flexGrow: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {tabValue === 0 && (
          <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
            {analysis ? (
              <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 0 }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ fontSize: '0.7rem', py: 0.5, fontWeight: 'bold' }}>Move</TableCell>
                      <TableCell sx={{ fontSize: '0.7rem', py: 0.5, fontWeight: 'bold' }} align="right">Loss</TableCell>
                      <TableCell sx={{ fontSize: '0.7rem', py: 0.5, fontWeight: 'bold' }} align="right">Win%</TableCell>
                      <TableCell sx={{ fontSize: '0.7rem', py: 0.5, fontWeight: 'bold' }} align="right">Visits</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {topMoves.slice(0, 20).map((move: any, index: number) => (
                      <TableRow key={index} hover>
                        <TableCell sx={{ fontSize: '0.7rem', py: 0.3 }}>{move.move}</TableCell>
                        <TableCell align="right" sx={{ fontSize: '0.7rem', py: 0.3, color: move.scoreLoss > 2 ? 'error.main' : 'text.primary' }}>
                          {move.scoreLoss.toFixed(1)}
                        </TableCell>
                        <TableCell sx={{ fontSize: '0.7rem', py: 0.3 }} align="right">{(move.winrate * 100).toFixed(1)}%</TableCell>
                        <TableCell sx={{ fontSize: '0.7rem', py: 0.3 }} align="right">{move.visits}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : (
              <Box sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="caption" color="textSecondary">Analyzing move...</Typography>
              </Box>
            )}
          </Box>
        )}
        
        {tabValue === 1 && (
          <Box sx={{ p: 2, overflow: 'auto' }}>
            <Typography variant="caption" color="textSecondary">Detailed analysis data will appear here.</Typography>
          </Box>
        )}

        {tabValue === 2 && (
          <Box sx={{ p: 1, flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
            <textarea 
              style={{ 
                flexGrow: 1, 
                width: '100%', 
                padding: '8px', 
                border: '1px solid #ddd', 
                borderRadius: '4px',
                fontFamily: 'inherit',
                fontSize: '0.8rem',
                resize: 'none'
              }}
              placeholder="Your SGF notes for this position here."
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