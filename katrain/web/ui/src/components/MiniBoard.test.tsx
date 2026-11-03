import { render } from '@testing-library/react';
import { expect, it } from 'vitest';
import MiniBoard from './MiniBoard';
import { stoneSpriteUrl } from './board/stoneAppearance';

it('uses canonical SGF coordinates for shared thumbnail stone images', () => {
  const { container } = render(<MiniBoard boardSize={19} blackStones={['dd']} whiteStones={['ed']} />);
  const sprites = container.querySelectorAll('image');
  expect(sprites).toHaveLength(2);
  expect(sprites[0]).toHaveAttribute('href', stoneSpriteUrl('B', 19, 3, 3));
  expect(sprites[1]).toHaveAttribute('href', stoneSpriteUrl('W', 19, 4, 3));
  expect(sprites[0].getAttribute('width')).toBe(sprites[1].getAttribute('width'));
});
