import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('extract_candidates', Path(__file__).resolve().parents[2] / 'scripts/extract_kifu_sgf_event_candidates.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_multivalue_and_escaped_root_delimiters():
    sgf = '(;GN[file][第2届甲赛]GC[第2届甲赛 | 结果: W+R | 5手]C[注释;\\]括号(仍在值内]DT[2020-01-01];B[aa])'
    result = module.extract({'album_id': 1, 'album_event': 'file', 'series_core': 'file', 'sgf_content': sgf})
    assert result['root_properties']['GN'] == ['file', '第2届甲赛']
    assert result['root_properties']['EV'] == []
    assert len(result['candidates']) == 1
    assert result['candidates'][0]['sources'] == ['GN[1]', 'GC[0]']
    assert result['candidates'][0]['core_differs'] is True


def test_comments_not_cut_at_arbitrary_pipe_or_silently_approved():
    result = module.extract({'album_id': 2, 'album_event': '甲赛', 'series_core': '甲赛',
                             'sgf_content': '(;GN[甲赛]GC[讨论 | 不是结果字段];B[aa])'})
    assert result['candidates'][0]['value'] == '讨论 | 不是结果字段'
    assert result['candidates'][0]['needs_manual_review'] is True
    assert result['decision'].startswith('UNREVIEWED')


def test_same_label_produces_no_supplement_and_root_only_game():
    result = module.extract({'album_id': 3, 'album_event': '甲赛', 'series_core': '甲赛',
                             'sgf_content': '(;GN[甲赛][甲赛]GC[甲赛 | 结果: B+R])'})
    assert result['candidate_count'] == 0


def test_summary_rejects_incomplete_capture(tmp_path):
    import json
    import pytest
    spec2 = importlib.util.spec_from_file_location('summarize_candidates', Path(__file__).resolve().parents[2] / 'scripts/summarize_kifu_sgf_event_candidates.py')
    summary_module = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(summary_module)
    source = tmp_path / 'capture.jsonl'
    source.write_text(json.dumps({'kind': 'manifest', 'meta': {'read_only': 'on'}}) + '\n')
    report = tmp_path / 'report.json'
    with pytest.raises(ValueError, match='incomplete capture'):
        summary_module.summarize(source, tmp_path / 'out.gz', report)
    assert not report.exists()
