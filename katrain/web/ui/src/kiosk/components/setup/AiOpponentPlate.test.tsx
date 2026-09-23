import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AiOpponentPlate from './AiOpponentPlate';

describe('AiOpponentPlate', () => {
  it('把档位读数放在名牌上,不再单独占一行', () => {
    render(<AiOpponentPlate
      name="星皮猴" levelName="2 段" displayElo={1500} refRank="业余 2 段"
      index={21} total={39} onOpen={() => {}} testId="plate"
    />);
    expect(screen.getByTestId('plate')).toHaveTextContent('星皮猴');
    expect(screen.getByTestId('plate')).toHaveTextContent('第 22 / 39 档');
    expect(screen.getByTestId('plate')).toHaveTextContent('1500');
  });

  it('平台没给对标棋力就不画那一段,不写「未知」', () => {
    render(<AiOpponentPlate
      name="星猛虎" levelName="9 段" displayElo={3000}
      index={38} total={39} onOpen={() => {}} testId="plate"
    />);
    expect(screen.getByTestId('plate')).not.toHaveTextContent('对标');
  });

  it('点名牌打开全表', async () => {
    const onOpen = vi.fn();
    render(<AiOpponentPlate
      name="星皮猴" levelName="2 段" displayElo={1500}
      index={0} total={39} onOpen={onOpen} testId="plate"
    />);
    await userEvent.click(screen.getByTestId('plate'));
    expect(onOpen).toHaveBeenCalledOnce();
  });
});
