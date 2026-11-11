import LoginModal from '../galaxy/components/auth/LoginModal';
interface LoginDialogProps { open: boolean; onClose: () => void; onLoginSuccess: (token: string) => void; }
// Legacy callers share the same canonical authentication flow.
export default function LoginDialog({ onLoginSuccess, ...props }: LoginDialogProps) {
  return <LoginModal {...props} onSuccess={() => onLoginSuccess(localStorage.getItem('token') ?? '')} />;
}
