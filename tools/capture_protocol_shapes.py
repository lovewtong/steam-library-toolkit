"""Explicit local-session probe; export field types, never raw Steam responses."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from steam_auth import collect_client
from steam_sources import atomic_json, utc_now


def main():
    parser = argparse.ArgumentParser(description='显式使用 Windows 本机会话采集脱敏协议字段类型；不保存原始响应')
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = collect_client(local_session=True, capture_protocol_shapes=True)
        shapes = result.get('protocol_shapes')
        if not shapes or not shapes.get('observations'):
            raise ValueError('No protocol observations')
        atomic_json(args.output, {**shapes, 'captured_at': utc_now(),
                                 'origin': 'live_windows_local_session',
                                 'client_state': result['client']['state'],
                                 'api_state': result['api']['state']})
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, RuntimeError, KeyError):
        print('协议采样失败；未输出原始响应或凭据')
        return 1
    print(f'已保存 {len(shapes["observations"])} 条字段类型观察：{args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
