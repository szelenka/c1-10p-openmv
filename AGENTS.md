# Agent Instructions

## Hard Rules

- Treat `README.md` as the current project contract for deployment files, UART settings, pin mapping, serial frames, and host verification commands.
- Do not flash, copy files to an OpenMV board, open a serial/UART connection to hardware, or change the companion ESP32 repo unless the user explicitly asks.
- Do not run networked dependency or submodule commands without approval. `.gitmodules` references `Adafruit_MicroPython_LED_Animation`, but no gitlink is tracked in this checkout.
- Do not replace OpenMV APIs in `main.py` with CPython shims just to satisfy host tests. `main.py` is compiled on the host but runs on OpenMV firmware.
- Do not create commits, tags, branches, or pushes unless the user asks. Before any requested source-control action, run `git status --short` and keep unrelated user changes out of the action.

## Key Paths

- `main.py`: OpenMV boot entry point. It initializes camera, NeoPixels, UART3 at 115200 baud, serial command processing, face tracking, and the infinite runtime loop.
- `serial_processor.py`: ESP32/OpenMV serial framing, parser state machine, LED command handling, eye mirroring behavior, and `VISION_RESULT` frame encoding.
- `vision_filter.py`: face tracking smoothing, hold-time behavior, bad-box rejection, confidence values, and tuning constants.
- `test_serial_processor.py`: CPython `unittest` coverage for serial frames, parser behavior, LED state, tracking toggles, and known ESP32 frame examples.
- `test_vision_filter.py`: CPython `unittest` coverage for tracking smoothing, hold windows, jump rejection, reacquisition, and reset behavior.
- `README.md`: verification source for deployment files, hardware mapping, command IDs, packet format, and tuning guidance.

## Verification

Run the host test suite after changes to `serial_processor.py`, `vision_filter.py`, or either test file:

```bash
python3 -m unittest discover
```

Run syntax checks after any Python change, including `main.py`:

```bash
python3 -m py_compile main.py serial_processor.py vision_filter.py test_serial_processor.py test_vision_filter.py
```

There is no checked-in CI workflow, package manifest, linter config, or active git hook. Treat both commands above as the available local verification path.

## Change Rules

- If serial frame layout, command IDs, checksums, LED IDs, or `VISION_RESULT` fields change, update `serial_processor.py`, `test_serial_processor.py`, and the serial protocol tables or frame examples in `README.md` in the same change.
- If tracking behavior changes, update `vision_filter.py` and add or adjust `test_vision_filter.py` cases for at least one accepted detection, one rejected detection, and one missed-frame or timeout path affected by the change.
- If OpenMV hardware setup changes in `main.py`, update the deployment, pin, UART, or tracking notes in `README.md` when those user-visible facts change.
- Keep host tests independent of OpenMV hardware modules. Use fakes like `FakeUART`, `FakePixels`, and `FakePulse` rather than importing `main.py`.
- Search existing modules and tests before adding files. Extend the current root-level modules unless a new file has a distinct runtime role that the existing modules cannot own cleanly.

## Done-When Checklist

- Relevant tests or syntax checks above pass, or the final response names the exact command that could not be run and why.
- Protocol, pin, UART, deployment, and tuning documentation in `README.md` matches any changed runtime behavior.
- Host-side tests cover changed parser, frame builder, LED state, or tracking filter behavior with deterministic assertions.
- Hardware-only behavior is identified in the final response when it cannot be validated in this checkout.
- Any reusable repo convention discovered during the task is added here, and stale or non-actionable instructions are removed in the same change.
