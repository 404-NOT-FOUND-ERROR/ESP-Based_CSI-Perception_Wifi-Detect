#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run offline Python checks and optional C compiler checks in this repository."""
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    compiler = parser.add_mutually_exclusive_group()
    compiler.add_argument('--zig', type=Path, help='Path to zig; invokes zig cc')
    compiler.add_argument('--cc', help='C11 compiler executable, e.g. gcc or clang')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / '.build'
    output.mkdir(exist_ok=True)
    results = []
    env = dict(os.environ)
    env['ZIG_LOCAL_CACHE_DIR'] = str(output / 'zig-cache/local')
    env['ZIG_GLOBAL_CACHE_DIR'] = str(output / 'zig-cache/global')

    def run(name, command, stdout_file=None):
        process = subprocess.run([str(value) for value in command], cwd=root, env=env,
                                 capture_output=True, text=True, encoding='utf-8', errors='replace')
        if stdout_file is not None and process.returncode == 0:
            stdout_file.write_text(process.stdout, encoding='utf-8')
        results.append({'name': name, 'exit_code': process.returncode,
                        'stdout': process.stdout if stdout_file is None else f'written to {stdout_file.name}',
                        'stderr': process.stderr})
        print(f'{name}: {"PASS" if process.returncode == 0 else "FAIL"}')
        if process.returncode:
            raise RuntimeError(process.stdout + process.stderr)

    try:
        hotspot = root / 'fixtures/simulated-hotspot.json'
        csi = root / 'fixtures/simulated-capture.jsonl'
        c_command = [str(args.zig), 'cc'] if args.zig else [args.cc] if args.cc else None
        if c_command:
            suffix = '.exe' if os.name == 'nt' else ''
            csi_dir = root / 'components/app_csi_probe'
            radio_dir = root / 'components/app_radio_probe'
            includes = [csi_dir / 'include', csi_dir / 'host/compat', radio_dir / 'include',
                        root / 'components/app_radio_contract/include']
            flags = ['-std=c11', '-O2', '-UNDEBUG', '-Wall', '-Wextra', '-Werror']
            flags += ['-I' + str(path) for path in includes]

            def build(name, sources, execute=True):
                binary = output / (name + suffix)
                run(name + ' compile', c_command + flags + sources + ['-o', binary])
                if execute:
                    run(name, [binary])
                return binary

            build('n1-core', [radio_dir / 'app_radio_probe.c', radio_dir / 'host/test_probe.c'])
            csi_binary = build('csi-core', [csi_dir / 'app_csi_probe.c', csi_dir / 'csi_json.c',
                                         csi_dir / 'csi_s31.c', csi_dir / 'host/test_csi.c'])
            if os.name == 'nt':
                build('csi-concurrency', [csi_dir / 'app_csi_probe.c', csi_dir / 'host/test_threads.c'])
            else:
                results.append({'name': 'csi-concurrency', 'status': 'Windows-only; not run on this host'})
            csi = output / 'generated-csi.jsonl'
            run('CSI C fixture', [csi_binary, '--fixture'], csi)
            fixture_binary = build('n1-export', [radio_dir / 'app_radio_probe.c',
                                               root / 'tools/radio_review/tests/export_fixture.c'], execute=False)
            hotspot = output / 'generated-hotspot.json'
            run('N1 C fixture', [fixture_binary], hotspot)

        run('CSI analyzer (11 tests)', [sys.executable, 'components/app_csi_probe/host/test_analyzer.py', csi])
        run('Offline review (23 tests)', [sys.executable, 'tools/radio_review/tests/test_review.py', hotspot, csi])
        run('Package links and provenance', [sys.executable, 'tools/verify_package.py'])
    except (OSError, RuntimeError) as error:
        results.append({'error': str(error)})
        return_code = 1
    else:
        return_code = 0
    report = {'schema': 'radio-lab.desktop-check.v1',
              'time_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'compiler_checks': c_command is not None, 'simulated': True,
              'result': 'passed' if return_code == 0 else 'failed', 'checks': results}
    (output / 'test-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return return_code


if __name__ == '__main__':
    raise SystemExit(main())
