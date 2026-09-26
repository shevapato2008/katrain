export type AdminPage = 'tutorial' | 'cron' | 'capture' | 'training' | 'diagnostics';
export const isLabPage = (page: AdminPage) => page === 'capture' || page === 'training' || page === 'diagnostics';
