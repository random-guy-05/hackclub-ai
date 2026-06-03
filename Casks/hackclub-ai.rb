cask "hackclub-ai" do
  version "1.1.0"
  sha256 "a80846dac00b0c65defa2e2d70ae445594e225157cf48579f9105243f8cbe46d"

  url "https://github.com/random-guy-05/hackclub-ai/releases/download/v#{version}/HackClub-AI.dmg"
  name "HackClub AI"
  desc "Native macOS desktop chat client for the Hack Club AI proxy"
  homepage "https://github.com/random-guy-05/hackclub-ai"

  app "HackClub AI.app"

  postflight do
    system_command "/usr/bin/xattr",
                   args: ["-dr", "com.apple.quarantine", "#{appdir}/HackClub AI.app"]
    system_command "/usr/bin/open",
                   args: ["#{appdir}/HackClub AI.app"]
  end
end
