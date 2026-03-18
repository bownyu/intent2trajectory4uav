from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from statistics import mean
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from intent2trajectory.generator import generate_sample, load_config, validate_sample  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate a small attack diversification report for one airframe.')
    parser.add_argument('--config', default=str(ROOT / 'configs' / 'dataset_config.json'))
    parser.add_argument('--airframe', default='quad_small')
    parser.add_argument('--count', type=int, default=20)
    parser.add_argument('--seed', type=int, default=20260318)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)
    cfg['progress'] = {'enabled': False}
    if args.airframe in cfg['airframes']['profiles']:
        cfg['airframes']['profiles'][args.airframe]['enabled'] = True
    accepted = []
    attempt = 0
    while len(accepted) < args.count and attempt < args.count * 10:
        sample = generate_sample('attack', seed=args.seed + attempt, profile=cfg, airframe_name=args.airframe)
        result = validate_sample(sample, cfg)
        if result['valid']:
            accepted.append(sample['metadata'])
        attempt += 1
    if not accepted:
        print(json.dumps({'accepted': 0, 'attempted': attempt}, ensure_ascii=False, indent=2))
        return 1

    realized = Counter(md.get('pressure_profile_realized', '') for md in accepted)
    target = Counter(md.get('pressure_profile_target', '') for md in accepted)
    report = {
        'accepted': len(accepted),
        'attempted': attempt,
        'airframe': args.airframe,
        'target_profile_breakdown': dict(target),
        'realized_profile_breakdown': dict(realized),
        'commit_onset_ratio': {
            'min': min(md.get('commit_onset_ratio', 0.0) for md in accepted),
            'mean': mean(md.get('commit_onset_ratio', 0.0) for md in accepted),
            'max': max(md.get('commit_onset_ratio', 0.0) for md in accepted),
        },
        'terminal_spike_ratio': {
            'min': min(md.get('terminal_spike_ratio', 0.0) for md in accepted),
            'mean': mean(md.get('terminal_spike_ratio', 0.0) for md in accepted),
            'max': max(md.get('terminal_spike_ratio', 0.0) for md in accepted),
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
