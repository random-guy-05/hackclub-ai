# Homebrew Cask Distribution Design

**Date:** 2026-06-03

## Goal

Add a Homebrew-based install path for HackClub AI that installs the GitHub Release DMG, removes the quarantine attribute automatically, and launches the app automatically after install.

## Constraints

- The app is not signed or notarized.
- The distribution path must work from existing GitHub Releases artifacts.
- The install flow should minimize manual steps for end users.
- The workaround must stay explicit about being a workaround rather than trusted Apple distribution.

## Chosen Approach

Use a Homebrew cask that points at the GitHub Release DMG:

- `url` resolves to `https://github.com/random-guy-05/hackclub-ai/releases/download/v<version>/HackClub-AI.dmg`
- `app` installs `HackClub AI.app`
- `postflight` removes the quarantine attribute from the installed app
- `postflight` launches the installed app with `open`

The repo will also include a small generator script so the cask stays reproducible:

- read the release version from a single source of truth
- compute or accept the DMG SHA-256
- render the cask file into `Casks/hackclub-ai.rb`

## File Changes

- Add `VERSION` as the canonical app/release version
- Add `scripts/generate_homebrew_cask.py` to render the cask
- Add `Casks/hackclub-ai.rb` as the generated cask artifact
- Add tests for the generator output
- Update the macOS build script to read the shared version
- Update README install and release documentation

## Tradeoffs

- Auto-launch during `brew install` is intentionally aggressive UX
- Quarantine removal is a workaround, not a real trust chain
- The nicest `brew install --cask random-guy-05/tap/hackclub-ai` flow still requires publishing the same cask file in a separate `homebrew-tap` repo

## Verification

- Unit tests cover the cask renderer output
- The generator script produces a valid `Casks/hackclub-ai.rb`
- The README documents both direct cask install and tap publication workflow
