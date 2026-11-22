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

## First real N1 export

The [first device export review](FIELD_NOTES/2026-11-22-n1-run6.md) confirms 170
valid observations over 88.207 seconds, no missed or overwritten reads, and
zero historical replay mismatches. All observations are unmarked, so movement
classification is pending. The raw capture stays local; the public field note
contains aggregate results and its SHA-256.

Repository fixtures remain synthetic and marked `simulated=true`. Real CSI,
labeled movement detection, integrated coexistence and power measurements
have their own acceptance gates.

## Next evidence gate

The next N1 step is [labeled movement collection](N1_NEXT_CAPTURE.zh-CN.md).
For CSI, stage 1 in the [development plan](DEVELOPMENT_PLAN.zh-CN.md) still
requires a fixed runtime/export contract from the integrating application.
Record firmware/SDK, power source, run ID, packet counters and original-file
hashes for every device window.

Desktop verification is separate from target compilation, installation,
runtime identity, RF measurement and human acceptance. The [power plan](POWER_PLAN.md)
requires whole-device measurements before any energy-saving claim.
