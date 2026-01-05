import { useEffect } from 'react';

interface ShortcutHandlerProps {
  onAction: (action: string) => void;
  onNewGame: () => void;
  onLoadSGF: () => void;
  onSaveSGF: () => void;
  onToggleUI: (setting: string) => void;
  onOpenPopup: (popup: string) => void;
}

export const useKeyboardShortcuts = ({
  onAction,
  onNewGame,
  onLoadSGF,
  onSaveSGF,
  onToggleUI,
  onOpenPopup
}: ShortcutHandlerProps) => {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Ignore if typing in an input
      if ((event.target as HTMLElement).tagName === 'INPUT' || (event.target as HTMLElement).tagName === 'TEXTAREA') {
        return;
      }

      const ctrl = event.ctrlKey || event.metaKey;
      const shift = event.shiftKey;
      const key = event.key.toLowerCase();

      switch (key) {
        // Navigation
        case 'arrowleft':
          if (ctrl) onAction('start');
          else if (shift) onAction('back-10');
          else onAction('back');
          break;
        case 'arrowright':
          if (ctrl) onAction('end');
          else if (shift) onAction('forward-10');
          else onAction('forward');
          break;
        case 'arrowup':
          // Branch up (not implemented in API yet easily, or maps to undo branch?)
          // Kivy: KEY_NAV_BRANCH_UP = "up" -> switch_branch(1)
          // We need an API for switch_branch
           // onAction('switch-branch-up'); 
           // For now, let's map to nothing or add to API
          break;
        case 'arrowdown':
          // Kivy: KEY_NAV_BRANCH_DOWN = "down" -> switch_branch(-1)
          break;
        case 'home':
          onAction('start');
          break;
        case 'end':
          onAction('end');
          break;
        case 'pageup':
          onAction('make-main');
          break;
        case 'delete':
          if (ctrl) onAction('delete');
          break;
        
        // Actions
        case 'p':
          onAction('pass');
          break;
        case 'enter':
          onAction('ai-move');
          break;
        case 'n':
          if (ctrl) {
            event.preventDefault();
            onNewGame();
          } else {
             // Mistake navigation
             if (shift) onAction('mistake-prev');
             else onAction('mistake-next');
          }
          break;
        case 's':
          if (ctrl) {
            event.preventDefault();
            onSaveSGF();
          }
          break;
        case 'l':
          if (ctrl) {
            event.preventDefault();
            onLoadSGF();
          }
          break;
        
        // Toggles
        case ' ': // Space
          event.preventDefault();
          onToggleUI('continuous_analysis'); // This might need a specific API call if it's not a standard toggle
          break;
        case 'm':
          onToggleUI('numbers');
          break;
        case 'k':
          onToggleUI('coords');
          break;
        case '`':
        case '~':
          onToggleUI('zen_mode');
          break;
        case 'escape':
           // Stop analysis
           // onAction('stop-analysis');
           break;

        // Popups (Function keys)
        case 'f2': onOpenPopup('analysis'); break;
        case 'f3': onOpenPopup('report'); break;
        case 'f5': onOpenPopup('timer'); break; // Or pause timer? Kivy uses F15/Pause/Break for pause. F5 is usually refresh in browser.
        case 'f6': onOpenPopup('teacher'); break;
        case 'f7': onOpenPopup('ai'); break;
        case 'f8': onOpenPopup('config'); break;
        case 'f9': onOpenPopup('contribute'); break;
        case 'f10': onOpenPopup('tsumego'); break;

        // Copy/Paste (Ctrl+C/V handled by browser usually, but we might want to hook for SGF)
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onAction, onNewGame, onLoadSGF, onSaveSGF, onToggleUI, onOpenPopup]);
};
