export type AdminPage = 'tutorial' | 'cron' | 'capture' | 'training';
export const isLabPage = (page: AdminPage) => page === 'capture' || page === 'training';
