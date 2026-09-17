import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  useEngineReadiness,
} from './EngineReadinessContext';
import { EngineReadinessProvider } from './EngineReadinessProvider';

const { engineHealthMock } = vi.hoisted(() => ({ engineHealthMock: vi.fn() }));
vi.mock('../../api', () => ({ API: { engineHealth: engineHealthMock } }));

const Probe = () => <span data-testid="readiness">{useEngineReadiness()}</span>;

const flush = async () => {
  await act(async () => {
    await Promise.resolve();
  });
};

describe('EngineReadinessProvider', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-09-17T00:00:00Z'));
    engineHealthMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('polls immediately, becomes unavailable after 120s, recovers, then stops polling', async () => {
    engineHealthMock
      .mockResolvedValueOnce({ status: 'ok' })
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ status: 'ok', engines: { local: 'unreachable', cloud: 'unconfigured' } })
      .mockResolvedValue({ status: 'ok', engines: { local: 'error_503', cloud: 'unconfigured' } });

    render(
      <EngineReadinessProvider>
        <Probe />
      </EngineReadinessProvider>,
    );

    expect(screen.getByTestId('readiness')).toHaveTextContent('warming');
    await flush();
    expect(engineHealthMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4_000);
    });
    expect(engineHealthMock).toHaveBeenCalledTimes(3);
    expect(screen.getByTestId('readiness')).toHaveTextContent('warming');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(116_000);
    });
    expect(screen.getByTestId('readiness')).toHaveTextContent('unavailable');

    engineHealthMock.mockResolvedValue({
      status: 'ok',
      engines: { local: 'reachable', cloud: 'unconfigured' },
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2_000);
    });
    expect(screen.getByTestId('readiness')).toHaveTextContent('ready');

    const callsAtReady = engineHealthMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(engineHealthMock).toHaveBeenCalledTimes(callsAtReady);
  });

  it('ignores an in-flight response after unmount and schedules no further poll', async () => {
    let resolveHealth!: (value: unknown) => void;
    engineHealthMock.mockReturnValue(new Promise((resolve) => { resolveHealth = resolve; }));

    const view = render(
      <EngineReadinessProvider>
        <Probe />
      </EngineReadinessProvider>,
    );
    expect(engineHealthMock).toHaveBeenCalledTimes(1);

    view.unmount();
    await act(async () => {
      resolveHealth({ status: 'ok', engines: { local: 'reachable', cloud: 'unconfigured' } });
      await Promise.resolve();
      await vi.advanceTimersByTimeAsync(10_000);
    });

    expect(engineHealthMock).toHaveBeenCalledTimes(1);
  });
});
