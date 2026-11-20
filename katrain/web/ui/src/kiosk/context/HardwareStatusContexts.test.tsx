import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { API, type VisionStatusResponse } from '../../api';
import { GeometryAPI, type GeometryStatus } from '../../api/geometryApi';
import { VisionProvider, useVision } from './VisionContext';
import { GeometryProvider, useGeometry } from './GeometryContext';

const visionResponse = (connected: boolean | null): VisionStatusResponse => ({
  enabled: false, camera_connected: false, pose_locked: false, sync_state: 'idle', bound_session_id: null,
  led_connected: connected,
});
const geometryResponse = (connected: boolean | null): GeometryStatus => ({
  phase: 'required', session_calibrated: false, last_valid: false,
  capabilities: { camera_ready: false, led_ready: connected, geometry_ready: false },
});

function VisionProbe() {
  const { visionStatus, refreshStatus } = useVision();
  return <button onClick={() => void refreshStatus()}>{String(visionStatus.ledConnected)}</button>;
}
function GeometryProbe() {
  const { status, refresh } = useGeometry();
  return <button onClick={() => void refresh()}>{String(status.capabilities.led_ready)}</button>;
}

function ReferenceProbe() {
  const { visionStatus, refreshStatus } = useVision();
  return <button onClick={() => void refreshStatus()}>{JSON.stringify({
    status: visionStatus.referenceStatus,
    reason: visionStatus.referenceReason,
    targetNodeId: visionStatus.referenceTargetNodeId,
    targetRevision: visionStatus.referenceTargetRevision,
    sourceNodeId: visionStatus.referenceSourceNodeId,
    sourceRevision: visionStatus.referenceSourceRevision,
    ready: visionStatus.recognitionReady,
  })}</button>;
}

describe('reference evidence status', () => {
  afterEach(() => vi.restoreAllMocks());

  it('defaults unsupported optional fields to unavailable without changing recognition readiness', async () => {
    vi.spyOn(API, 'visionStatus').mockResolvedValue({ ...visionResponse(true), recognition_ready: true });
    render(<VisionProvider><ReferenceProbe /></VisionProvider>);
    await waitFor(() => expect(JSON.parse(screen.getByRole('button').textContent!)).toEqual({
      status: 'unavailable', reason: null, targetNodeId: null, targetRevision: null,
      sourceNodeId: null, sourceRevision: null, ready: true,
    }));
  });

  it.each(['current', 'pending', 'limited', 'unavailable'] as const)('maps %s evidence and exact target/source identities independently of readiness', async (referenceStatus) => {
    vi.spyOn(API, 'visionStatus').mockResolvedValue({
      ...visionResponse(true), recognition_ready: true,
      reference_status: referenceStatus, reference_reason: 'witness_mismatch',
      reference_target_node_id: 17, reference_target_revision: 12,
      reference_source_node_id: 16, reference_source_revision: 11,
    });
    render(<VisionProvider><ReferenceProbe /></VisionProvider>);
    await waitFor(() => expect(JSON.parse(screen.getByRole('button').textContent!)).toEqual({
      status: referenceStatus, reason: 'witness_mismatch', targetNodeId: 17, targetRevision: 12,
      sourceNodeId: 16, sourceRevision: 11, ready: true,
    }));
  });
});

describe('hardware status cache on request failure', () => {
  afterEach(() => vi.restoreAllMocks());

  it('vision invalidates a green LED status on failure and recovers from the next response', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const status = vi.spyOn(API, 'visionStatus').mockResolvedValue(visionResponse(true));
    render(<VisionProvider><VisionProbe /></VisionProvider>);
    await waitFor(() => expect(screen.getByRole('button')).toHaveTextContent('true'));
    status.mockRejectedValueOnce(new Error('offline'));
    await act(async () => fireEvent.click(screen.getByRole('button')));
    expect(screen.getByRole('button')).toHaveTextContent('null');
    status.mockResolvedValue(visionResponse(false));
    await act(async () => fireEvent.click(screen.getByRole('button')));
    expect(screen.getByRole('button')).toHaveTextContent('false');
  });

  it.each(['offline', 'geometry request failed 404'])('geometry invalidates green LED on %s and recovers', async (error) => {
    const status = vi.spyOn(GeometryAPI, 'status').mockResolvedValue(geometryResponse(true));
    render(<MemoryRouter><GeometryProvider><GeometryProbe /></GeometryProvider></MemoryRouter>);
    await waitFor(() => expect(screen.getByRole('button')).toHaveTextContent('true'));
    status.mockRejectedValue(new Error(error));
    await act(async () => fireEvent.click(screen.getByRole('button')));
    expect(screen.getByRole('button')).toHaveTextContent('null');
    status.mockResolvedValue(geometryResponse(false));
    await act(async () => fireEvent.click(screen.getByRole('button')));
    expect(screen.getByRole('button')).toHaveTextContent('false');
  });
});
