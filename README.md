# X515 Env Spoofer

Environment and browser fingerprint suite emulating a fixed hardware
profile: ASUS X515EA-BQ950 (Intel i3-1115G4, Intel UHD Graphics, 12 GB,
1920x1080). Built on Playwright (CDP) with a runtime JavaScript patch
layer. Designed for privacy testing, QA of fingerprint-dependent web
applications, and research on browser fingerprinting techniques.

## What it does

- Persistent per-profile hardware fingerprint (currently ASUS X515EA):
  `navigator.hardwareConcurrency`, `navigator.deviceMemory`, WebGL
  UNMASKED_VENDOR / UNMASKED_RENDERER strings, screen geometry, locale,
  timezone.
- Deterministic, seed-driven output noise for `Canvas.toDataURL`,
  `CanvasRenderingContext2D.getImageData`, and WebGL parameter reads,
  so canvas / WebGL fingerprints are stable within one identity and
  change with a new one.
- Automation-surface masking: `navigator.webdriver` (prototype and
  instance), plugins array, `window.chrome` shape, Notification /
  Permissions consistency, client-hint user agent data.
- Isolated chromium launches via Playwright persistent context, either
  with a per-profile user-data dir or a throwaway temp one (wiped on
  close).
- System cleanup helper: removes cookies, Local Storage, Session
  Storage, IndexedDB and HTTP caches across Chrome / Edge / Firefox,
  flushes DNS, prunes old `%TEMP%` files.

## Setup

Requires Python 3.10+.

```
python -m pip install colorama playwright patchright
python -m playwright install chromium
```

The launcher prefers the patchright engine (CDP protocol-level stealth,
required for Google sign-in flows) and falls back to playwright.

## Run

```
python chess_env_spoofer.py
```

## Build a single executable

```
python -m pip install pyinstaller
pyinstaller --onefile --noconsole --collect-all playwright --collect-all patchright --name X515EnvSpoofer chess_env_spoofer.py
```

Result: `dist\X515EnvSpoofer.exe`. The exe self-attaches a console, so
`--noconsole` does not break the interactive menu.

## Isolation model

- persistent mode: `profiles/<name>/chrome-data` user-data dir kept per
  identity; never touches the host browser's profile.
- fresh mode: temp user-data dir, removed on close.
- autopilot: terminates host browsers, runs the cleanup, re-rolls the
  identity seeds, then launches fresh.

## Files layout

| path | purpose |
|------|---------|
| `profiles/<name>/fingerprint.json` | persisted identity and noise seeds |
| `profiles/<name>/config.json` | proxy settings |
| `profiles/<name>/chrome-data/` | isolated chromium user data dir |
| `state.json` | tool-level state (last used profile, purge targets) |
| `spoofer.log` | action log |

## Notes

- TLS: the underlying Chromium / BoringSSL stack produces genuine
  Chrome JA3 / JA4 signatures on its own; no extra work is done at this
  layer.
- Timezone, language, and proxy should match each other for a coherent
  identity.
- To adapt the suite to different hardware profiles, edit the
  `HARDWARE`, `WEBGL`, `SCREEN`, and `IDENTITY` dictionaries in
  `chess_env_spoofer.py` and generate a fresh profile.

## Development

Run tests with:

```
python smoke_test.py
```

## License

MIT. See `LICENSE`.
