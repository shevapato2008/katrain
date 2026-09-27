export type AdminPage = 'tutorial' | 'cron' | 'performance' | 'users' | 'audit' | 'capture' | 'training' | 'diagnostics';
export const isLabPage = (page: AdminPage) => page === 'capture' || page === 'training' || page === 'diagnostics';
