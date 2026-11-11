import { afterEach, expect, it, vi } from 'vitest';
import { API } from './api';
afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); });
const nonStrict = __KIOSK_2D_ONLY__ && import.meta.env.VITE_BOX_SSO_STRICT === 'true' ? it.skip : it;
const strict = __KIOSK_2D_ONLY__ && import.meta.env.VITE_BOX_SSO_STRICT === 'true' ? it : it.skip;
strict('does not issue private phone requests from a strict Kiosk build', async () => {
 const fetch=vi.fn();vi.stubGlobal('fetch',fetch);
 await expect(API.phoneStatus(null)).rejects.toMatchObject({detail:{code:'bind_not_allowed'}});
 expect(fetch).not.toHaveBeenCalled();
});
nonStrict('private phone requests use the captured credential without localStorage fallback or private URL parameters', async () => {
 localStorage.setItem('token','new-account-token');const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({bound:false})});vi.stubGlobal('fetch',fetch);
 await API.phoneStatus(null);expect(fetch.mock.calls[0][1].headers).toEqual({});
 await API.createPhoneBindChallenge({phone:'13800138000',purpose:'bind',flow_id:'a'.repeat(32)},'captured-account-token');
 await API.phoneBind({challenge_id:'opaque',code:'123456',flow_id:'a'.repeat(32),current_password:'private'},'captured-account-token');
 for(const [url,init] of fetch.mock.calls.slice(1)){expect(init.headers.Authorization).toBe('Bearer captured-account-token');expect(url).not.toContain('13800138000');expect(url).not.toContain('private');expect(init.cache).toBe('no-store');}
});
