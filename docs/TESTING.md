# Desktop Checks

电脑检查只验证源码、记录格式和报告交互。通过它不等于传感器已实测。

## Requirements

- Windows PowerShell 7 or Windows PowerShell 5.1.
- Python 3.10+.
- Zig 0.13+ available as `zig` on `PATH`, or pass an absolute path with `-ZigPath`.
- The host concurrency test uses Windows threads. CSI target compilation additionally needs the owning Mosaico project's pinned ESP-IDF build database and toolchain.

## Run the core and offline tests

From this repository root:

```powershell
pwsh .\tools\test.ps1 -ZigPath 'C:\tools\zig\zig.exe'
```

The script builds N1 and CSI C host tests into `.build/`, checks concurrent queue accounting, then runs CSI analyzer tests and N1/CSI report tests over included fixtures. All included captures are synthetic.

On Linux or macOS with a C11 compiler, run `python tools/test.py --cc gcc`
or `--cc clang`. This runs the portable cores and Python checks; the Windows
thread-accounting check runs on Windows. The GitHub workflow uses GCC on Linux.

## Rebuild the report

```powershell
python .\tools\radio_review\review.py `
  .\fixtures\simulated-hotspot.json `
  .\fixtures\simulated-capture.jsonl `
  --out .\examples\report-rebuilt
```

Use a new output folder each time. Open its `report.html` in a browser. The published sample is [examples/report/report.html](../examples/report/report.html).

## Run one analyzer directly

```powershell
python .\components\app_csi_probe\host\analyze_capture.py `
  .\fixtures\simulated-capture.jsonl --output .\.build\csi-quality.json

python .\components\app_csi_probe\host\test_analyzer.py `
  .\fixtures\simulated-capture.jsonl
```

## What a desktop pass means

Optional browser QA uses an existing Playwright installation:

```powershell
node .\tools\check-browser.mjs
```

Set `PLAYWRIGHT_MODULE` to an installed `index.mjs` when the module is outside the
normal Node search path. Set `EDGE_PATH` to an existing Edge executable when
using that browser. The script writes desktop screenshots and `.build/browser-results.json`;
it does not install a browser or access the device.

- C cores compile with warnings as errors and their ownership/capacity tests pass.
- CSI JSONL schema, timestamp ordering, self-motion labels and end counters agree.
- N1 ring IDs, read gaps, source changes and historical supported trend parameters are handled consistently.
- HTML works offline at desktop and mobile widths; no external requests are required.

## What needs real hardware

CSI byte layout, invalid-prefix interpretation, packet rate and stability; hotspot trend repeatability; camera/voice/network coexistence; battery power; scene detection and actual companion response. Track these as separate gates in the [roadmap](DEVELOPMENT_PLAN.md).
