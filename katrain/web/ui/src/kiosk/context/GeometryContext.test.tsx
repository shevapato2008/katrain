import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GeometryAPI, type GeometryStatus } from '../../api/geometryApi';
import { GeometryProvider, useGeometry } from './GeometryContext';

const ready: GeometryStatus = { phase: 'ready', session_calibrated: true, last_valid: true,
  capabilities: { camera_ready: true, led_ready: true, geometry_ready: true, recognition_ready: true, model_ready: true } };
function Probe() {
  const { status, preflight } = useGeometry();
  return <><output>{status.phase}:{String(status.capabilities.model_ready)}</output>
    <button onClick={() => void preflight()}>检查</button></>;
}
afterEach(() => vi.restoreAllMocks());
describe('GeometryProvider preflight status', () => {
  it('applies the authoritative check response even when earlier status said ready', async () => {
    vi.spyOn(GeometryAPI, 'status').mockResolvedValue(ready);
    vi.spyOn(GeometryAPI, 'preflight').mockResolvedValue({ ready: false, reason: 'model_not_ready',
      status: { ...ready, phase: 'required', capabilities: { ...ready.capabilities, model_ready: false } } });
    render(<MemoryRouter><GeometryProvider><Probe /></GeometryProvider></MemoryRouter>);
    await screen.findByText('ready:true');
    fireEvent.click(screen.getByRole('button', { name: '检查' }));
    await waitFor(() => expect(screen.getByText('required:false')).toBeInTheDocument());
  });
});
