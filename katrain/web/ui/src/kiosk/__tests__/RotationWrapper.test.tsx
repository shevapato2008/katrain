import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import RotationWrapper from '../components/layout/RotationWrapper';

const mockUseOrientation = vi.fn();
vi.mock('../context/OrientationContext', () => ({
  useOrientation: () => mockUseOrientation(),
}));

describe('RotationWrapper', () => {
  it('renders children', () => {
    mockUseOrientation.mockReturnValue({ rotation: 0 });
    render(<RotationWrapper><div>CHILD</div></RotationWrapper>);
    expect(screen.getByText('CHILD')).toBeInTheDocument();
  });

  it('no transform for 0', () => {
    mockUseOrientation.mockReturnValue({ rotation: 0 });
    render(<RotationWrapper><div>x</div></RotationWrapper>);
    const w = screen.getByTestId('rotation-wrapper');
    expect(w.style.transform).toBe('');
    expect(w.style.width).toBe('100vw');
    expect(w.style.height).toBe('100vh');
  });

  it('rotate(90deg) with dimension swap for 90', () => {
    mockUseOrientation.mockReturnValue({ rotation: 90 });
    render(<RotationWrapper><div>x</div></RotationWrapper>);
    const w = screen.getByTestId('rotation-wrapper');
    expect(w.style.transform).toBe('rotate(90deg) translateY(-100%)');
    expect(w.style.width).toBe('100vh');
    expect(w.style.height).toBe('100vw');
  });

  it('rotate(180deg) for 180', () => {
    mockUseOrientation.mockReturnValue({ rotation: 180 });
    render(<RotationWrapper><div>x</div></RotationWrapper>);
    const w = screen.getByTestId('rotation-wrapper');
    expect(w.style.transform).toBe('rotate(180deg) translate(-100%, -100%)');
  });

  it('rotate(270deg) with dimension swap for 270', () => {
    mockUseOrientation.mockReturnValue({ rotation: 270 });
    render(<RotationWrapper><div>x</div></RotationWrapper>);
    const w = screen.getByTestId('rotation-wrapper');
    expect(w.style.transform).toBe('rotate(270deg) translateX(-100%)');
    expect(w.style.width).toBe('100vh');
  });
});
