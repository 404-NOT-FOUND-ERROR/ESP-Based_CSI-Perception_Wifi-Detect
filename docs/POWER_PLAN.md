# Power-Aware Sensing

目标：待机时减少无需求工作；互动开始时保持语音、表情和控制响应。以下是待测策略，不代表已经省下某个百分比。

## Operating states

| State | CSI | Camera | CPU / Wi-Fi intent |
| --- | --- | --- | --- |
| Chat, photo Q&A, comfort or motor control | Off | Only for an active vision task | Keep the measured performance required by the interaction |
| Docked idle | Off by default; optionally open a bounded attention window | Stop stream/inference when no owner needs frames | Reuse static display frames; retain the accepted wake path |
| Follow or walk | Off in the first version | Vision supplies identity/direction | Keep control and posture timing; N1 RSSI is supporting context |
| Explicit rest | Off | Off | Dimmest useful screen or screen off; consider sleep only with a tested wake source |

## CSI strategies to compare

1. **Invitation-time attention window, preferred first:** open a fixed-dock observation window shortly before an agreed invitation; once activity is confirmed, stop radio observation and hand off to the camera/voice experience.
2. **Periodic sampler, comparison only:** start with 6 s on / 24 s off (20% CSI uptime). Include settling, baseline rebuild and detection inside the six-second window. A short event entirely during the off interval can be missed.
3. **Continuous capture:** use only for brief labeled data collection and an explicitly measured demo; it is not the default idle policy.

After every CSI-off period, publish `unknown`. On resume verify source, channel, format and motion evidence, start a fresh run and rebuild the baseline. Compare detection latency and misses separately from the CSI-on percentage.

## Whole-device sequence

1. Reduce work that has no active owner: CSI driver and optional ping traffic, camera stream/inference, repeated UI refresh and diagnostic logs.
2. Measure the same interaction script as a baseline with the current always-ready Wi-Fi policy.
3. Test dynamic CPU frequency alone. Request performance during audio encoding/decoding, vision inference, full expression playback and active control; release it afterward. Verify the S31-supported frequency configuration and runtime lock behavior.
4. Test `WIFI_PS_MIN_MODEM` during docked idle as a separate change. Beacon/DTIM timing may delay voice, browser and CSI packet reception. Restore the low-latency mode before an attention window or interaction.
5. Combine only individually useful settings, then repeat coexistence and power measurements.

CPU frequency, Wi-Fi modem sleep and transmitter power affect different parts of the system; vary them independently. S31 light sleep/deep sleep are separate rest modes. A live voice session, USB connection or peripheral may keep parts of the system active; inspect actual runtime locks before promising sleep.

## Measurement protocol

- Use a USB power analyzer that records energy and peak current. Later repeat at the battery input. A multimeter voltage reading alone does not measure average power.
- Fix AP, signal level, screen brightness, volume, peripherals and script. Identify charge state, supply point and duration.
- Run each condition at least 10 minutes. Record Wh or mAh, peak current, startup/baseline cost, CSI packet rate, missed/false events and voice/camera/control behavior.
- Change one factor per comparison: CSI schedule, camera demand gating, CPU frequency, then Wi-Fi power-save. Keep a no-CSI baseline.
- Complete voice checks (wake and reply delay), screen/voice checks, phone reconnection and motor timing before accepting a power setting.

`CSI on-time / observation time` is the CSI duty fraction, not whole-device energy reduction. Report supply point and raw readings so future firmware revisions can be compared.

An empty [measurement template](../examples/power-measurements.csv) is provided. Fill results only after the corresponding run.
