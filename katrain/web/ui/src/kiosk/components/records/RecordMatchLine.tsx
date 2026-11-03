import type { CSSProperties } from 'react';
import './recordMatchLine.css';

type Player = { name: string; rank: string | null };

type Props = {
  black: Player;
  white: Player;
  result: string;
  variant: 'kifu' | 'history';
  winner?: 'B' | 'W' | null;
};

const rankSize = { '--kiosk-base-size': '18px' } as CSSProperties;

/** Shared, non-interactive historical match line for the two record lists. */
export default function RecordMatchLine({ black, white, result, variant, winner }: Props) {
  const rank = (value: string | null) => value ? (
    <small className="record-match__rank" title={value}
      aria-label={value} data-kiosk-base-size="" style={rankSize}>
      {value}
    </small>
  ) : null;

  return (
    <span className={`record-match record-match--${variant}`}>
      <span className={`record-match__player record-match__player--black${winner === 'B' ? ' is-winner' : ''}`}>
        <span className="record-match__stone record-match__stone--black" aria-hidden="true" />
        <span className="record-match__name" title={black.name}>{black.name}</span>
        {rank(black.rank)}
      </span>
      <span className="record-match__result" title={result} aria-label={result}>
        <span className="record-match__result-label">{result}</span>
      </span>
      <span className={`record-match__player record-match__player--white${winner === 'W' ? ' is-winner' : ''}`}>
        {rank(white.rank)}
        <span className="record-match__name" title={white.name}>{white.name}</span>
        <span className="record-match__stone record-match__stone--white" aria-hidden="true" />
      </span>
    </span>
  );
}
