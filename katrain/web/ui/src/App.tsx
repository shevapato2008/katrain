import { useState, useEffect, useRef } from 'react';
import { Box, CssBaseline, ThemeProvider, createTheme, Divider, Typography } from '@mui/material';
import { API, type GameState } from './api';
import { i18n } from './i18n';
import { useTranslation } from './hooks/useTranslation';
import Board from './components/Board';
import Sidebar from './components/Sidebar';
import ControlBar from './components/ControlBar';
import TopBar from './components/TopBar';
import AnalysisPanel from './components/AnalysisPanel';
import PlayerCard from './components/PlayerCard';
import ScoreGraph from './components/ScoreGraph';
import NewGameDialog from './components/NewGameDialog';
import AISettingsDialog from './components/AISettingsDialog';
import GameReportDialog from './components/GameReportDialog';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';

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
  const { t } = useTranslation();
  const [statusMessage, setStatusMessage] = useState<string>(t("Initializing..."));
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isNewGameDialogOpen, setNewGameDialogOpen] = useState(false);
  const [isAISettingsDialogOpen, setAISettingsDialogOpen] = useState(false);
  const [isGameReportDialogOpen, setGameReportDialogOpen] = useState(false);
  const [gameReport, setGameReport] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [analysisToggles, setAnalysisToggles] = useState<Record<string, boolean>>({
    children: false,
    eval: false,
    hints: false,
    policy: false,
    ownership: false,
    coords: true,
    numbers: false,
    score: true,
    winrate: true
  });

  useEffect(() => {
    if (gameState && gameState.ui_state) {
      setAnalysisToggles(prev => ({
        ...prev,
        children: gameState.ui_state.show_children,
        eval: gameState.ui_state.show_dots,
        hints: gameState.ui_state.show_hints,
        policy: gameState.ui_state.show_policy,
        ownership: gameState.ui_state.show_ownership,
        coords: gameState.ui_state.show_coordinates,
        numbers: gameState.ui_state.show_move_numbers,
      }));
    }
  }, [gameState]);

  useEffect(() => {
    const initSession = async () => {
      try {
        const data = await API.createSession();
        setSessionId(data.session_id);
        setGameState(data.state);
        
        const initialLang = data.state?.language || "en";
        await i18n.loadTranslations(initialLang);

        
        setStatusMessage(t("Ready"));

        // Setup WebSocket
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws/${data.session_id}`);
        ws.onmessage = (event) => {
          const msg = JSON.parse(event.data);
          if (msg.type === 'game_update') {
            setGameState(msg.state);
          } else if (msg.type === 'log') {
            setStatusMessage(msg.data.message);
          } else if (msg.type === 'sound') {
            playSound(msg.data.sound);
          } else if (msg.type === 'game_report') {
            setGameReport(msg.data);
            setGameReportDialogOpen(true);
          }
        };
      } catch (error) {
        console.error("Failed to initialize session", error);
        setStatusMessage("Error: Failed to connect");
      }
    };
    initSession();
  }, []);

  const playSound = (sound: string) => {
    const audio = new Audio(`/assets/sounds/${sound}.wav`);
    audio.play().catch(e => console.warn("Failed to play sound", e));
  };

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
      else if (action === 'undo') data = await API.undo(sessionId, 'smart');
      else if (action === 'back') data = await API.undo(sessionId, 1);
      else if (action === 'back-10') data = await API.undo(sessionId, 10);
      else if (action === 'start') data = await API.undo(sessionId, 9999);
      else if (action === 'forward') data = await API.redo(sessionId, 1);
      else if (action === 'forward-10') data = await API.redo(sessionId, 10);
      else if (action === 'end') data = await API.redo(sessionId, 9999);
      else if (action === 'ai-move') data = await API.aiMove(sessionId);
      else if (action === 'resign') data = await API.resign(sessionId);
      else if (action === 'rotate') data = await API.rotate(sessionId);
      else if (action === 'mistake-prev') data = await API.findMistake(sessionId, 'undo');
      else if (action === 'mistake-next') data = await API.findMistake(sessionId, 'redo');
      
      if (data) setGameState(data.state);
    } catch (error) {
      console.error("Action failed", error);
    }
  };

  const handleNewGame = () => {
    setNewGameDialogOpen(true);
  };

  const handleNewGameConfirm = async (mode: string, settings: any) => {
    if (!sessionId) return;
    try {
      const data = await API.gameSetup(sessionId, mode, settings);
      setGameState(data.state);
      setNewGameDialogOpen(false);
      setSidebarOpen(false);
    } catch (error) {
      console.error("Game setup failed", error);
    }
  };

  const handleAISettingsConfirm = async (bw: 'B' | 'W', strategy: string) => {
    if (!sessionId) return;
    try {
      const isHuman = strategy === 'player:human';
      const data = await API.updatePlayer(
        sessionId, 
        bw, 
        isHuman ? 'player:human' : 'player:ai', 
        isHuman ? 'game:normal' : strategy
      );
      setGameState(data.state);
    } catch (error) {
      console.error("AI Settings update failed", error);
    }
  };

  const handleSwapPlayers = async () => {
    if (!sessionId) return;
    try {
      const data = await API.swapPlayers(sessionId);
      setGameState(data.state);
    } catch (error) {
      console.error("Swap players failed", error);
    }
  };

  const handleAnalyzeGame = async () => {
    if (!sessionId) return;
    try {
      const data = await API.analyzeGame(sessionId);
      setGameState(data.state);
    } catch (error) {
      console.error("Analyze game failed", error);
    }
  };

  const handleGameReport = async () => {
    if (!sessionId) return;
    try {
      const data = await API.getGameReport(sessionId);
      setGameReport(data.report);
      setGameReportDialogOpen(true);
    } catch (error) {
      console.error("Game report failed", error);
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

  const handleToggleChange = async (toggle: string) => {
    if (!sessionId) return;
    
    if (toggle === 'continuous_analysis') {
      try {
        // We don't have a direct API for this in the provided list, 
        // but let's assume one exists or map it to something relevant. 
        // Actually, the backend likely has /api/analysis/continuous
        const response = await fetch('/api/analysis/continuous', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ session_id: sessionId })
        });
        if (response.ok) {
           const data = await response.json();
           setGameState(data.state);
        }
      } catch (e) {
        console.error("Continuous analysis toggle failed", e);
      }
      return;
    }

    // Optimistic update
    setAnalysisToggles(prev => ({ ...prev, [toggle]: !prev[toggle] }));
    try {
      const data = await API.toggleUI(sessionId, toggle);
      setGameState(data.state);
    } catch (error) {
      console.error("Toggle UI failed", error);
      // Revert on error
      setAnalysisToggles(prev => ({ ...prev, [toggle]: !prev[toggle] }));
    }
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

  const handleNodeAction = async (action: string) => {
    if (!sessionId || !gameState) return;
    try {
      let data;
      if (action === 'delete') data = await API.deleteNode(sessionId);
      else if (action === 'prune') data = await API.pruneBranch(sessionId);
      else if (action === 'make-main') data = await API.makeMainBranch(sessionId);
      else if (action === 'toggle-collapse') data = await API.toggleCollapse(sessionId);
      
      if (data) setGameState(data.state);
    } catch (error) {
      console.error("Node action failed", error);
    }
  };

  const handleLanguageChange = async (lang: string) => {
    if (!sessionId) return;
    try {
      const data = await API.updateConfig(sessionId, 'general/language', lang);
      await i18n.loadTranslations(lang);

      setGameState(data.state);
    } catch (error) {
      console.error("Language change failed", error);
    }
  };

  const handleShowPV = async (pv: string) => {
    if (!sessionId) return;
    try {
      const data = await API.showPV(sessionId, pv);
      setGameState(data.state);
    } catch (error) {
      console.error("Show PV failed", error);
    }
  };

  const handleClearPV = async () => {
    if (!sessionId) return;
    try {
      const data = await API.clearPV(sessionId);
      setGameState(data.state);
    } catch (error) {
      console.error("Clear PV failed", error);
    }
  };

  useKeyboardShortcuts({
    onAction: handleAction,
    onNewGame: handleNewGame,
    onLoadSGF: () => fileInputRef.current?.click(),
    onSaveSGF: handleSaveSGF,
    onToggleUI: handleToggleChange,
    onOpenPopup: (popup) => {
      if (popup === 'analysis') { /* TODO: Extra analysis popup */ }
      if (popup === 'report') handleGameReport();
      if (popup === 'timer') { /* TODO: Timer popup */ }
      if (popup === 'teacher') { /* TODO: Teacher popup */ }
      if (popup === 'ai') setAISettingsDialogOpen(true);
      if (popup === 'config') { /* TODO: Config popup */ }
      if (popup === 'contribute') { /* TODO: Contribute popup */ }
      if (popup === 'tsumego') { /* TODO: Tsumego popup */ }
    }
  });

  // Hidden file input for shortcut
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (ev) => {
        const content = ev.target?.result as string;
        handleLoadSGF(content);
      };
      reader.readAsText(file);
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <input 
        type="file" 
        ref={fileInputRef} 
        style={{ display: 'none' }} 
        accept=".sgf,.ngf,.gib" 
        onChange={handleFileChange} 
      />
      {!sessionId || !gameState ? (
        <Box sx={{ display: 'flex', height: '100vh', justifyContent: 'center', alignItems: 'center', bgcolor: '#cfd8dc' }}>
          <Typography variant="h5">{t("Initializing KaTrain...")}</Typography>
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
              onAnalyzeGame={handleAnalyzeGame}
              onGameReport={handleGameReport}
              onLanguageChange={handleLanguageChange}
              onSwapPlayers={handleSwapPlayers}
            />
          )}
          
          <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#cfd8dc', position: 'relative' }}>
            <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', p: 1 }}>
              {gameState && (
            <Board 
              gameState={gameState} 
              onMove={(x, y) => {
                 if (gameState.player_to_move === 'B' || gameState.player_to_move === 'W') {
                    handleMove(x, y);
                 }
              }}
              onNavigate={handleNavigate}
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
              <AnalysisPanel 
                gameState={gameState} 
                onNodeAction={handleNodeAction} 
                onShowPV={handleShowPV}
                onClearPV={handleClearPV}
              />
            </Box>
            
            <Divider />
            <Box sx={{ p: 1, bgcolor: '#fff' }}>
              <Typography variant="caption" color="textSecondary" sx={{ fontWeight: 'bold' }}>{t("GRAPH")}</Typography>
              <ScoreGraph 
                gameState={gameState} 
                onNavigate={handleNavigate} 
                showScore={analysisToggles.score}
                showWinrate={analysisToggles.winrate}
              />
            </Box>
          </Box>
        </Box>
        <NewGameDialog 
          open={isNewGameDialogOpen} 
          gameState={gameState}
          onClose={() => setNewGameDialogOpen(false)} 
          onConfirm={handleNewGameConfirm} 
        />
        <AISettingsDialog
          open={isAISettingsDialogOpen}
          gameState={gameState}
          onClose={() => setAISettingsDialogOpen(false)}
          onConfirm={handleAISettingsConfirm}
        />
        <GameReportDialog
          open={isGameReportDialogOpen}
          onClose={() => setGameReportDialogOpen(false)}
          report={gameReport}
        />
        </Box>
      )}
    </ThemeProvider>
  );
}

export default App;
