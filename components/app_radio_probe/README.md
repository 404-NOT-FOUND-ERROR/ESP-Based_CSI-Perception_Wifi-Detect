# app_radio_probe

Hotspot observation recorder and provisional relative-signal trend. Pure C,
with no Wi-Fi calls, timers, tasks, motor commands, storage I/O or allocation.
It depends only on the public `app_network_link.h` observation contract.

## Ownership and use

The remote service allocates 48,092 bytes once in PSRAM (host: heap), initializes
the context with `app_radio_probe_init`, and frees it after its worker and HTTP
borrowers have stopped. Allocation failure disables the experiment while other
remote features continue. All functions run under that service's mutex. The
caller must supply storage aligned for ordinary C objects and keep it alive.

Start a run with an explicit fixed/carried phone role. Feed copied network
snapshots; duplicate read-attempt IDs do not create records. A mark describes
subsequent samples until changed or unpaired. Distances are human labels in
millimetres, 0 means unspecified, maximum 100,000 mm. Unpaired reads clear the
active label and distance. Stop freezes the data; a new start replaces the run.

The ring retains 1,200 observations, approximately 10 minutes at 2 Hz. Each
record carries ID, read-attempt ID/time, network generation, BSSID, channel,
RSSI, validity/error, FTM responder flag, label, distance, trend and paired state.
Overwrite and skipped read-attempt counts are explicit. Missing observations
are never interpolated. Run IDs isolate recordings; counter exhaustion stops
or rejects new admission rather than reusing a run/record identity.

## Trend contract

The provisional filter compares medians of the oldest/newest three values in
an eight-read window. A difference of at least 6 dB is strengthening/weakening;
within 2 dB is stable; the remaining band is unknown. Three consecutive matching
evaluations confirm a candidate. A changing candidate immediately becomes
unknown while evidence builds. These constants are exported with each run and
require real labelled validation before use by companion scenes.

AP, network generation or channel changes, invalid/stale reads, skipped IDs or
gaps over 1 second clear history. Reads older than 1.5 seconds are invalid.
The timestamps are local API-read times; age of the driver's original signal
measurement is unknown. Stable means the signal window changed little. There
is no distance conversion, user identity, direction or physical action output.

## Verification

`python tools/test.py --zig <zig-executable>` from this repository root compiles
and runs the recorder and CSI host tests, then validates new C-generated fixtures. `test_probe.c` covers noise,
sustained change, stale input, AP/session changes, missing samples, time wrap,
label loss, bounded overwrite and frozen export. RF performance and resource
coexistence require target installation and labelled field records.
