# Fabled Windows Installer

This folder contains the Windows Installer source for shipping Fabled as a
standard per-machine installation in `C:\Program Files\Fabled`.

## What it does

- Installs `Fabled.exe` to `C:\Program Files\Fabled`
- Registers the game in Apps & Features
- Uses a fixed `UpgradeCode`, so higher-version releases upgrade older installs
  instead of creating parallel copies
- Leaves player saves alone because those stay in
  `C:\Users\<user>\Saved Games\Fabled`

## Build requirements

- `Fabled.exe` in the repo root
- WiX Toolset CLI 6.x

## Build command

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\build-installer.ps1 -Version 1.0.0
```

To rebuild the game executable first:

```powershell
powershell -ExecutionPolicy Bypass -File .\installer\build-installer.ps1 -Version 1.0.0 -RebuildExe
```

The installer artifact is written to:

`.\installer\artifacts\Fabled-<version>-x64.msi`

## Upgrade behavior

- Keep the `UpgradeCode` in `Fabled.Installer.wxs` unchanged forever.
- Increase the installer version every release.
- Ship the new MSI.
- When a player runs the newer MSI over an older installed version, Windows
  upgrades the existing installation in place.

## Release checklist

1. Build and smoke-test `Fabled.exe`
2. Choose a new installer version such as `1.0.1`
3. Build the MSI
4. Test fresh install
5. Test upgrade from the previous MSI
6. Optionally sign both `Fabled.exe` and the MSI before distribution
