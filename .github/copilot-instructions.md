# Copilot instructions — Harvst Greenhouse integration

This repository is a **custom [Home Assistant](https://www.home-assistant.io/)
integration** (installable via [HACS](https://hacs.xyz)) for the **Harvst**
greenhouse watering control panel. Use these notes to stay productive and avoid
re-discovering things that were already worked out.

## What this integration does

Connects to a Harvst control panel over the **local network** (no cloud) and
exposes:

- Greenhouse temperature (wired probe) + rolling-average temperature sensors.
- Pump-running and per-zone watering binary sensors.
- Per-zone watering-duration `number` entities and per-zone "water now" buttons.
- A `harvst.water_zone` service to run a zone for N seconds.

The auxiliary outputs (**Aux 1/2/3**) and the panel's **WiFi setup** are
intentionally **out of scope** — do not add entities for them.

## Reverse-engineered panel API (the device has no documented API)

The panel is an ESP-based device. The integration was built by reverse
engineering the following endpoints — treat these as the source of truth:

- `GET /events` — **Server-Sent Events** stream. About once per second it emits
  `event: new_readings` with a JSON payload, e.g.
  `{"te":22,"teAve":14.66667,"ti":-13,"ta":-13,"h":-13,"cc":100,...}`.
  - `te` = wired temperature °C (`-13` means probe absent/disconnected).
  - `teAve` = rolling average temperature.
  - `cc` = pump current in mA (~`100` idle, strongly **negative** ~`-4000`
    while pumping).
  - `pump_state` = `0`/`1`, only present on transition readings.
  - The stream also emits keep-alive `data: hello!` / `data: ping` lines that
    must be ignored.
- `GET /control?device=pump&state=on&zone=<1|2>&time=<seconds>` — triggers
  watering for a zone. Returns `302` redirect to `/?updated=y` (the client uses
  `allow_redirects=False` and accepts `200` or `302`).
- `GET /control?do=clear<zone>` — clears the "last watered" state for a zone.
- `GET /settings` — HTML page containing `Device ID: <div>A84467B865E4</div>`,
  used to derive a stable unique id. Its "System information" table also holds
  diagnostic rows scraped by the coordinator on every poll:
  - `Pump back pressure` → e.g. `56 / 4712` (surfaced as the
    `pump_back_pressure` sensor: state = first number, `raw`/`reference`
    attributes for the full string and second number).
  - `Pump detection` → e.g. `Pump OK` (surfaced as the `pump_detection` sensor).
  The exact meaning of the two back-pressure numbers is not documented; we
  expose them faithfully rather than guessing. The settings scrape is
  best-effort — a failure logs at debug and keeps the previous values rather
  than failing the whole update (the SSE reading is the primary data).

**Watering detection:** prefer `pump_state` when present, otherwise treat
`cc < 0` as "pump running".

**Per-zone attribution limitation (important):** the panel only reports a single
pump state, not which zone is active. Per-zone watering binary sensors therefore
reflect zones **triggered through Home Assistant** (tracked in the coordinator
via `_active_zone` + a monotonic `_active_until`). Keep this behaviour and keep
it documented in the README. Don't claim true per-zone hardware feedback.

A real panel lives at `http://192.168.2.172/` on the author's network, but the
host is **configurable** via the config flow — never hard-code it in the
integration.

## Code layout & conventions

- Integration code: `custom_components/harvst/`
  - `client.py` — `HarvstClient` (async HTTP + SSE parsing). `HarvstError` /
    `HarvstConnectionError`.
  - `coordinator.py` — `HarvstCoordinator(DataUpdateCoordinator)`,
    `parse_reading()`, `HarvstData` dataclass, shared `zone_durations`,
    `async_water_zone`, `zone_is_watering`.
  - `__init__.py` — setup/unload, platform list, `water_zone` service.
  - `entity.py` — `HarvstEntity` base (DeviceInfo). Import `DeviceInfo` from
    `homeassistant.helpers.entity` (NOT `homeassistant.helpers.device_info`).
  - `sensor.py`, `binary_sensor.py`, `number.py`, `button.py`,
    `config_flow.py`, `const.py`, plus `manifest.json`, `services.yaml`,
    `strings.json`, `translations/en.json`.
- Tests: `tests/` (pytest + `pytest-homeassistant-custom-component`).
- HACS metadata: `hacs.json`; integration metadata: `manifest.json`.

## Testing — gotchas that cost time before

- Run tests with `pytest` after `pip install -r requirements_test.txt`. Current
  baseline: all tests pass (~91% coverage). CI runs Python 3.12 and 3.13.
- The HA test harness **blocks real sockets** and **fails on leftover threads**.
  - `tests/test_client.py` uses a hand-rolled fake session
    (`_FakeSession`/`_FakeResponse`/`_FakeContent`) — do NOT make real network
    calls or spawn threads in tests.
  - `tests/conftest.py` has a session-scoped autouse `_warmup_dns_resolver`
    fixture that pre-spawns the aiodns/`pycares` resolver thread before the
    harness snapshots threads. Newer `pycares` (>=4.5) starts a persistent
    daemon thread when an `AsyncResolver` is first constructed (which happens
    implicitly when any `aiohttp.ClientSession` is created, including mocked
    ones). Without the warm-up, `verify_cleanup` flags it as a leak and a test
    teardown errors out. **Keep this fixture.**
- Lint/format with `ruff check custom_components tests` and
  `ruff format custom_components tests`. Ruff config (`pyproject.toml`) uses
  isort with `force-sort-within-sections = true`, so import blocks get merged —
  let `ruff format` sort them.

## CI / release

- `.github/workflows/ci.yaml` — lint (ruff) → validate (`hassfest` + `hacs/action`)
  → tests (3.12 / 3.13). The HACS action sets `ignore: brands` because brand
  assets live in the separate `home-assistant/brands` repo, not here.
- `.github/workflows/release.yaml` — on **CI success on `main`** (or a
  `v*.*.*` tag push) it reads the version from `manifest.json`, and if a release
  for that tag does not already exist, zips `custom_components/harvst` into
  `harvst.zip` and publishes a GitHub release.
- **To cut a new release:** bump `version` in
  `custom_components/harvst/manifest.json` and merge to `main`. Pushing without
  bumping the version is safe — the release job detects the existing tag and
  skips.

## Brand icon (for future reference)

The integration/HACS logo cannot live in this repo. To add one, submit a PR to
[`home-assistant/brands`](https://github.com/home-assistant/brands) adding
`custom_integrations/harvst/icon.png` (256×256) and optional `logo.png`. Until
then HA shows a default icon — that's expected for custom components. Per-entity
mdi icons (`_attr_icon` / `icons.json`) *can* live here.

## House rules

- Keep `martinwoodward/haharvst` as the repo. `gh` is authenticated as
  `martinwoodward` (ssh).
- Never commit the local `.venv/` (already gitignored).
- Include the commit trailer
  `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>` on
  commits.
