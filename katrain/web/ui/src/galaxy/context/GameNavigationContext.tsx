import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';

interface GameNavigationContextType {
  /** Register an active game that requires confirmation before leaving */
  registerActiveGame: (onLeave: () => Promise<void> | void) => void;
  /** Unregister the active game (game ended) */
  unregisterActiveGame: () => void;
  /** Check if there's an active game */
  hasActiveGame: boolean;
  /** Request navigation - will show confirmation if there's an active game */
  requestNavigation: (path: string) => void;
}

const GameNavigationContext = createContext<GameNavigationContextType | null>(null);

export const useGameNavigation = () => {
  const ctx = useContext(GameNavigationContext);
  if (!ctx) throw new Error('useGameNavigation must be used within GameNavigationProvider');
  return ctx;
};

export const GameNavigationProvider = ({ children }: { children: ReactNode }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [activeGameHandler, setActiveGameHandler] = useState<(() => Promise<void> | void) | null>(null);
  const [pendingPath, setPendingPath] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);

  const registerActiveGame = useCallback((onLeave: () => Promise<void> | void) => {
    setActiveGameHandler(() => onLeave);
  }, []);

  const unregisterActiveGame = useCallback(() => {
    setActiveGameHandler(null);
  }, []);

  const requestNavigation = useCallback((path: string) => {
    if (activeGameHandler) {
      setPendingPath(path);
      setShowConfirm(true);
    } else {
      navigate(path);
    }
  }, [activeGameHandler, navigate]);

  const handleConfirmLeave = async () => {
    setShowConfirm(false);
    if (activeGameHandler) {
      await activeGameHandler();
    }
    if (pendingPath) {
      navigate(pendingPath);
      setPendingPath(null);
    }
    setActiveGameHandler(null);
  };

  const handleCancel = () => {
    setShowConfirm(false);
    setPendingPath(null);
  };

  return (
    <GameNavigationContext.Provider
      value={{
        registerActiveGame,
        unregisterActiveGame,
        hasActiveGame: !!activeGameHandler,
        requestNavigation,
      }}
    >
      {children}

      {/* Leave Game Confirmation Dialog */}
      <Dialog open={showConfirm} onClose={handleCancel}>
        <DialogTitle>{t('leave_game_title', 'Leave Game?')}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t('leave_game_warning', 'The game is still in progress. Leaving will resign the game. Are you sure?')}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancel}>{t('continue_game', 'Continue Game')}</Button>
          <Button onClick={handleConfirmLeave} color="error" variant="contained">
            {t('resign_and_exit', 'Resign & Exit')}
          </Button>
        </DialogActions>
      </Dialog>
    </GameNavigationContext.Provider>
  );
};
