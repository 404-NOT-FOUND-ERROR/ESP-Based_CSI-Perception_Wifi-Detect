# Capture Formats

## N1 hotspot JSON

Schema: `airboat.hotspot-probe.v1`. Export one stopped run. The report checks run identity, contiguous record IDs, overwrite and missed-read counters, parameter agreement, source validity and wrapping read time.

Useful fields:

- `sample_seq`, `read_ms`, `network_generation`: sample identity and local API-read time.
- `valid`, `read_error`, `rssi_dbm`: reading and driver result.
- `bssid`, `channel`, `ftm_responder`: associated AP identity/capability evidence.
- `paired`, `label`, `distance_mm`: pairing and manual annotation. Distance is a human-entered reference, not an RSSI conversion.
- `trend_parameters`, `trend`: exact candidate filter settings and device-reported output.
- `meta.simulated`: keeps generated fixtures distinct from device records.

The offline tool replays only the known historical profile: 500 ms reads, 8-sample window, first/last median of 3, 6 dB trend threshold, 2 dB stable threshold, 3 confirmations and a 1,000 ms gap reset. An unknown profile stays inspectable but does not get silently replayed with these constants. Ring truncation and omitted stale duplicate ticks can prevent exact reconstruction.

## R1 CSI JSONL

One capture has one `airboat.csi.session.v1` manifest, ordered `airboat.csi.raw.v1` records and one final `airboat.csi.end.v1` counters record.

Raw frames preserve:

- callback-local microseconds and wrapping hardware RX timestamp;
- network generation, BSSID, channel, format, RX sequence and RSSI;
- full original payload bytes, requested mode and `first_word_invalid`;
- label, IMU/body epoch and motion eligibility evidence.

Final counters must reconcile exported, accepted, queued and discarded frames. Incomplete exports are rejected. First-word invalid bytes are preserved and marked; the analyzer does not assign carrier meaning before the real S31 layout is confirmed.

## Common rules

- A changed input during analysis is rejected. Reports include SHA-256 and byte size.
- Simulated and real records cannot be mixed inside a CSI capture.
- Independent captures keep independent timelines.
- CSI plot points may be downsampled; record totals and label intervals use all validated frames.
- Record formats are versioned. Add a new explicit adapter and tests when firmware changes its schema.
