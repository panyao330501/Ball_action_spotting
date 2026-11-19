"""Apply reviewed Pass identity and frame decisions to isolated training folds."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def csvread(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return digest(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--review', type=Path, required=True)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--frozen', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise FileExistsError(a.output)
    source, reviewed = csvread(a.source), csvread(a.review)
    originals = {r['review_id']: r for r in source}
    if len(originals) != 17 or len(reviewed) != 17 or len({r['review_id'] for r in reviewed}) != 17:
        raise ValueError('审核行数或 ID 不完整')
    editable = {'identity_decision', 'confirmed_pass_time_sec', 'confirmed_frame_index_25fps', 'new_comment'}
    for row in reviewed:
        original = originals[row['review_id']]
        if row.keys() != original.keys() or any(row[k] != original[k] for k in row if k not in editable):
            raise ValueError(f"原始字段改变：{row['review_id']}")
        if row['identity_decision'] not in {'same_nearest_gt', 'separate_pass', 'unclear'}:
            raise ValueError(f"身份判断无效：{row['review_id']}")
        if row['identity_decision'] != 'unclear':
            t, frame = float(row['confirmed_pass_time_sec']), int(row['confirmed_frame_index_25fps'])
            start = float(row['clip_start_sec'])
            if not math.isfinite(t) or abs(t - frame / 25) > 0.001 or not start <= t <= start + 10:
                raise ValueError(f"审核时间或帧号无效：{row['review_id']}")
    base, frozen = read(a.base / 'manifest.json'), read(a.frozen / 'manifest.json')
    if digest(a.frozen / 'manifest.json') != base['frozen_manifest_sha256']:
        raise ValueError('冻结清单哈希不符')
    results = []
    for fold in base['folds']:
        name = fold['fold_id']; ids = set(fold['train_video_ids']); test = set(fold['test_video_ids'])
        if ids & test:
            raise ValueError('训练测试重叠')
        for filename, expected in fold['output_sha256'].items():
            if digest(a.base / name / filename) != expected:
                raise ValueError(f'原训练标签哈希不符：{name}/{filename}')
        labels = read(a.base / name / 'train_pass_events.json')
        excluded = read(a.base / name / 'excluded_bepro_pass.json')
        pending = read(a.base / name / 'pending_pass_additions.json')
        ignore = read(a.base / name / 'ignore_intervals.json')
        corrections = read(a.base / name / 'time_corrections.json')
        proxies = read(a.base / name / 'drive_proxy_events.json')
        lookup = {x['event_id']: x for x in labels}
        updates, additions, uncertain = [], [], []
        for row in reviewed:
            if row['video_id'] not in ids:
                continue
            rid = row['review_id']; event_id = row['nearest_bepro_event_id']; decision = row['identity_decision']
            if decision == 'unclear':
                uncertain.append(rid); continue
            t = float(row['confirmed_pass_time_sec']); frame = int(row['confirmed_frame_index_25fps'])
            if decision == 'same_nearest_gt':
                if event_id not in lookup or lookup[event_id]['video_id'] != row['video_id']:
                    raise ValueError(f'匹配事件不在训练正例中：{rid}')
                item = lookup[event_id]
                updates.append({'review_id': rid, 'event_id': event_id, 'previous_time_sec': item['training_time_sec'], 'confirmed_time_sec': t})
                item.update(training_time_sec=t, training_frame_index_25fps=frame,
                            source='identity_review_time_correction', review_id=rid)
            else:
                event = {'event_id': 'human-pass-' + rid, 'video_id': row['video_id'], 'label': 'Pass',
                         'bepro_time_sec': None, 'training_time_sec': t, 'training_frame_index_25fps': frame,
                         'source': 'identity_review_separate_pass', 'review_id': rid, 'visibility': 'VISIBLE'}
                if any(x['video_id'] == row['video_id'] and abs(x['training_time_sec'] - t) < 0.5 for x in labels):
                    raise ValueError(f'新增传球与已有正例过近：{rid}')
                labels.append(event); additions.append(event)
            pending = [x for x in pending if x['review_id'] != rid]
            ignore = [x for x in ignore if not (x['review_id'] == rid and x['reason'] == 'confirmed_pass_pending_exact_label')]
        # Two comments explicitly identify the nearby Bepro event as reception/goalkeeper catch.
        for rid in ('u18-review-002', 'u18-train-025'):
            row = next(x for x in reviewed if x['review_id'] == rid)
            if row['video_id'] not in ids:
                continue
            item = lookup.get(row['nearest_bepro_event_id'])
            if item is None:
                raise ValueError(f'待排除标签不在训练集：{rid}')
            labels.remove(item)
            excluded.append({'event_id': item['event_id'], 'video_id': item['video_id'],
                             'bepro_time_sec': item['bepro_time_sec'], 'reason': 'identity_review_nonpass_nearest',
                             'review_id': rid, 'comment': row['new_comment']})
            ignore.append({'video_id': item['video_id'], 'start_sec': max(0, item['bepro_time_sec'] - 3),
                           'end_sec': item['bepro_time_sec'] + 3, 'reason': 'identity_review_nonpass_nearest', 'review_id': rid})
        if {x['video_id'] for x in labels + excluded + pending + proxies} - ids:
            raise ValueError('训练数据含留出比赛')
        directory = a.output / name; directory.mkdir(parents=True)
        hashes = {}
        for filename, items in [('train_pass_events.json', labels), ('excluded_bepro_pass.json', excluded),
                                ('pending_pass_additions.json', pending), ('ignore_intervals.json', ignore),
                                ('time_corrections.json', corrections), ('drive_proxy_events.json', proxies),
                                ('identity_updates.json', updates), ('identity_additions.json', additions)]:
            hashes[filename] = write(directory / filename, items)
        results.append({**{k: fold[k] for k in ('fold_id', 'train_video_ids', 'test_video_ids', 'frozen_train_gt_sha256', 'frozen_test_gt_sha256')},
                        'training_pass': len(labels), 'excluded_bepro_pass': len(excluded),
                        'pending_pass_additions': len(pending), 'identity_corrections': len(updates),
                        'identity_additions': len(additions), 'identity_unclear': len(uncertain),
                        'drive_proxy_events': len(proxies), 'output_sha256': hashes})
    manifest = {'schema_version': 3, 'purpose': 'match-isolated training only',
                'base_manifest_sha256': digest(a.base / 'manifest.json'),
                'frozen_manifest_sha256': digest(a.frozen / 'manifest.json'),
                'identity_source_sha256': digest(a.source), 'identity_review_sha256': digest(a.review), 'folds': results}
    write(a.output / 'manifest.json', manifest)
    print(json.dumps(results, ensure_ascii=False))


if __name__ == '__main__':
    main()
