# Radio Lab collaboration

Read `docs/DEVELOPMENT_PLAN.md`, `docs/ARCHITECTURE.md` and `docs/POWER_PLAN.md`
before extending this experiment. Keep raw capture provenance, schema versions,
source hashes, input ownership and fixed SDK requirements explicit.

- This is an experimental component/tool repository. The owning application
  controls its firmware version, Wi-Fi lifecycle, integration and device window.
- Keep simulated fixtures labeled. Distinguish desktop checks, target compilation,
  runtime identity, RF tests and human acceptance.
- CSI defaults off. A power design is not measured savings. Preserve control and
  sensor freshness contracts when adding scheduling or power modes.
- Preserve file SPDX notices and the repository's MIT / Apache-2.0 boundaries.
- Put local recordings in `data/local/`; publish only intentionally selected,
  reviewed captures. Raw capture identity and AP identifiers belong in that review.
- Explain purposes and concrete steps in concise Chinese, with technical details
  in the engineering sections. Update both README languages together.
- Run `python tools/test.py` for Python checks, and `python tools/test.py --cc
  <compiler>` or `--zig <path>` for C core checks. Run `python tools/verify_package.py`
  and `git diff --check` before committing.
- Use Clash `http://127.0.0.1:7897` for GitHub/network operations in this workspace;
  do not change the machine's global proxy settings.
