# Validation Record

Updated: 2026-11-22

## Desktop package

- N1 and CSI C cores compiled with Zig and warnings treated as errors.
- Windows CSI queue accounting passed 20,000 concurrent offer attempts.
- C-generated N1 and CSI fixtures passed the offline analyzers.
- CSI analyzer: 11 tests passed. Offline review: 23 tests passed.
- Package check: local links, 29 imported-file hashes, 2 fixture hashes,
  embedded report data and 4 planned power-measurement rows passed.
- Browser check: 8 groups passed at desktop and 390 px widths; no JavaScript
  errors or external requests.

All capture files in this repository are synthetic and marked
`simulated=true`. These checks validate code, file handling and presentation.
They do not measure a real hotspot, CSI radio payload, activity detector,
device power, or integrated Mosaico behavior.

## Next evidence gate

Stage 1 in the [development plan](DEVELOPMENT_PLAN.zh-CN.md) is the next step:
the integrating application owner selects a fixed firmware source snapshot,
agrees on the export schema and authentication boundary, and provides a short
device window. Record the firmware commit, SDK, board identity, power source,
run ID, packet counters and original-file hashes before starting N1 or CSI
field collection.

Desktop verification is separate from target compilation, installation,
runtime identity, RF measurement and human acceptance. The [power plan](POWER_PLAN.md)
requires whole-device measurements before any energy-saving claim.
