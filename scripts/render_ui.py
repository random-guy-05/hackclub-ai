#!/usr/bin/env python3
"""Render the app window's content view to a PNG (offscreen) for visual inspection."""
import os
import sys

import AppKit
from AppKit import NSBitmapImageRep, NSPNGFileType

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hackclub_app
from hackclub_ai import Shell, UiBlock


def main():
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
    shell = Shell()
    ui = hackclub_app.MacChatUI.alloc().initWithShell_(shell)
    shell.ui_delegate = ui

    # fake sidebar sessions
    import time
    def fake(title, hist, ago):
        return {"id": title[:6], "title": title, "history": hist, "updated_at": time.time() - ago}
    sessions = [
        fake("Refactor the auth module", ["q"] * 8, 300),
        fake("Explain async generators in Python", ["q"] * 4, 5400),
        fake("Build a CLI todo app", ["q"] * 12, 90000),
    ]
    hackclub_app.list_saved_sessions = lambda: sessions

    shell.show_welcome()
    if not os.environ.get("WELCOME"):
        with shell._frag_lock:
            shell.blocks.append(UiBlock("user", "How do I read a file in Python?"))
            shell.blocks.append(UiBlock("asst", ""))
            shell.blocks.append(UiBlock("think", "The user wants the idiomatic way to read a file. I'll show `open()` with a context manager, mention reading the whole file vs. line-by-line for large files, and keep it tight."))
            shell.blocks.append(UiBlock("md", "You can use the built-in `open()`:\n\n```python\nwith open('file.txt') as f:\n    data = f.read()\n```\n\nThis reads the **whole file** into memory. For large files, iterate line by line."))
            shell.blocks.append(UiBlock("user", "And how do I write one?"))
            shell.blocks.append(UiBlock("asst", ""))
            shell.blocks.append(UiBlock("think_live", "Writing is symmetric — open in write mode and use the context manager so the handle closes automatically. I should warn that `'w'` truncates."))
            shell.blocks.append(UiBlock("spin", "▆  Writing · ·", "class:spin"))
    ui._last_render_ver = -1
    ui.refreshAll()

    win = ui.window
    win.setFrame_display_(((100, 100), (1280, 860)), True)
    root = win.contentView()
    root.layoutSubtreeIfNeeded()
    root.displayIfNeeded()

    rect = root.bounds()
    rep = root.bitmapImageRepForCachingDisplayInRect_(rect)
    root.cacheDisplayInRect_toBitmapImageRep_(rect, rep)
    data = rep.representationUsingType_properties_(NSPNGFileType, None)
    out = "/tmp/hc_render.png"
    data.writeToFile_atomically_(out, True)
    print("wrote", out, int(rect.size.width), int(rect.size.height))


if __name__ == "__main__":
    main()
