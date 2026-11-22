# Sources and Packaging

## Fixed source delivery

The experiment was extracted from the AirBoat radio worktree at
`d99be2383cd7d3c1d67955c944b59121154585a3` on 2026-11-22. The source manifest lists
each imported file and its original SHA-256. Host tools and documentation were
adapted for this repository; embedded capture logic is retained.

- N1 source delivery: `9f81a8cf2a9133e9391e3035f09fdafe47527cc1`.
- R1 CSI source delivery: `076a77acfea9347029a2d8fe8840b45c254ce72b`.
- Offline replay: `9478f28a66188715a3e4933a61f8c7709f0eeefe`.
- Power design: `d99be2383cd7d3c1d67955c944b59121154585a3`.

These identify the experiment's history; the integrating application's current
commits, build settings and device acceptance are managed by its owner.

## SDK and research references

- [Espressif ESP-IDF](https://github.com/espressif/esp-idf/tree/7b9cc1ac79f865983f59bb8ff3ff43eb74ff1dbe): fixed local S31 SDK revision used in the source delivery, version macros 6.2.0.
- [Espressif esp-csi](https://github.com/espressif/esp-csi/tree/8633d67152db2808f141cc1595970aa9cf406045): router sampling workflow; adapt ownership and S31 configuration before integration.
- [esp-radar 0.3.4](https://components.espressif.com/components/espressif/esp-radar/versions/0.3.4): research snapshot depended on binaries without the required S31/IDF 6.2 pair.
- [ESPectre core-only SDK](https://github.com/francescopace/espectre/blob/3bacdb786a39e269e2f3b27ed7f4ae47a780ad83/docs/SDK.md#core-only): detector candidate after real layout and normalization are known. No ESPectre source is included here; evaluate its GPL-3.0-only licensing when selecting that implementation.

Research references describe the versions reviewed. A newly released upstream
version is a separate compatibility decision.

## Package changes

- Moved the public AP observation header into header-only `app_radio_contract`.
- Adjusted the N1 CMake dependency to that contract. An integrating app with an
  existing owner uses its own authoritative header/component.
- Replaced workspace-specific build scripts with `tools/test.py` and a thin
  PowerShell wrapper; source fixtures are regenerated only under `.build/`.
- Added bilingual entry documents, explicit stage gates, power measurements,
  self-contained example reports and CI for portable cores / Python checks.
- Normalized text to LF for reproducible Git checkouts; the manifest records
  original and packaged byte hashes separately.
- Preserved imported Apache-2.0 SPDX markers; retained the target repository's
  existing MIT license for documentation and new project glue.

## Included data

Both fixtures were generated from the real C recorders on a computer. They carry
synthetic identities and `simulated=true`. The report screenshot shows these same
fixtures. Their purpose is to reproduce transport, validation and replay checks.
