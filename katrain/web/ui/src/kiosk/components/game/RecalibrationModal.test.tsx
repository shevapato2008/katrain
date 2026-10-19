import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { MemoryRouter, Route, Routes, useNavigate, useParams } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API, type GameType } from '../../../api';
import { GeometryAPI, type GeometryStatus } from '../../../api/geometryApi';
import { GeometryProvider, useGeometry } from '../../context/GeometryContext';
import { kioskTheme } from '../../theme';
import PhysicalBoardGuard from '../vision/PhysicalBoardGuard';
import { useVisionSync } from '../../hooks/useVisionSync';
import RecalibrationModal from './RecalibrationModal';

vi.mock('../vision/GeometryVideoPanel', () => ({ default: () => <div>CAMERA</div> }));
vi.mock('../vision/CameraGeometryOverlay', () => ({ default: () => null }));

const ready: GeometryStatus = {
  phase: 'ready', geometry_revision: 3, session_calibrated: true, last_valid: true,
  capabilities: { camera_ready: true, led_ready: true, geometry_ready: true, recognition_ready: true },
};
const active: GeometryStatus = { ...ready, phase: 'converging_exposure', session_calibrated: false };
let response: GeometryStatus;
let gameType: GameType;

function Game() {
  const { completeRecalibration } = useGeometry();
  const { sessionId } = useParams();
  useVisionSync(sessionId ?? null, completeRecalibration);
  return <><div>对局内容</div><RecalibrationModal open onClose={vi.fn()} gameType={gameType} /></>;
}
function Flow() {
  const { refresh, completeRecalibration } = useGeometry();
  const navigate = useNavigate();
  return <>
    <button onClick={() => void refresh()}>刷新状态</button>
    <button onClick={() => navigate("/game/another")}>换一局</button>
    <button onClick={() => void completeRecalibration("original")}>原对局已绑定</button>
    <PhysicalBoardGuard requireRecognition sub="实体盘对局">
      <Game />
    </PhysicalBoardGuard>
  </>;
}
const renderFlow = () => render(<ThemeProvider theme={kioskTheme}><MemoryRouter initialEntries={["/game/original"]}>
  <GeometryProvider><Routes><Route path="/game/:sessionId" element={<Flow />} /></Routes></GeometryProvider>
</MemoryRouter></ThemeProvider>);

describe('mid-game recalibration uses the shared screen', () => {
  beforeEach(() => {
    gameType = 'free';
    response = ready;
    vi.spyOn(GeometryAPI, 'status').mockImplementation(async () => response);
    vi.spyOn(GeometryAPI, 'layout').mockRejectedValue(new Error('not needed'));
    vi.spyOn(GeometryAPI, 'calibrate').mockImplementation(async () => { response = active; return active; });
    vi.spyOn(GeometryAPI, 'cancel').mockImplementation(async () => {
      response = { ...active, phase: 'cancelled', stopped_phase: 'converging_exposure' }; return response;
    });
    vi.spyOn(API, 'visionResetSync').mockResolvedValue(undefined);
    vi.spyOn(API, 'visionBind').mockResolvedValue(undefined);
    vi.spyOn(API, 'visionUnbind').mockResolvedValue(undefined);
    vi.stubGlobal('WebSocket', class { close() {} });
  });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it('202 hands control to five steps; same revision never resets sync and a new revision resets once', async () => {
    renderFlow();
    await screen.findByText('对局内容');
    fireEvent.click(screen.getByRole('button', { name: '重新标定' }));
    await waitFor(() => expect(screen.queryByText('对局内容')).not.toBeInTheDocument());
    expect(screen.getAllByTestId('calib-step')).toHaveLength(5);
    expect(screen.getAllByTestId('calib-step')[1]).toHaveAttribute('data-state', 'now');
    expect(GeometryAPI.calibrate).toHaveBeenCalledWith('manual');
    expect(API.visionResetSync).not.toHaveBeenCalled();
    response = ready;
    await act(async () => fireEvent.click(screen.getByRole('button', { name: '刷新状态', hidden: true })));
    await screen.findByText('对局内容');
    expect(API.visionResetSync).not.toHaveBeenCalled();
    response = { ...ready, geometry_revision: 4 };
    await act(async () => fireEvent.click(screen.getByRole('button', { name: '刷新状态', hidden: true })));
    await waitFor(() => expect(screen.getByText('对局内容')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: '原对局已绑定', hidden: true }));
    await waitFor(() => expect(API.visionResetSync).toHaveBeenCalledTimes(1));
    await act(async () => fireEvent.click(screen.getByRole('button', { name: '刷新状态', hidden: true })));
    await waitFor(() => expect(API.visionResetSync).toHaveBeenCalledTimes(1));
  });

  it('cancelled calibration clears the deferred reset before an unrelated ready revision', async () => {
    renderFlow();
    await screen.findByText('对局内容');
    fireEvent.click(screen.getByRole('button', { name: '重新标定' }));
    await screen.findByRole('button', { name: '取消标定' });
    fireEvent.click(screen.getByRole('button', { name: '取消标定' }));
    await waitFor(() => expect(screen.getAllByTestId('calib-step')[1]).toHaveAttribute('data-state', 'warn'));
    response = { ...ready, geometry_revision: 4 };
    await act(async () => fireEvent.click(screen.getByRole('button', { name: '刷新状态', hidden: true })));
    await screen.findByText('对局内容');
    expect(API.visionResetSync).not.toHaveBeenCalled();
  });
  it('new ready revision waits for the original successful bind before resetting', async () => {
    let resolveBind!: () => void;
    renderFlow();
    await screen.findByText('对局内容');
    await waitFor(() => expect(API.visionBind).toHaveBeenCalledWith('original'));
    fireEvent.click(screen.getByRole('button', { name: '重新标定' }));
    await screen.findByRole('button', { name: '取消标定' });
    vi.mocked(API.visionBind).mockImplementationOnce(() => new Promise<void>(resolve => { resolveBind = resolve; }));
    response = { ...ready, geometry_revision: 4 };
    await act(async () => fireEvent.click(screen.getByRole('button', { name: '刷新状态', hidden: true })));
    await screen.findByText('对局内容');
    expect(API.visionResetSync).not.toHaveBeenCalled();
    resolveBind();
    await waitFor(() => expect(API.visionResetSync).toHaveBeenCalledTimes(1));
  });

  it.each(['failed', 'disabled'] as const)('%s clears the pending reset before later readiness', async phase => {
    renderFlow();
    await screen.findByText('对局内容');
    fireEvent.click(screen.getByRole('button', { name: '重新标定' }));
    await screen.findByRole('button', { name: '取消标定' });
    response = { ...active, phase };
    await act(async () => fireEvent.click(screen.getByRole('button', { name: '刷新状态', hidden: true })));
    await waitFor(() => expect(screen.queryByRole('button', { name: '取消标定' })).not.toBeInTheDocument());
    response = { ...ready, geometry_revision: 4 };
    await act(async () => fireEvent.click(screen.getByRole('button', { name: '刷新状态', hidden: true })));
    await screen.findByText('对局内容');
    expect(API.visionResetSync).not.toHaveBeenCalled();
  });

  it('a request failure clears the pending reset before an unrelated new revision', async () => {
    vi.mocked(GeometryAPI.calibrate).mockRejectedValueOnce(new Error('offline'));
    renderFlow();
    await screen.findByText('对局内容');
    fireEvent.click(screen.getByRole('button', { name: '重新标定' }));
    await screen.findByText('重新定位失败，请重试');
    response = { ...ready, geometry_revision: 4 };
    await act(async () => fireEvent.click(screen.getByRole('button', { name: '刷新状态', hidden: true })));
    fireEvent.click(screen.getByRole('button', { name: '原对局已绑定', hidden: true }));
    expect(API.visionResetSync).not.toHaveBeenCalled();
  });

  it('leaving the original route clears the pending reset for another game', async () => {
    renderFlow();
    await screen.findByText('对局内容');
    fireEvent.click(screen.getByRole('button', { name: '重新标定' }));
    await screen.findByRole('button', { name: '取消标定' });
    fireEvent.click(screen.getByRole('button', { name: '换一局', hidden: true }));
    response = { ...ready, geometry_revision: 4 };
    await act(async () => fireEvent.click(screen.getByRole('button', { name: '刷新状态', hidden: true })));
    await screen.findByText('对局内容');
    await waitFor(() => expect(API.visionBind).toHaveBeenCalledWith('another'));
    expect(API.visionResetSync).not.toHaveBeenCalled();
  });

  it('local-game rebind keeps its prepared reference without an extra reset', async () => {
    gameType = 'pvp_local';
    renderFlow();
    await screen.findByText('对局内容');
    fireEvent.click(screen.getByRole('button', { name: '重新标定' }));
    await screen.findByRole('button', { name: '取消标定' });
    response = { ...ready, geometry_revision: 4 };
    await act(async () => fireEvent.click(screen.getByRole('button', { name: '刷新状态', hidden: true })));
    await screen.findByText('对局内容');
    await waitFor(() => expect(API.visionBind).toHaveBeenCalledTimes(2));
    expect(API.visionResetSync).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '原对局已绑定', hidden: true }));
    expect(API.visionResetSync).not.toHaveBeenCalled();
  });

});
