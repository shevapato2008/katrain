import { useEffect, useState } from 'react';
import { Snackbar } from '@mui/material';

const eventName = 'katrain:auth-notice';
export function showAuthNotice(message: string) {
  window.dispatchEvent(new CustomEvent<string>(eventName, { detail: message }));
}

// Lives above the routes so a successful Kiosk registration can navigate immediately.
export default function AuthNotice() {
  const [message, setMessage] = useState('');
  useEffect(() => {
    const receive = (event: Event) => setMessage((event as CustomEvent<string>).detail);
    window.addEventListener(eventName, receive);
    return () => window.removeEventListener(eventName, receive);
  }, []);
  return <Snackbar open={Boolean(message)} autoHideDuration={4500} onClose={() => setMessage('')} message={message} anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }} />;
}
