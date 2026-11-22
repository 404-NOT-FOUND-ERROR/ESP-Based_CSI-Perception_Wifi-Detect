# app_csi_probe

R1 preparation package: bounded raw CSI capture, ESP32-S31 metadata adapter,
JSONL encoding and host quality replay. It publishes no activity event and has
no motor, audio, display, network setup or Wi-Fi lifecycle calls. Adding the
component leaves capture inactive until the existing network owner integrates it.

The [power policy design](POWER_POLICY.md) specifies bounded observation windows,
driver-level CSI shutdown, optional probe traffic, and separate CPU/Wi-Fi power
experiments. It is an integration plan; no runtime power behavior is added here.

## Responsibilities and dependencies

- `app_csi_probe.c`: caller-owned capture context, source/run filtering, motion
  evidence, a 32-frame queue and loss counters. No heap, tasks, I/O or SDK calls.
- `csi_s31.c`: prepare/compare the pinned SDK MAC-v3 configuration and copy
  `wifi_csi_info_t` metadata into the portable recorder. Depends on public Wi-Fi
  headers only. No callback registration or enable operation is performed here.
- `csi_json.c`: encode one copied frame into a caller-owned 2 KiB text buffer.
- `host/analyze_capture.py`: validate saved data, reconcile counts, and summarize
  source/layout groups, packet rate, gaps, labels and motion eligibility.

The host API `analyze(source, csv_path=None, visitor=None)` optionally calls
`visitor(row)` synchronously for each locally validated frame. The visitor borrows
the frame dictionary for that call and must not mutate it. Its exceptions propagate.
Final counters and file completeness are checked after the last frame; callers
publish visitor-derived results only after `analyze()` returns successfully.
The default return value and command-line interface are unchanged. An offline
HTML review tool is documented in `tools/radio_review/README.md` at the app root.

All implementation is application-owned Apache-2.0 code. No ESPectre/radar
algorithm or third-party binary is included. ESP-IDF types remain SDK-owned.

## Ownership, concurrency and storage

Allocate `app_csi_probe_storage_bytes()` bytes aligned for `max_align_t` once.
On the tested S31 ABI the context is **18,784 B**; each copied frame is 584 B.
The callback-visible context belongs in internal 8-bit RAM. The consuming task
keeps its frame and 2 KiB encoder buffers in its own persistent storage.

Every core operation tries one lock-free atomic flag once. Callback contention
drops that offered frame and increments a lock-free counter; there is no spin,
mutex, allocation, printing or waiting. Owner updates return false when busy
and are retried later by their task. `pop()` distinguishes busy/empty/frame.
The callback copies at most 512 bytes and rejects longer data without truncation.
An independently counted full queue drops the newest offered frame. Accepted
IDs remain ordered; IDs skipped for a full queue are visible in the next frame.
Counters are cumulative uint32 values for a short experiment; split sessions
before overflow. Run/record identity exhaustion closes admission.

The network owner remains responsible for callback ownership and lifetime. Stop
admission, disable CSI, detach/quiesce its callback, drain records and only then
release memory. The SDK documentation inspected here does not establish that
unregistering alone waits for all callbacks; retain the context until the Wi-Fi
owner has established quiescence, such as completed driver deinitialization.
No other task registers a CSI callback. A callback captures its run token at
entry; `offer()` rejects tokens from earlier runs. Queued records retain their
original run/generation. On begin, leftovers are explicitly counted discarded.
The owner closes a run on disconnect, AP/channel change or Wi-Fi reconfiguration;
it must settle the previous driver delivery before reopening admission.

## Capture and motion contract

`begin()` requires a nonzero network generation, unicast BSSID and channel. It
requires the previous run stopped and resets the manual label/motion context.
The callback preserves raw bytes, local 64-bit callback time, wrapping hardware
RX time, RX sequence, source/channel/format, RSSI/noise and invalid-prefix flag.
Local callback time is not represented as hardware measurement time.

`motion()` receives fresh evidence from the existing posture/command owners.
Eligibility requires a nonzero epoch, locked head, stationary body, no commanded
motion and age at most 250 ms. Future or missing evidence is ineligible. This
is an experimental data-quality gate, separate from the motor's deadlines.
All raw records are retained even while ineligible; the evidence itself is
exported. Label 0 unknown, 1 quiet, 2 user walking, 3 self movement, 4 occluded.
The caller clears labels when the annotating phone disconnects. A new physical
motion episode uses a new epoch; later detectors rebuild their background.

S31 configuration explicitly requests force-LLTF and 8-bit components. Verify
`esp_wifi_get_csi_config()` against `app_csi_s31_config_matches()` before admitting
records. Actual carrier layout is still unverified: exports preserve this fact,
the entire original payload and `first_word_invalid`. No padding, carrier map,
IQ conversion, distance or direction is inferred. Once the real layout is known,
exclude the first four bytes when flagged and use only validated carriers.

## File and transport contract

A saved capture has exactly one `airboat.csi.session.v1` manifest, ordered
`airboat.csi.raw.v1` frames, and a final `airboat.csi.end.v1` counter record. The
manifest supplies capture/boot identity, real/simulated provenance, target, SDK,
requested configuration and export transport. Counters cover the same capture
interval: subtract a start snapshot when reusing an existing context. Exported
frames + queued + discarded must equal accepted. Save the final counters even
when a test is stopped early; the analyzer rejects incomplete exports.

The encoder returns zero for insufficient capacity. It belongs to a low-priority
export task, outside callbacks and control loops. The measured encoder stack is
208 B before libc callees, versus 48 B for the S31 adapter and 32 B for `offer()`;
budget at least 4 KiB for the exporter task and measure its runtime watermark.
Its output can exceed the existing remote protocol's 1 KiB response buffer.
Mainline must add authenticated chunk/stream transport with backpressure; do not
insert a full JSON record into that response buffer or print frames on live
control/voice tasks. No phone route or active ping generator is wired in this
package. A 32-frame ingress queue buffers approximately 1.6 s at 20 pps; sustained
capture requires ongoing drainage, with transport loss separately counted.

## Minimal caller sequence

1. The network owner verifies a connected, fixed source and holds the context.
2. Prepare/set/read back the S31 config; capture stays default off.
3. Begin a run, publish fresh posture context and a manual label.
4. The sole CSI callback calls `app_csi_s31_offer()` with its captured run token.
5. A consumer pops frames and passes the copied frame to an export worker.
6. Stop admission on source changes/stop; disable delivery, drain and close the file.

The integration implementation must serialize lifecycle changes and test in-flight
callbacks. This package provides the core/adapter seams; it does not change the
current application, sdkconfig, network owner or firmware version.

## Verification

From this repository root:

```powershell
python tools/test.py
python tools/test.py --zig "C:\tools\zig\zig.exe"
```

The first command runs offline Python checks on the included fixtures. The second
also builds the real C capture cores, adapter boundary tests, N1 recorder and
fixture exporters. The Windows run adds 20,000 concurrent offers with exact
accounting; Linux CI runs the portable cores and all Python checks.

The source delivery previously compiled three translation units against fixed
ESP32-S31 headers; that check is distinct from this host boundary double and from
full application link, runtime packet format, power and hardware acceptance.
See [testing](../../docs/TESTING.md), [source provenance](../../docs/SOURCES.md)
and [roadmap](../../docs/DEVELOPMENT_PLAN.md).
