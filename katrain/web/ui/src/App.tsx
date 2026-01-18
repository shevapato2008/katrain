import { useState, useEffect, useRef, useMemo } from 'react';
import { Box, CssBaseline, ThemeProvider, createTheme, Divider, Typography, Snackbar, Alert } from '@mui/material';
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
import LoginDialog from './components/LoginDialog';
import RegisterDialog from './components/RegisterDialog';
import TimeSettingsDialog from './components/TimeSettingsDialog';
import TeachingSettingsDialog from './components/TeachingSettingsDialog';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#4a6b5c', // Muted jade accent
      light: '#5d8270',
      dark: '#2f4539',
    },
    background: {
      default: '#0f0f0f', // Deep charcoal
      paper: '#252525', // Tertiary bg
    },
    text: {
      primary: '#f5f3f0', // Primary text
      secondary: '#b8b5b0', // Secondary text
      disabled: '#4a4845',
    },
    divider: 'rgba(255, 255, 255, 0.05)',
    success: {
      main: '#30a06e',
    },
    warning: {
      main: '#e89639',
    },
    error: {
      main: '#e16b5c',
    },
    info: {
      main: '#5b9bd5',
    },
  },
  typography: {
    fontFamily: "'Manrope', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif",
    fontSize: 16,
    h1: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
    h2: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
    h3: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
    h4: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
    h5: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
    h6: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
    body1: { fontFamily: "'Manrope', sans-serif" },
    body2: { fontFamily: "'Manrope', sans-serif" },
    button: { fontFamily: "'Manrope', sans-serif", fontWeight: 600 },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: '8px',
          padding: '8px 16px',
          transition: 'all 150ms cubic-bezier(0.4, 0, 0.2, 1)',
          '&:hover': {
            transform: 'scale(1.02)',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: '12px',
        },
      },
    },
  },
});

function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'));
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [activeEngine, setActiveEngine] = useState<"local" | "cloud" | null>(null);
  const { t } = useTranslation();
  const [statusMessage, setStatusMessage] = useState<string>(t("Initializing..."));
  const [isSidebarOpen, setSidebarOpen] = useState(false);
  const [isNewGameDialogOpen, setNewGameDialogOpen] = useState(false);
  const [isAISettingsDialogOpen, setAISettingsDialogOpen] = useState(false);
  const [isGameReportDialogOpen, setGameReportDialogOpen] = useState(false);
  const [isLoginDialogOpen, setLoginDialogOpen] = useState(false);
  const [isRegisterDialogOpen, setRegisterDialogOpen] = useState(false);
  const [isTimeSettingsDialogOpen, setTimeSettingsDialogOpen] = useState(false);
  const [isTeachingSettingsDialogOpen, setTeachingSettingsDialogOpen] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [gameReport, setGameReport] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Notifications Settings
  const [showPassAlert, setShowPassAlert] = useState(() => localStorage.getItem('showPassAlert') !== 'false');
  const [playPassSound, setPlayPassSound] = useState(() => localStorage.getItem('playPassSound') !== 'false');
  const [showEndAlert, setShowEndAlert] = useState(() => localStorage.getItem('showEndAlert') !== 'false');
  const [playEndSound, setPlayEndSound] = useState(() => localStorage.getItem('playEndSound') !== 'false');
  
  const [notification, setNotification] = useState<{ open: boolean; message: string; severity: 'info' | 'success' }>({
    open: false,
    message: '',
    severity: 'info'
  });

  const settings = useMemo(() => ({
    showPassAlert,
    playPassSound,
    showEndAlert,
    playEndSound
  }), [showPassAlert, playPassSound, showEndAlert, playEndSound]);

  const handleUpdateSettings = (key: string, value: boolean) => {
    localStorage.setItem(key, String(value));
    if (key === 'showPassAlert') setShowPassAlert(value);
    if (key === 'playPassSound') setPlayPassSound(value);
    if (key === 'showEndAlert') setShowEndAlert(value);
    if (key === 'playEndSound') setPlayEndSound(value);
  };

  // Detection Refs
  const prevGameId = useRef<string | null>(null);
  const prevNodeId = useRef<number | null>(null);
  const prevHistoryLen = useRef(0);
  const prevGameEnded = useRef(false);
  const audioCache = useRef<Record<string, HTMLAudioElement>>({});
  const lastSoundRef = useRef<{name: string, time: number} | null>(null);

  const playSound = (sound: string) => {
    const now = Date.now();
    if (lastSoundRef.current && lastSoundRef.current.name === sound && now - lastSoundRef.current.time < 500) {
      console.log("Skipping duplicate sound", sound);
      return;
    }
    lastSoundRef.current = { name: sound, time: now };

    if (!audioCache.current[sound]) {
      audioCache.current[sound] = new Audio(`/assets/sounds/${sound}.wav`);
    }
    const audio = audioCache.current[sound];
    audio.currentTime = 0;
    audio.play().catch(e => console.warn("Failed to play sound", e));
  };

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
            if (msg.state.engine) {
              setActiveEngine(msg.state.engine);
            }
          } else if (msg.type === 'log') {
            setStatusMessage(msg.data.message);
          } else if (msg.type === 'sound') {
            playSound(msg.data.sound);
          } else if (msg.type === 'game_report') {
            setGameReport(msg.data);
            setGameReportDialogOpen(true);
          }
        };

        // Get user info if token exists
        if (token) {
          try {
            const userData = await API.getMe(token);
            setUser(userData);
          } catch (e) {
            console.error("Failed to get user info, token might be expired", e);
            localStorage.removeItem('token');
            setToken(null);
            setUser(null);
          }
        }

      } catch (error) {
        console.error("Failed to initialize session", error);
        setStatusMessage("Error: Failed to connect");
      }
    };
    initSession();
  }, [token]);

  const handleLoginSuccess = (newToken: string) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
    setLoginDialogOpen(false);
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken(null);
    setUser(null);
  };

  useEffect(() => {
    if (!gameState) return;

    // Game change detection
    if (gameState.game_id !== prevGameId.current) {
        prevGameId.current = gameState.game_id;
        prevNodeId.current = gameState.current_node_id;
        prevHistoryLen.current = gameState.history.length;
        prevGameEnded.current = !!gameState.end_result;
        return; 
    }

    const isNewMove = gameState.history.length > prevHistoryLen.current;
    const isDifferentNode = gameState.current_node_id !== prevNodeId.current;
    const isAtTip = gameState.current_node_index === gameState.history.length - 1;

    // 1. Pass Detection
    if (isNewMove && isDifferentNode && isAtTip && gameState.is_pass) {
        let passedPlayer = 'Unknown';
        if (gameState.player_to_move === 'B') passedPlayer = 'White';
        else if (gameState.player_to_move === 'W') passedPlayer = 'Black';

        if (showPassAlert) {
            const msg = passedPlayer === 'Unknown' 
                ? t('Pass') 
                : `${t(passedPlayer)} ${t('Passed')}`;
            setNotification({ 
                open: true, 
                message: msg, 
                severity: 'info' 
            });
        }
        if (playPassSound) playSound('boing');
    }

    // 2. Game End Detection
    if (gameState.end_result && !prevGameEnded.current) {
         if (showEndAlert) {
             setNotification({ 
                 open: true, 
                 message: `${t('Game Ended')}: ${gameState.end_result}`, 
                 severity: 'success' 
             });
         }
         if (playEndSound) playSound('countdownbeep');
    }

    // Update refs
    prevNodeId.current = gameState.current_node_id;
    prevHistoryLen.current = gameState.history.length;
    prevGameEnded.current = !!gameState.end_result;

  }, [gameState, showPassAlert, playPassSound, showEndAlert, playEndSound, t]);

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
      if (popup === 'timer') setTimeSettingsDialogOpen(true);
      if (popup === 'teacher') setTeachingSettingsDialogOpen(true);
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
        <Box sx={{ display: 'flex', height: '100vh', justifyContent: 'center', alignItems: 'center', bgcolor: '#0f0f0f' }}>
          <Typography variant="h5" sx={{ color: '#f5f3f0' }}>{t("Initializing KaTrain...")}</Typography>
        </Box>
      ) : (
        <Box className="app-container animate-fade-in">
          <TopBar
            onMenuClick={() => setSidebarOpen(!isSidebarOpen)}
            analysisToggles={analysisToggles}
            onToggleChange={handleToggleChange}
            status={statusMessage}
            engine={activeEngine}
            user={user}
            onLoginClick={() => setLoginDialogOpen(true)}
            onRegisterClick={() => setRegisterDialogOpen(true)}
            onLogoutClick={handleLogout}
          />

        <Box className="main-content">
          {isSidebarOpen && (
            <Sidebar
              gameState={gameState}
              settings={settings}
              onUpdateSettings={handleUpdateSettings}
              onNewGame={handleNewGame}
              onLoadSGF={handleLoadSGF}
              onSaveSGF={handleSaveSGF}
              onAISettings={() => setAISettingsDialogOpen(true)}
              onAnalyzeGame={handleAnalyzeGame}
              onGameReport={handleGameReport}
              onLanguageChange={handleLanguageChange}
              onSwapPlayers={handleSwapPlayers}
              onTimeSettings={() => setTimeSettingsDialogOpen(true)}
              onTeachingSettings={() => setTeachingSettingsDialogOpen(true)}
            />
          )}

          <Box className="board-container">
            <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', p: 2 }}>
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

          <Box sx={{ width: 320, display: 'flex', flexDirection: 'column', borderLeft: '1px solid rgba(255, 255, 255, 0.05)', bgcolor: '#1a1a1a' }}>
            <Box sx={{ p: 1, display: 'flex', gap: 1 }}>
              {gameState && (
                <>
                  <PlayerCard 
                    player="B" 
                    info={gameState.players_info.B} 
                    captures={gameState.prisoner_count.B} 
                    active={gameState.player_to_move === 'B'} 
                    timer={gameState.timer}
                  />
                  <PlayerCard 
                    player="W" 
                    info={gameState.players_info.W} 
                    captures={gameState.prisoner_count.W} 
                    active={gameState.player_to_move === 'W'} 
                    timer={gameState.timer}
                  />
                </>
              )}
            </Box>
            <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.05)' }} />

            <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
              <AnalysisPanel
                gameState={gameState}
                onNodeAction={handleNodeAction}
                onShowPV={handleShowPV}
                onClearPV={handleClearPV}
              />
            </Box>

            <Divider sx={{ borderColor: 'rgba(255, 255, 255, 0.05)' }} />
            <Box sx={{ p: 1, bgcolor: '#252525' }}>
              <Typography variant="caption" sx={{ fontWeight: 600, color: '#7a7772', fontSize: '0.75rem', letterSpacing: '0.5px' }}>{t("GRAPH")}</Typography>
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
          sessionId={sessionId}
          gameState={gameState}
          onClose={() => setAISettingsDialogOpen(false)}
        />
        <GameReportDialog
          open={isGameReportDialogOpen}
          onClose={() => setGameReportDialogOpen(false)}
          report={gameReport}
        />
        <LoginDialog 
          open={isLoginDialogOpen} 
          onClose={() => setLoginDialogOpen(false)}
          onLoginSuccess={handleLoginSuccess} 
        />
        <RegisterDialog
          open={isRegisterDialogOpen}
          onClose={() => setRegisterDialogOpen(false)}
          onRegisterSuccess={(username) => {
            setNotification({ open: true, message: `User ${username} registered successfully!`, severity: 'success' });
            setLoginDialogOpen(true);
          }}
        />
        <TimeSettingsDialog 
          open={isTimeSettingsDialogOpen} 
          onClose={() => setTimeSettingsDialogOpen(false)} 
        />
        <TeachingSettingsDialog 
          open={isTeachingSettingsDialogOpen} 
          onClose={() => setTeachingSettingsDialogOpen(false)} 
        />
        <Snackbar 
          open={notification.open} 
          autoHideDuration={4000} 
          onClose={() => setNotification(prev => ({ ...prev, open: false }))}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          <Alert 
            onClose={() => setNotification(prev => ({ ...prev, open: false }))} 
            severity={notification.severity} 
            variant="filled"
            sx={{ width: '100%', boxShadow: 3 }}
          >
            {notification.message}
          </Alert>
        </Snackbar>
        </Box>
      )}
    </ThemeProvider>
  );
}

export default App;