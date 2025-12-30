import { useState, useEffect } from 'react';
import { Box, CssBaseline, ThemeProvider, createTheme, Divider, Typography } from '@mui/material';
import { API, type GameState } from './api';
import Board from './components/Board';
import Sidebar from './components/Sidebar';
import ControlBar from './components/ControlBar';
import TopBar from './components/TopBar';
import AnalysisPanel from './components/AnalysisPanel';
import PlayerCard from './components/PlayerCard';
import ScoreGraph from './components/ScoreGraph';
import NewGameDialog from './components/NewGameDialog';
import AISettingsDialog from './components/AISettingsDialog';

const theme = createTheme({
  palette: {
    primary: {
      main: '#3f51b5',
    },
    background: {
      default: '#cfd8dc',
    },
  },
});

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>("Initializing...");
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isNewGameDialogOpen, setNewGameDialogOpen] = useState(false);
  const [isAISettingsDialogOpen, setAISettingsDialogOpen] = useState(false);
  const [analysisToggles, setAnalysisToggles] = useState<Record<string, boolean>>({
    children: false,
    eval: true,
    hints: true,
    policy: false,
    ownership: false
  });

  useEffect(() => {
    const initSession = async () => {
      try {
        const data = await API.createSession();
        setSessionId(data.session_id);
        setGameState(data.state);
        setStatusMessage("Ready");

        // Setup WebSocket
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws/${data.session_id}`);
        ws.onmessage = (event) => {
          const msg = JSON.parse(event.data);
          if (msg.type === 'game_update') {
            setGameState(msg.state);
          } else if (msg.type === 'log') {
            setStatusMessage(msg.data.message);
          }
        };
      } catch (error) {
        console.error("Failed to initialize session", error);
        setStatusMessage("Error: Failed to connect");
      }
    };
    initSession();
  }, []);

  const handleMove = async (x: number, y: number) => {
    if (!sessionId) return;
    try {
      const data = await API.playMove(sessionId, { x, y });
      setGameState(data.state);
    } catch (error) {
      console.error("Move failed", error);
    }
  };

  const handleAction = async (action: string) => {
    if (!sessionId) return;
    try {
      let data;
      if (action === 'pass') data = await API.playMove(sessionId, null);
      else if (action === 'back') data = await API.undo(sessionId, 1);
      else if (action === 'back-10') data = await API.undo(sessionId, 10);
      else if (action === 'start') data = await API.undo(sessionId, 9999);
      else if (action === 'forward') data = await API.redo(sessionId, 1);
      else if (action === 'forward-10') data = await API.redo(sessionId, 10);
      else if (action === 'end') data = await API.redo(sessionId, 9999);
      else if (action === 'ai-move') data = await API.aiMove(sessionId);
      
      if (data) setGameState(data.state);
    } catch (error) {
      console.error("Action failed", error);
    }
  };

  const handleNewGame = () => {
    setNewGameDialogOpen(true);
  };

  const handleNewGameConfirm = async (settings: any) => {
    if (!sessionId) return;
    try {
      const data = await API.newGame(sessionId, settings);
      setGameState(data.state);
      setNewGameDialogOpen(false);
      setSidebarOpen(false);
    } catch (error) {
      console.error("New game failed", error);
    }
  };

  const handleAISettingsConfirm = async (bw: 'B' | 'W', strategy: string) => {
    if (!sessionId) return;
    try {
      const data = await API.updatePlayer(sessionId, bw, undefined, strategy);
      setGameState(data.state);
    } catch (error) {
      console.error("AI Settings update failed", error);
    }
  };

  const handleLoadSGF = async (sgf: string) => {
    if (!sessionId) return;
    try {
      const data = await API.loadSGF(sessionId, sgf);
      setGameState(data.state);
      setSidebarOpen(false);
    } catch (error) {
      console.error("Load SGF failed", error);
    }
  };

  const handleSaveSGF = async () => {
    if (!sessionId) return;
    try {
      const { sgf } = await API.saveSGF(sessionId);
      const blob = new Blob([sgf], { type: 'application/x-go-sgf' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `katrain_${new Date().toISOString().replace(/[:.]/g, '-')}.sgf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Save SGF failed", error);
    }
  };

  const handleToggleChange = (toggle: string) => {
    setAnalysisToggles(prev => ({ ...prev, [toggle]: !prev[toggle] }));
  };

  const handleNavigate = async (nodeId: number) => {
    if (!sessionId) return;
    try {
      const data = await API.navigate(sessionId, nodeId);
      setGameState(data.state);
    } catch (error) {
      console.error("Navigation failed", error);
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {!sessionId || !gameState ? (
        <Box sx={{ display: 'flex', height: '100vh', justifyContent: 'center', alignItems: 'center', bgcolor: '#cfd8dc' }}>
          <Typography variant="h5">Initializing KaTrain...</Typography>
        </Box>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh', width: '100vw', overflow: 'hidden' }}>
          <TopBar 
            onMenuClick={() => setSidebarOpen(!isSidebarOpen)} 
            analysisToggles={analysisToggles} 
            onToggleChange={handleToggleChange}
            status={statusMessage}
          />
        
        <Box sx={{ flexGrow: 1, display: 'flex', overflow: 'hidden' }}>
          {isSidebarOpen && (
            <Sidebar 
              gameState={gameState} 
              onNewGame={handleNewGame} 
              onLoadSGF={handleLoadSGF} 
              onSaveSGF={handleSaveSGF} 
              onAISettings={() => setAISettingsDialogOpen(true)}
            />
          )}
          
          <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#cfd8dc', position: 'relative' }}>
            <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', p: 1 }}>
              {gameState && (
                <Board 
                  gameState={gameState} 
                  onMove={handleMove} 
                  analysisToggles={analysisToggles} 
                />
              )}
            </Box>
            <ControlBar onAction={handleAction} nextPlayer={gameState?.player_to_move || 'B'} />
          </Box>

          <Box sx={{ width: 320, display: 'flex', flexDirection: 'column', borderLeft: '1px solid #ddd', bgcolor: '#fafafa' }}>
            <Box sx={{ p: 1, display: 'flex', gap: 1 }}>
              {gameState && (
                <>
                  <PlayerCard 
                    player="B" 
                    info={gameState.players_info.B} 
                    captures={gameState.prisoner_count.B} 
                    active={gameState.player_to_move === 'B'} 
                  />
                  <PlayerCard 
                    player="W" 
                    info={gameState.players_info.W} 
                    captures={gameState.prisoner_count.W} 
                    active={gameState.player_to_move === 'W'} 
                  />
                </>
              )}
            </Box>
            <Divider />
            
            <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
              <AnalysisPanel gameState={gameState} />
            </Box>
            
            <Divider />
            <Box sx={{ p: 1, bgcolor: '#fff' }}>
              <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold' }}>GRAPH</Typography>
              <ScoreGraph gameState={gameState} onNavigate={handleNavigate} />
            </Box>
          </Box>
        </Box>
        <NewGameDialog 
          open={isNewGameDialogOpen} 
          onClose={() => setNewGameDialogOpen(false)} 
          onConfirm={handleNewGameConfirm} 
        />
        <AISettingsDialog
          open={isAISettingsDialogOpen}
          gameState={gameState}
          onClose={() => setAISettingsDialogOpen(false)}
          onConfirm={handleAISettingsConfirm}
        />
        </Box>
      )}
    </ThemeProvider>
  );
}

export default App;