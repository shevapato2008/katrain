import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PhysicalModeToggle from '../components/tsumego/PhysicalModeToggle';
import { readPhysicalMode, writePhysicalMode } from '../pages/tsumegoUnits';

describe('Physical mode persistence and component', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('readPhysicalMode and writePhysicalMode', () => {
    it('should default to false with empty localStorage', () => {
      expect(readPhysicalMode()).toBe(false);
    });

    it('should persist and read true value', () => {
      writePhysicalMode(true);
      expect(readPhysicalMode()).toBe(true);
    });

    it('should persist and read false value', () => {
      writePhysicalMode(true);
      writePhysicalMode(false);
      expect(readPhysicalMode()).toBe(false);
    });

    it('should handle localStorage unavailability gracefully', () => {
      const getItem = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
        throw new Error('Storage unavailable');
      });
      const setItem = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new Error('Storage unavailable');
      });

      expect(readPhysicalMode()).toBe(false);
      writePhysicalMode(true); // should not throw
      writePhysicalMode(false); // should not throw

      getItem.mockRestore();
      setItem.mockRestore();
    });
  });

  describe('PhysicalModeToggle component', () => {
    it('should render with capable=true', () => {
      const handleChange = vi.fn();
      render(
        <PhysicalModeToggle checked={false} onChange={handleChange} capable={true} />
      );

      expect(screen.getByTestId('physical-mode-toggle')).toBeInTheDocument();
      expect(screen.getByText('使用物理棋盘')).toBeInTheDocument();
    });

    it('should render with capable=false and show disabled label', () => {
      const handleChange = vi.fn();
      render(
        <PhysicalModeToggle checked={false} onChange={handleChange} capable={false} />
      );

      expect(screen.getByText('未检测到实体棋盘')).toBeInTheDocument();
      const switchElement = screen.getByRole('switch');
      expect(switchElement).toBeDisabled();
    });

    it('should call onChange with true when switch is clicked and capable=true', () => {
      const handleChange = vi.fn();
      render(
        <PhysicalModeToggle checked={false} onChange={handleChange} capable={true} />
      );

      const switchElement = screen.getByRole('switch');
      fireEvent.click(switchElement);

      expect(handleChange).toHaveBeenCalledWith(true);
    });

    it('should render checked state when checked=true and capable=true', () => {
      const handleChange = vi.fn();
      render(
        <PhysicalModeToggle checked={true} onChange={handleChange} capable={true} />
      );

      const switchElement = screen.getByRole('switch') as HTMLInputElement;
      expect(switchElement.checked).toBe(true);
    });

    it('should not render checked when capable=false even if checked=true', () => {
      const handleChange = vi.fn();
      render(
        <PhysicalModeToggle checked={true} onChange={handleChange} capable={false} />
      );

      const switchElement = screen.getByRole('switch') as HTMLInputElement;
      expect(switchElement.checked).toBe(false);
    });
  });
});
