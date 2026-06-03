#!/usr/bin/env python3
"""Generate the Homebrew cask for HackClub AI releases."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"
DEFAULT_DMG_PATH = ROOT / "dist" / "HackClub-AI.dmg"
DEFAULT_OUTPUT_PATH = ROOT / "Casks" / "hackclub-ai.rb"
RELEASE_URL_TEMPLATE = (
    "https://github.com/random-guy-05/hackclub-ai/releases/download/v#{version}/HackClub-AI.dmg"
)


def read_version_text(text: str) -> str:
    version = text.strip()
    if not version:
        raise ValueError("VERSION file is empty")
    return version


def read_version(path: Path = VERSION_FILE) -> str:
    return read_version_text(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_cask(version: str, sha256: str) -> str:
    return f"""cask "hackclub-ai" do
  version "{version}"
  sha256 "{sha256}"

  url "{RELEASE_URL_TEMPLATE}"
  name "HackClub AI"
  desc "Native macOS desktop chat client for the Hack Club AI proxy"
  homepage "https://github.com/random-guy-05/hackclub-ai"

  app "HackClub AI.app"

  postflight do
    system_command "/usr/bin/xattr",
                   args: ["-dr", "com.apple.quarantine", "#{{appdir}}/HackClub AI.app"]
    system_command "/usr/bin/open",
                   args: ["#{{appdir}}/HackClub AI.app"]
  end
end
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="Release version. Defaults to VERSION file.")
    parser.add_argument(
        "--sha256",
        help="DMG SHA-256. If omitted, it is computed from --dmg.",
    )
    parser.add_argument(
        "--dmg",
        type=Path,
        default=DEFAULT_DMG_PATH,
        help=f"Path to the DMG used for SHA-256 calculation. Defaults to {DEFAULT_DMG_PATH}.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output cask path. Defaults to {DEFAULT_OUTPUT_PATH}.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version = args.version or read_version()
    sha256 = args.sha256 or sha256_file(args.dmg)
    cask_text = render_cask(version, sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(cask_text, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
