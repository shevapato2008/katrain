import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, it } from 'vitest';
import type { VerifiedAnalysisParameters } from '../../types/kifu';
import { kifuDefaultRulesSource, kifuEventRules, kifuRulesLabel } from './kifuRules';

const parameters: VerifiedAnalysisParameters = {
  version: 1, verified: true, rules: 'japanese', komi: 6.5,
  sgf_sha256: 'sgf', parameter_sha256: 'params',
  provenance: { source: 'verified_evidence', evidence: { event_rules: 'korean' } },
};

it('preserves wire and raw rules while displaying Korean event rules for all nine approved games', () => {
  const evidence = JSON.parse(readFileSync(resolve(process.cwd(), '../../../docs/operations/kifu-rules-approved-49-20261007.json'), 'utf8')) as Array<{
    album_id: number; verified: true; rules: string; komi: number; sgf_sha256: string; event_rules?: string; raw_sgf_rules: string;
  }>;
  const koreanGames = evidence.filter(row => row.event_rules === 'korean');
  expect(koreanGames.map(row => row.album_id)).toEqual([24108, 24151, 24152, 24153, 24154, 24156, 24157, 24158, 24159]);
  for (const row of koreanGames) {
    const snapshot = { ...parameters, verified: row.verified, rules: row.rules, komi: row.komi, sgf_sha256: row.sgf_sha256,
      provenance: { source: 'verified_evidence', evidence: row } };
    const before = JSON.stringify(snapshot);
    expect(kifuRulesLabel(kifuEventRules(snapshot, row.raw_sgf_rules), (_key, fallback) => fallback)).toBe('韩国规则');
    expect(snapshot.rules).toBe('japanese');
    expect(row.raw_sgf_rules).toBe('japanese');
    expect(JSON.stringify(snapshot)).toBe(before);
  }
});

it('accepts only supported event rules from verified evidence with an equivalent wire rule', () => {
  for (const provenance of [
    {},
    { source: 'sgf', evidence: { event_rules: 'korean' } },
    { source: 'verified_evidence', evidence: null },
    { source: 'verified_evidence', evidence: { event_rules: 42 } },
    { source: 'verified_evidence', evidence: { event_rules: 'unsupported' } },
    { source: 'verified_evidence', evidence: { event_rules: 'constructor' } },
    { source: 'verified_evidence', evidence: { event_rules: 'chinese' } },
  ]) {
    expect(kifuEventRules({ ...parameters, provenance }, 'chinese')).toBe('japanese');
  }
  expect(kifuEventRules({ ...parameters, verified: false }, 'chinese')).toBe('japanese');
  expect(kifuEventRules({ ...parameters, rules: 'chinese' }, null)).toBe('chinese');
  expect(kifuEventRules({ ...parameters, rules: 'korean' }, null)).toBe('korean');
  expect(kifuEventRules({ ...parameters, rules: 'korean', provenance: { source: 'verified_evidence', evidence: { event_rules: 'japanese' } } }, null)).toBe('japanese');
  expect(kifuEventRules(null, 'aga-button')).toBe('aga-button');
  expect(kifuRulesLabel(kifuEventRules(null, null), (_key, fallback) => fallback)).toBe('规则待核验');
});

it.each([['japanese', 6.5, '日本规则'], ['chinese', 7.5, '中国规则']] as const)('labels default %s and explains its komi source without event verification', (rules, komi, label) => {
  const snapshot: VerifiedAnalysisParameters = { ...parameters, version: 3, verified: false, rules, komi,
    provenance: { source: 'komi_default', raw_rules: null, raw_komi: String(komi), policy: 'komi-default-v1', evidence: { event_rules: 'korean' } } };
  const before = JSON.stringify(snapshot);
  expect(kifuRulesLabel(kifuEventRules(snapshot, null), (_key, fallback) => fallback, snapshot)).toBe(`${label}（默认）`);
  expect(kifuDefaultRulesSource(snapshot, (_key, fallback) => fallback)).toBe(`SGF 未记录规则；按贴目 ${komi} 默认采用${label}，未核验赛事实际规则。`);
  expect(snapshot.provenance.raw_rules).toBeNull();
  expect(snapshot.provenance.policy).toBe('komi-default-v1');
  expect(JSON.stringify(snapshot)).toBe(before);
  expect(kifuDefaultRulesSource(parameters, (_key, fallback) => fallback)).toBeNull();
});
