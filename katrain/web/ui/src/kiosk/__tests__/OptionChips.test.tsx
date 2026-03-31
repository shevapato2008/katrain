import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import OptionChips from '../components/common/OptionChips';

describe('OptionChips', () => {
  it('renders label and all options', () => {
    render(
      <ThemeProvider theme={kioskTheme}>
        <OptionChips
          label="棋盘"
          options={[
            { value: 9, label: '9路' },
            { value: 13, label: '13路' },
            { value: 19, label: '19路' },
          ]}
          value={19}
          onChange={() => {}}
        />
      </ThemeProvider>
    );
    expect(screen.getByText('棋盘')).toBeInTheDocument();
    expect(screen.getByText('9路')).toBeInTheDocument();
    expect(screen.getByText('13路')).toBeInTheDocument();
    expect(screen.getByText('19路')).toBeInTheDocument();
  });

  it('calls onChange when an option is clicked', () => {
    const onChange = vi.fn();
    render(
      <ThemeProvider theme={kioskTheme}>
        <OptionChips
          label="棋盘"
          options={[
            { value: 9, label: '9路' },
            { value: 19, label: '19路' },
          ]}
          value={19}
          onChange={onChange}
        />
      </ThemeProvider>
    );
    fireEvent.click(screen.getByText('9路'));
    expect(onChange).toHaveBeenCalledWith(9);
  });
});
