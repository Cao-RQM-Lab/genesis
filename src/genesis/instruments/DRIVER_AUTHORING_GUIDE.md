# Genesis Instrument Driver Authoring Guide

This document explains how to write a functional instrument driver in Genesis with no prior project context.

It is based on current working drivers:
- `src/genesis/instruments/b29xx/driver.py`
- `src/genesis/instruments/sr850/driver.py`

## 1) File and Module Layout

Create a folder under `src/genesis/instruments/`:

- `src/genesis/instruments/<instrument_key>/driver.py`

Example:
- `src/genesis/instruments/my_device/driver.py`

Genesis discovers this automatically via `loadBuiltInInstruments()` in:
- `src/genesis/core/instrument/discovery.py`

Your module must export:
- `registerInstruments(registry)`

## 2) Required APIs to Implement

Your class must extend `BaseInstrument` from:
- `src/genesis/core/instrument/base_instrument.py`

Implement/override:

1. `initialize(self) -> None`
   - Apply configured state without full reset commands unless explicitly needed.

2. `applySafeState(self) -> None`
   - Drive instrument to safe state from `metadata["safeConfig"]` (fallback to job config if needed).

3. `applyConfigValue(self, key: str, value: float | int | str) -> None`
   - Translate one logical config key into one or more transport commands.

4. `readMeasurements(self, signalKeys: list[str]) -> dict[str, float]`
   - Return only requested signals, parsed as floats.

Recommended class methods:

5. `getJobConfigFields(cls) -> list[ConfigFieldDefinition]`
   - Define UI + serialization config schema.

6. `getAvailableMeasurementSignals(cls) -> list[tuple[str, str]]`
   - Define user-selectable measured signals.

7. `getDefaultAddress(cls) -> str`
   - Return factory default VISA resource when known.

8. `getSupportedTransportKeys(cls) -> list[str]`
   - Usually `["visa"]` unless intentionally supporting others.

## 3) Naming Conventions

Follow these conventions to match current code:

- `INSTRUMENT_TYPE_KEY`: short lowercase key, e.g. `"b29xx"`, `"sr850"`.
- Driver class: `PascalCase`, e.g. `B29xxInstrument`.
- Folder name should match instrument key.
- Config keys:
  - descriptive + unit suffix when numeric (e.g. `referenceFrequencyHz`, `forceVoltageLevelV`).
  - enums use `...Index` when the instrument expects integer selectors.
- Measurement keys:
  - stable short keys used in job JSON and plotting (`x`, `y`, `r`, `theta`, `senseVoltageV`).

## 4) Config Schema: What to Include from the Manual

Use `ConfigFieldDefinition` (`src/genesis/core/instrument/config_field.py`) for each user-exposed parameter.

Field properties you should set carefully:
- `key`, `label`, `fieldType`, `default`
- `minValue`, `maxValue`, `stepValue` for numeric fields
- `choices` for enums (`ConfigChoice`)
- `helpText` with command mapping and key constraints
- `sweepable=True` only for safe/meaningful dynamic setpoints

### Parameter selection strategy

Include parameters that are:
1. Frequently needed for normal operation.
2. Stable to change at runtime.
3. Supported in remote mode with deterministic command mapping.

Avoid exposing:
1. Rare service/diagnostic/internal calibration controls.
2. Mode/commands that require complex preconditions unless implemented robustly.
3. Parameters known to vary by firmware unless guarded.

## 5) Defaults: How to Choose from Manual

Default values should come from the instrument manual, in this order:
1. Factory defaults from command reference.
2. If factory default is unsafe/unhelpful, choose conservative lab-safe defaults and document why.
3. Ensure defaults are valid under other defaults (e.g. mode-dependent values).

Always document source rationale in a nearby comment or `helpText`.

Examples already in code:
- B29xx default GPIB address `23`
- SR850 default GPIB address `8`

## 6) Determining `sweepable`

Mark a parameter `sweepable=True` only if all are true:
1. It represents a physical setpoint intended to vary point-to-point.
2. Runtime changes are supported and safe for repeated command updates.
3. Its command path is deterministic in `applyConfigValue`.
4. It is meaningful as an axis in job sweeps/plots.

Typical sweepable examples:
- SMU forced level (V or A)
- Lock-in reference frequency / amplitude / phase

Typical non-sweepable examples:
- Static wiring/config modes
- Auto-range toggles
- Deep filter/config indices unless explicitly desired

## 7) Safety and Runtime Behavior Requirements

Genesis now provides centralized setpoint safety in:
- `src/genesis/core/runtime/setpoint_safety.py`

Important implications:
- Drivers should expose accurate numeric bounds in `ConfigFieldDefinition` (`minValue`, `maxValue`).
- Runtime safety uses those bounds for clamping and slew-limited stepping.
- Keep `applyConfigValue` deterministic and idempotent; do not hide extra asynchronous behavior.

Slew behavior is orchestrated outside drivers (device-agnostic), so new drivers do not need custom slew code.

## 8) `applyConfigValue` Implementation Pattern

Use a clear key-dispatch structure:

1. Persist incoming value into `self.jobConfig[key]`.
2. Derive dependent mode/channel state from `self.jobConfig`.
3. For each supported key:
   - validate/normalize if needed,
   - emit command(s),
   - return.
4. Ignore unknown keys safely (or raise if appropriate).

Keep formatting helpers (`_fmtFloat`) for consistent command strings.

## 9) Measurement Read Pattern

Recommended:
- Map signal keys to query commands or SNAP indices.
- Read only requested keys.
- Parse robustly (strip, split commas if needed).
- Return `dict[str, float]` with only successful values.

## 10) Registration Boilerplate

Each `driver.py` should include:

1. Factory function:
- builds instrument with `name`, `transport`, `metadata`, `jobConfig`.

2. Registration function:
- `registerInstruments(registry)` calling `registry.registerInstrument(...)`.

Minimal template:

```python
INSTRUMENT_TYPE_KEY = "mydevice"

class MyDeviceInstrument(BaseInstrument):
    ...

def _myDeviceFactory(name, transport, metadata=None, jobConfig=None):
    return MyDeviceInstrument(
        name=name,
        transport=transport,
        metadata=metadata,
        jobConfig=jobConfig,
    )

def registerInstruments(registry: InstrumentRegistry) -> None:
    registry.registerInstrument(
        key=INSTRUMENT_TYPE_KEY,
        instrumentType=MyDeviceInstrument,
        factory=_myDeviceFactory,
    )
```

## 11) Practical Manual-to-Driver Workflow

1. Read manual sections:
   - command summary,
   - parameter ranges,
   - defaults,
   - remote command syntax examples.
2. Draft `getJobConfigFields` with explicit bounds/defaults/choices.
3. Implement `applyConfigValue` key-by-key with exact command mapping.
4. Implement `readMeasurements` for selected signals.
5. Implement `initialize` and `applySafeState`.
6. Register driver and run app.
7. Validate with real hardware or dummy transport first, then hardware.

## 12) Validation Checklist Before Merge

- Driver discovered by registry automatically.
- Config fields render correctly in Job Builder.
- Defaults load and initialize without errors.
- Each config key maps to expected command.
- Measurement reads parse correctly.
- Sweepable fields change correctly during sweeps.
- Stop/abort and safe-state behavior works as expected.
- No reset-heavy side effects in normal initialize path.

## 13) Documentation Sync Requirement

When critical functionality changes are implemented in Genesis (especially runtime safety, sweep orchestration, plotting behavior, or driver contract expectations), documentation must be updated in the same work:

- `README.md` for user-facing workflow/behavior changes.
- `src/genesis/instruments/DRIVER_AUTHORING_GUIDE.md` for driver-facing requirements and patterns.

For agent-to-agent context handoff summaries, explicitly include:
- whether these documents were updated,
- what sections changed,
- and any remaining doc follow-up items.
