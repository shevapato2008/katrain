#!/usr/bin/env python3
"""
SGF数据质量分析脚本

用法:
  python scripts/analyze_sgf_quality.py              # 输出完整报告
  python scripts/analyze_sgf_quality.py --list-ambiguous  # 列出所有模糊注释的题目
  python scripts/analyze_sgf_quality.py --list-no-marker  # 列出无标准标记的题目
  python scripts/analyze_sgf_quality.py --check 3D/1014   # 检查特定题目
"""

import argparse
import os
import sys
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from katrain.core.sgf_parser import SGF


DATA_DIR = Path("data/life-n-death")

# 标准标记模式
SUCCESS_MARKERS = ['恭喜', '答对', '正确', '黑活', '白活', '净活', '淨活', '眼杀', '净杀', '淨杀', '黑死', '白死']
FAIL_MARKERS = ['失败', '重来', '错误', '不行', '不成', '0 分', '0分']
KO_MARKERS = ['劫']


def classify_comment(comment: str, first_player: str = 'B') -> str:
    """
    对叶子节点注释进行分类
    返回: 'success', 'fail', 'ko', 'ambiguous'
    """
    if not comment:
        return 'empty'

    # 标准成功标记
    if any(m in comment for m in ['恭喜', '答对']):
        return 'success'
    if '正确' in comment and '错误' not in comment:
        return 'success'

    # 结果描述 - 需要结合先手方判断
    if '黑活' in comment or '淨活' in comment and '黑' in comment:
        return 'success' if first_player == 'B' else 'fail'
    if '白活' in comment or '淨活' in comment and '白' in comment:
        return 'success' if first_player == 'W' else 'fail'
    if '黑死' in comment:
        return 'fail' if first_player == 'B' else 'success'
    if '白死' in comment:
        return 'fail' if first_player == 'W' else 'success'
    if '眼杀' in comment or '净杀' in comment or '淨杀' in comment:
        return 'success'
    if '净活' in comment or '淨活' in comment:
        return 'success'

    # 失败标记
    if any(m in comment for m in FAIL_MARKERS):
        return 'fail'

    # 打劫
    if any(m in comment for m in KO_MARKERS):
        return 'ko'

    return 'ambiguous'


def get_leaf_nodes(node, leaves=None, depth=0):
    """获取所有叶子节点及其深度"""
    if leaves is None:
        leaves = []
    if not node.children:
        leaves.append((node, depth))
    for child in node.children:
        get_leaf_nodes(child, leaves, depth + 1)
    return leaves


def analyze_file(filepath: Path) -> dict:
    """分析单个SGF文件"""
    result = {
        'id': filepath.stem,
        'level': filepath.parent.name,
        'has_standard_marker': False,
        'leaf_classifications': Counter(),
        'ambiguous_comments': [],
        'max_depth': 0,
        'issues': []
    }

    try:
        root = SGF.parse_file(str(filepath))
    except Exception as e:
        result['issues'].append(f'解析错误: {e}')
        return result

    # 获取先手方
    pl = root.get_property('PL', 'B') or 'B'

    # 分析叶子节点
    leaves = get_leaf_nodes(root)
    result['max_depth'] = max(d for _, d in leaves) if leaves else 0

    for node, depth in leaves:
        comment = node.get_property('C', '')
        classification = classify_comment(comment, pl)
        result['leaf_classifications'][classification] += 1

        if classification == 'success' and any(m in comment for m in ['恭喜', '答对']):
            result['has_standard_marker'] = True

        if classification == 'ambiguous' and comment:
            result['ambiguous_comments'].append({
                'depth': depth,
                'comment': comment[:80]
            })

    # 检查问题
    if result['max_depth'] < 2:
        result['issues'].append(f'变化树过浅: max_depth={result["max_depth"]}')

    if not result['leaf_classifications'].get('success', 0):
        result['issues'].append('无成功路径标记')

    return result


def main():
    parser = argparse.ArgumentParser(description='SGF数据质量分析')
    parser.add_argument('--list-ambiguous', action='store_true', help='列出所有有模糊注释的题目')
    parser.add_argument('--list-no-marker', action='store_true', help='列出无标准成功标记的题目')
    parser.add_argument('--check', type=str, help='检查特定题目 (如 3D/1014)')
    parser.add_argument('--output', type=str, help='输出到文件')
    args = parser.parse_args()

    # 检查单个文件
    if args.check:
        level, pid = args.check.split('/')
        filepath = DATA_DIR / level / f'{pid}.sgf'
        if not filepath.exists():
            print(f'文件不存在: {filepath}')
            return
        result = analyze_file(filepath)
        print(f"\n=== {args.check} ===")
        print(f"叶子节点分类: {dict(result['leaf_classifications'])}")
        print(f"最大深度: {result['max_depth']}")
        print(f"有标准标记: {result['has_standard_marker']}")
        if result['ambiguous_comments']:
            print(f"模糊注释 ({len(result['ambiguous_comments'])}个):")
            for ac in result['ambiguous_comments'][:5]:
                print(f"  depth={ac['depth']}: \"{ac['comment']}\"")
        if result['issues']:
            print(f"问题: {result['issues']}")
        return

    # 分析所有文件
    all_results = []
    for level in ['3D', '4D']:
        level_dir = DATA_DIR / level
        if not level_dir.exists():
            continue
        for f in sorted(level_dir.glob('*.sgf')):
            result = analyze_file(f)
            all_results.append(result)

    # 输出列表
    output_lines = []

    if args.list_ambiguous:
        ambiguous = [r for r in all_results if r['ambiguous_comments']]
        output_lines.append(f"# 有模糊注释的题目 ({len(ambiguous)}个)\n")
        for r in ambiguous:
            output_lines.append(f"{r['level']}/{r['id']}")
            for ac in r['ambiguous_comments'][:2]:
                output_lines.append(f"  - depth={ac['depth']}: \"{ac['comment']}\"")

    elif args.list_no_marker:
        no_marker = [r for r in all_results if not r['has_standard_marker']]
        output_lines.append(f"# 无标准成功标记的题目 ({len(no_marker)}个)\n")
        for r in no_marker:
            output_lines.append(f"{r['level']}/{r['id']}: {dict(r['leaf_classifications'])}")

    else:
        # 完整报告
        total = len(all_results)
        with_standard = sum(1 for r in all_results if r['has_standard_marker'])
        with_ambiguous = sum(1 for r in all_results if r['ambiguous_comments'])
        shallow = sum(1 for r in all_results if r['max_depth'] < 2)

        all_classifications = Counter()
        for r in all_results:
            all_classifications.update(r['leaf_classifications'])

        output_lines.append("=" * 60)
        output_lines.append("SGF 数据质量分析报告")
        output_lines.append("=" * 60)
        output_lines.append(f"\n总文件数: {total}")
        output_lines.append(f"有标准成功标记 (恭喜/答对): {with_standard} ({with_standard*100/total:.1f}%)")
        output_lines.append(f"有模糊注释: {with_ambiguous} ({with_ambiguous*100/total:.1f}%)")
        output_lines.append(f"变化树过浅: {shallow}")
        output_lines.append(f"\n叶子节点分类统计:")
        for cls, count in all_classifications.most_common():
            output_lines.append(f"  {cls}: {count}")

    # 输出
    output_text = '\n'.join(output_lines)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_text)
        print(f'已输出到 {args.output}')
    else:
        print(output_text)


if __name__ == '__main__':
    main()
