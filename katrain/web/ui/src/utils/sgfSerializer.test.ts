import { describe, it, expect } from 'vitest';
import { sgfToMoves, movesToSGF, validateSGFRoundTrip } from './sgfSerializer';
import type { SGFMetadata } from './sgfSerializer';

const defaultMeta: SGFMetadata = {
  boardSize: 19, komi: 6.5, handicap: 0, rules: 'japanese',
  playerBlack: '', playerWhite: '',
};

describe('sgfToMoves', () => {
  it('parses a simple game', () => {
    const sgf = '(;FF[4]GM[1]SZ[19]KM[6.5];B[pd];W[dd];B[pp];W[dp])';
    const { moves, stoneColors, metadata } = sgfToMoves(sgf);
    expect(moves).toEqual(['Q16', 'D16', 'Q4', 'D4']);
    expect(stoneColors).toEqual(['B', 'W', 'B', 'W']);
    expect(metadata.boardSize).toBe(19);
    expect(metadata.komi).toBe(6.5);
  });

  it('parses handicap AB[] stones as moves before game moves', () => {
    const sgf = '(;FF[4]SZ[19]HA[3]AB[pd][dp][pp];W[dd];B[qf])';
    const { moves, stoneColors } = sgfToMoves(sgf);
    // AB stones come first (as black moves), then game moves
    expect(moves).toEqual(['Q16', 'D4', 'Q4', 'D16', 'R14']);
    expect(stoneColors).toEqual(['B', 'B', 'B', 'W', 'B']);
  });

  it('handles pass moves (empty B[]/W[])', () => {
    const sgf = '(;FF[4]SZ[19];B[pd];W[];B[dd])';
    const { moves, stoneColors } = sgfToMoves(sgf);
    expect(moves).toEqual(['Q16', 'pass', 'D16']);
    expect(stoneColors).toEqual(['B', 'W', 'B']);
  });

  it('handles tt pass notation', () => {
    const sgf = '(;FF[4]SZ[19];B[pd];W[tt];B[dd])';
    const { moves, stoneColors } = sgfToMoves(sgf);
    expect(moves).toEqual(['Q16', 'pass', 'D16']);
    expect(stoneColors).toEqual(['B', 'W', 'B']);
  });

  it('follows only the main line (first variation)', () => {
    const sgf = '(;FF[4]SZ[19];B[pd];W[dd](;B[pp];W[dp])(;B[qp];W[cq]))';
    const { moves } = sgfToMoves(sgf);
    // Should follow first variation: B[pp], W[dp]
    expect(moves).toEqual(['Q16', 'D16', 'Q4', 'D4']);
  });

  it('follows main line through nested variations', () => {
    const sgf = '(;FF[4]SZ[19];B[pd](;W[dd](;B[pp])(;B[qp]))(;W[dp]))';
    const { moves } = sgfToMoves(sgf);
    // Main line: B[pd] → W[dd] (first var) → B[pp] (first nested var)
    expect(moves).toEqual(['Q16', 'D16', 'Q4']);
  });

  it('ignores variations completely when main line has no branches', () => {
    const sgf = '(;FF[4]SZ[19];B[pd];W[dd];B[pp])';
    const { moves } = sgfToMoves(sgf);
    expect(moves).toEqual(['Q16', 'D16', 'Q4']);
  });

  it('handles escaped characters in property values', () => {
    const sgf = '(;FF[4]SZ[19]PB[Lee \\[9p\\]];B[pd])';
    const { moves, metadata } = sgfToMoves(sgf);
    expect(moves).toEqual(['Q16']);
    expect(metadata.playerBlack).toBe('Lee [9p]');
  });

  it('handles 9x9 board', () => {
    const sgf = '(;FF[4]SZ[9];B[ee];W[ce])';
    const { moves, metadata } = sgfToMoves(sgf);
    expect(metadata.boardSize).toBe(9);
    expect(moves.length).toBe(2);
  });

  it('keeps stoneColors in sync when unparseable coords are encountered', () => {
    // Coordinate "zz" is out of range — should be silently skipped
    // but stoneColors must stay in sync with moves
    const sgf = '(;FF[4]SZ[19];B[pd];W[zz];B[dd])';
    const { moves, stoneColors } = sgfToMoves(sgf);
    expect(moves).toEqual(['Q16', 'D16']);
    expect(stoneColors).toEqual(['B', 'B']);
    expect(moves.length).toBe(stoneColors.length);
  });

  it('extracts player names and rules', () => {
    const sgf = '(;FF[4]SZ[19]PB[Go Seigen]PW[Kitani Minoru]RU[japanese]KM[5.5])';
    const { metadata } = sgfToMoves(sgf);
    expect(metadata.playerBlack).toBe('Go Seigen');
    expect(metadata.playerWhite).toBe('Kitani Minoru');
    expect(metadata.rules).toBe('japanese');
    expect(metadata.komi).toBe(5.5);
  });
});

describe('movesToSGF', () => {
  it('serializes a simple game', () => {
    const { sgf, moveCount } = movesToSGF(['Q16', 'D16', 'Q4'], defaultMeta);
    expect(moveCount).toBe(3);
    expect(sgf).toContain(';B[pd]');
    expect(sgf).toContain(';W[dd]');
    expect(sgf).toContain(';B[pp]');
  });

  it('serializes pass moves', () => {
    const { sgf } = movesToSGF(['Q16', 'pass', 'D16'], defaultMeta);
    expect(sgf).toContain(';B[pd]');
    expect(sgf).toContain(';W[]');
    expect(sgf).toContain(';B[dd]');
  });

  it('emits handicap stones as AB[] setup in root node', () => {
    const { sgf, moveCount } = movesToSGF(
      ['Q16', 'D4', 'Q4', 'D16'],
      { ...defaultMeta, handicap: 3 },
      ['B', 'B', 'B', 'W'],
    );
    // First 3 black stones → AB[] setup in root, not ;B[] move nodes
    expect(sgf).toContain('AB[pd][dp][pp]');
    // Only the game move (W[dd]) is a move node
    expect(sgf).toContain(';W[dd]');
    expect(moveCount).toBe(1); // Only 1 game move
    // Should NOT contain ;B[pd] etc as move nodes
    expect(sgf).not.toContain(';B[pd]');
  });
});

describe('round-trip', () => {
  it('simple game survives round-trip', () => {
    const original = ['Q16', 'D16', 'Q4', 'D4'];
    const { sgf } = movesToSGF(original, defaultMeta);
    const { moves } = sgfToMoves(sgf);
    expect(moves).toEqual(original);
  });

  it('handicap game survives round-trip', () => {
    const original = ['Q16', 'D4', 'Q4', 'D16', 'R14'];
    const colors: ('B' | 'W')[] = ['B', 'B', 'B', 'W', 'B'];
    const meta = { ...defaultMeta, handicap: 3 };
    const { sgf } = movesToSGF(original, meta, colors);
    // SGF should use AB[] for handicap, then ;W[dd];B[qf] for game moves
    expect(sgf).toContain('AB[pd][dp][pp]');
    const { moves, stoneColors } = sgfToMoves(sgf);
    // AB[] stones come back as moves (parsed from setup) — same round-trip
    expect(moves).toEqual(original);
    expect(stoneColors).toEqual(colors);
  });

  it('game with passes survives round-trip', () => {
    const original = ['Q16', 'D16', 'pass', 'D4'];
    const { sgf } = movesToSGF(original, defaultMeta);
    const { moves } = sgfToMoves(sgf);
    expect(moves).toEqual(original);
  });

  it('validateSGFRoundTrip returns valid for clean data', () => {
    const result = validateSGFRoundTrip(['Q16', 'D16'], defaultMeta);
    expect(result.valid).toBe(true);
  });
});

describe('variation handling', () => {
  it('complex real-world SGF with multiple variation levels', () => {
    // Root → B[pd] → W[dd] → (main: B[pp] → W[dp]) or (alt: B[qp])
    const sgf = '(;GM[1]FF[4]SZ[19];B[pd];W[dd](;B[pp];W[dp](;B[fq])(;B[eq]))(;B[qp];W[ep]))';
    const { moves } = sgfToMoves(sgf);
    // Main line: pd → dd → pp → dp → fq
    expect(moves).toEqual(['Q16', 'D16', 'Q4', 'D4', 'F3']);
  });

  it('variation at the very first move', () => {
    const sgf = '(;FF[4]SZ[19](;B[pd];W[dd])(;B[qd];W[dp]))';
    const { moves } = sgfToMoves(sgf);
    expect(moves).toEqual(['Q16', 'D16']);
  });

  it('empty variation is handled', () => {
    const sgf = '(;FF[4]SZ[19];B[pd]()(;W[dd]))';
    const { moves } = sgfToMoves(sgf);
    // Empty variation () followed by (;W[dd]) — main is the empty one
    // After empty variation, remaining siblings are skipped
    expect(moves).toEqual(['Q16']);
  });
});
