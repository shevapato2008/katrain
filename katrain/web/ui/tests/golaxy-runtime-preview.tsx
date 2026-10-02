import '../src/kiosk-shell/fonts.css';
import '../src/kiosk-shell/tokens.css';
import '../src/kiosk-shell/go-tokens.css';
import '../src/kiosk-shell/seclabel.css';
import '../src/kiosk-shell/icon.css';
import '../src/kiosk-shell/card.css';
import '../src/kiosk-shell/status.css';
import '../src/kiosk-shell/go-screens.css';
// Temporary visual gate only. Not reachable from the production entry or build.
// Delete this file and its HTML entry after the real data journeys are integrated.
import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { API } from '../src/api';
import { AuthProvider } from '../src/context/AuthContext';
import { kioskTheme } from '../src/kiosk/theme';
import KioskLayout from '../src/kiosk/components/layout/KioskLayout';
import GolaxyHomePage from '../src/kiosk/pages/GolaxyHomePage';
import GolaxySpectatorPage from '../src/kiosk/pages/GolaxySpectatorPage';


const states = new URLSearchParams(location.search);
const initialStage = states.get('state') === 'pending' ? 'pending' : states.get('state') === 'error' ? 'error' : 'main';
const rooms = [
 ['9348','升降战',0,11,'棋手甲','准 6 段','棋手乙','准 6 段',145],
 ['9361','升降战',-1,4,'棋手丙','7 段','棋手丁','准 7 段',82],
 ['9385','自由战',0,2,'棋手戊','5 段','棋手己','5 段',63],
 ['9398','升降战',0,8,'棋手庚','准 6 段','棋手辛','准 6 段',102],
 ['9402','自由战',-1,3,'棋手壬','4 段','棋手癸','5 段',37],
 ['9411','升降战',0,6,'棋手子','6 段','棋手丑','6 段',129],
].map(([id,type,handicap,count,black,br,white,wr,moves]) => ({ room_id:id, room_number:id, room_type:type, handicap, spectator_count:count, move_number:moves, phase:'进行中', black:{user_id:`${id}-b`,username:black,rank:br},white:{user_id:`${id}-w`,username:white,rank:wr} }));
const players = [
 ['棋友甲','星阵 3 星',184,167,'空闲'],['棋友乙','星阵 3 星',2463,2517,'对弈中'],
 ['棋友丙','准 6 段',237,220,'空闲'],['棋友丁','星阵 2 星',1333,1457,'拒邀'],
 ['棋友戊','4 段',70,52,'空闲'],['棋友己','准 5 段',159,109,'忙碌'],
 ['棋友庚','星阵 3 星',389,1001,'对弈中'],['棋友辛','5 段',446,127,'空闲'],
].map(([username,rank,wins,losses,status],i) => ({user_id:`fixture-${i}`,username,rank,wins,losses,status,invite_able:status==='空闲',user_code:`示意 · ${60000123+i}`,region:'上海 · 上海'}));
const black = ["D4", "Q16", "C17", "F17", "J16", "K16", "L16", "N15", "C14", "D14", "E13", "H13", "Q13", "C12", "F12", "B10", "H11", "Q10", "C9", "F9", "K9", "Q9", "C8", "G8", "J8", "Q8", "B7", "E7", "F7", "R7", "B6", "E6", "J6", "K6", "R6", "B5", "G5", "R5", "B4", "F4", "K4", "L3", "M3", "D2", "F2", "G1", "C16", "C15", "D15", "Q15", "R15", "S16", "J17", "K17"];
const white = ["Q4", "R4", "S4", "G19", "G18", "H18", "J18", "K18", "L18", "C18", "D18", "D17", "E17", "E15", "G14", "Q14", "R13", "S13", "K12", "S12", "D11", "S11", "D10", "F10", "G10", "H10", "J10", "K10", "D9", "E9", "D8", "D7", "C7", "D6", "K5", "G4", "H4", "J4", "E4", "H2", "J2", "K2", "L2", "M2", "Q18", "Q17", "P17", "P16"];
const snapshot = {
 room_id:'9348',room_number:'9348',board_size:19,black:rooms[0].black,white:rooms[0].white,
 black_stones:black,white_stones:white,move_number:145,phase:'进行中',result:null,room_type:'升降战',handicap:0,
 last_move:{color:'B',coordinate:'K6'},
 history:[{black_stones:black.filter(p=>p!=='K6'),white_stones:white,move_number:144,last_move:null}],
 clocks:{black:{remaining_seconds:11,period_seconds:30,periods_remaining:2},white:{remaining_seconds:28,period_seconds:30,periods_remaining:3},active_color:'W'},
 members:['棋手甲','棋手乙','棋友丙','棋友丁','棋友戊','棋友己','棋友庚','棋友辛','棋友壬','棋友癸','棋友子','棋友丑','棋友寅'].map((username,i)=>({user_id:`member-${i}`,username,role:i===0?'black':i===1?'white':'spectator'})),
};
API.platformStatus = async () => ({platforms:[{platform:'golaxy',connected:true,saved_username:'棋友甲'}]}) as any;
API.platformRooms = async () => ({rooms}) as any;
API.platformUsers = async () => ({users:players}) as any;
API.platformRoomSnapshot = async () => snapshot as any;
const originalFetch = window.fetch.bind(window);
window.fetch = ((input, options) => String(input).endsWith('/api/v1/auth/me')
 ? Promise.resolve(new Response(JSON.stringify({id:0,username:'预览账号',rank:'',credits:0}),{status:200,headers:{'Content-Type':'application/json'}}))
 : originalFetch(input,options)) as typeof fetch;
if (states.get('state') === 'spectator') history.replaceState({}, '', '/kiosk/play/cross-platform/golaxy/spectate/9348');
const home = <GolaxyHomePage profileInitialStage={initialStage} />;
createRoot(document.getElementById('root')!).render(<ThemeProvider theme={kioskTheme}><CssBaseline /><AuthProvider><BrowserRouter><Routes><Route element={<KioskLayout username="预览账号" />}><Route path="/tests/golaxy-runtime-preview.html" element={states.get('state') === 'spectator' ? <GolaxySpectatorPage /> : home} /><Route path="/kiosk/play/cross-platform/golaxy" element={home} /><Route path="/kiosk/play/cross-platform/golaxy/spectate/:roomId" element={<GolaxySpectatorPage />} /></Route></Routes></BrowserRouter></AuthProvider></ThemeProvider>);
