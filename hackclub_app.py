#!/usr/bin/env python3
"""HackClub AI — native macOS desktop application."""

from __future__ import annotations

import os
import re
import sys
import threading
import warnings

import AppKit
import objc

warnings.filterwarnings("ignore", category=objc.ObjCPointerWarning)
from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSApplication,
    NSAttributedString,
    NSBackingStoreBuffered,
    NSBox,
    NSButton,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSLayoutAttributeBottom,
    NSLayoutAttributeCenterX,
    NSLayoutAttributeCenterY,
    NSLayoutAttributeHeight,
    NSLayoutAttributeLeading,
    NSLayoutAttributeNotAnAttribute,
    NSLayoutAttributeTop,
    NSLayoutAttributeTrailing,
    NSLayoutAttributeWidth,
    NSLayoutConstraint,
    NSLayoutRelationEqual,
    NSLayoutRelationLessThanOrEqual,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSPopUpButton,
    NSSearchField,
    NSScrollView,
    NSSecureTextField,
    NSBezierPath,
    NSStackView,
    NSTableColumn,
    NSTableRowView,
    NSTableView,
    NSTextField,
    NSTextView,
    NSView,
    NSVisualEffectView,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskFullSizeContentView,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSMakeRange, NSObject
from PyObjCTools import AppHelper

from hackclub_ai import (
    BANNER,
    CMD_DESCRIPTIONS,
    COMMANDS,
    MODELS,
    Shell,
    delete_all_sessions,
    format_session_line,
    list_saved_sessions,
    session_epoch,
    load_api_key,
    load_composio_key,
    md_to_fragments,
    normalize_input,
    normalize_reasoning_for_model,
    parse_cli_args,
    parse_model_command,
    pick_macos_path,
    pick_saved_session,
    reasoning_variants_for_model,
    rename_saved_session,
    save_api_key,
    save_composio_key,
    session_display_title,
    session_title_from_history,
)

APP_NAME = "HackClub AI"
SIDEBAR_W = 288
TOPBAR_H = 60
COMPOSER_H = 132
CHAT_PAD = 32
BUBBLE_MAX = 620

SUGGESTIONS = [
    ("Explain a codebase", "/explain How does this project work?"),
    ("Debug an issue", "/debug Help me find and fix a bug"),
    ("Build something", "/build Implement a small feature end-to-end"),
    ("Quick answer", "/quick Give me a concise answer about Python asyncio"),
]

# Premium design tokens — Hack Club warm accent on refined neutrals
THEME = {
    "dark": {
        "window": (0.102, 0.106, 0.118),
        "canvas": (0.125, 0.130, 0.145),
        "surface": (0.165, 0.172, 0.192),
        "elevated": (0.205, 0.214, 0.239),
        "composer": (0.157, 0.164, 0.184),
        "composer_border": (0.275, 0.287, 0.322),
        "border": (0.235, 0.247, 0.278),
        "text": (0.957, 0.965, 0.980),
        "text_secondary": (0.690, 0.714, 0.757),
        "text_muted": (0.490, 0.514, 0.561),
        "accent": (0.961, 0.435, 0.227),
        "accent_text": (1.0, 1.0, 1.0),
        "accent_soft": (0.961, 0.435, 0.227),
        "user_label": (0.451, 0.678, 1.0),
        "user_text": (0.945, 0.957, 0.980),
        "assistant_label": (0.961, 0.471, 0.275),
        "success": (0.388, 0.851, 0.588),
        "warning": (0.984, 0.776, 0.380),
        "error": (0.969, 0.451, 0.451),
        "code_bg": (0.082, 0.086, 0.098),
        "code_text": (0.851, 0.871, 0.910),
        "pill_bg": (0.196, 0.204, 0.227),
        "palette_bg": (0.149, 0.156, 0.176),
        "palette_border": (0.275, 0.287, 0.322),
        "sidebar": (0.114, 0.118, 0.133),
        "sidebar_border": (0.196, 0.204, 0.227),
        "user_bubble": (0.196, 0.314, 0.604),
        "user_bubble_text": (0.980, 0.984, 1.0),
        "asst_bubble": (0.165, 0.172, 0.192),
        "asst_bubble_border": (0.235, 0.247, 0.278),
        "system_pill": (0.196, 0.204, 0.227),
    },
    "light": {
        "window": (0.945, 0.949, 0.957),
        "canvas": (0.976, 0.980, 0.988),
        "surface": (1.0, 1.0, 1.0),
        "elevated": (0.965, 0.969, 0.976),
        "composer": (1.0, 1.0, 1.0),
        "composer_border": (0.851, 0.863, 0.890),
        "border": (0.878, 0.890, 0.914),
        "text": (0.114, 0.122, 0.149),
        "text_secondary": (0.388, 0.408, 0.451),
        "text_muted": (0.557, 0.580, 0.620),
        "accent": (0.918, 0.357, 0.106),
        "accent_text": (1.0, 1.0, 1.0),
        "accent_soft": (0.918, 0.357, 0.106),
        "user_label": (0.0, 0.420, 0.851),
        "user_text": (0.122, 0.137, 0.180),
        "assistant_label": (0.886, 0.349, 0.114),
        "success": (0.118, 0.580, 0.322),
        "warning": (0.718, 0.478, 0.0),
        "error": (0.820, 0.180, 0.180),
        "code_bg": (0.949, 0.953, 0.965),
        "code_text": (0.176, 0.196, 0.235),
        "pill_bg": (0.929, 0.937, 0.949),
        "palette_bg": (1.0, 1.0, 1.0),
        "palette_border": (0.851, 0.863, 0.890),
        "sidebar": (0.949, 0.953, 0.965),
        "sidebar_border": (0.878, 0.890, 0.914),
        "user_bubble": (0.0, 0.420, 0.863),
        "user_bubble_text": (1.0, 1.0, 1.0),
        "asst_bubble": (1.0, 1.0, 1.0),
        "asst_bubble_border": (0.878, 0.890, 0.914),
        "system_pill": (0.929, 0.937, 0.949),
    },
}

STYLE_MAP = {
    "class:text": "text",
    "class:dim": "text_muted",
    "class:label": "text",
    "class:user_label": "user_label",
    "class:user_msg": "user_text",
    "class:asst_label": "assistant_label",
    "class:sep": "border",
    "class:attach": "accent",
    "class:ok": "success",
    "class:warn": "warning",
    "class:error": "error",
    "class:think": "text_muted",
    "class:think_label": "accent",
    "class:spin": "accent",
    "class:md_strong": "text",
    "class:md_em": "text_secondary",
    "class:code": "code_text",
    "class:status": "text_muted",
}


def rgb_color(rgb, alpha=1.0):
    return NSColor.colorWithRed_green_blue_alpha_(rgb[0], rgb[1], rgb[2], alpha)


def theme_color(theme, key, alpha=1.0):
    val = theme[key]
    if isinstance(val, str):
        val = theme[val]
    return rgb_color(val, alpha)


def _icon_path():
    bundle = AppKit.NSBundle.mainBundle()
    if bundle is not None:
        for name in ("AppIcon", "appicon"):
            path = bundle.pathForResource_ofType_(name, "icns")
            if path:
                return path
        resources = bundle.resourcePath()
        if resources:
            candidate = os.path.join(resources, "AppIcon.icns")
            if os.path.isfile(candidate):
                return candidate
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.path.join(here, "AppIcon.icns"), os.path.join(here, "..", "assets", "AppIcon.icns")):
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


def setup_app_branding(app):
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
    path = _icon_path()
    if path:
        img = AppKit.NSImage.alloc().initWithContentsOfFile_(path)
        if img is not None:
            app.setApplicationIconImage_(img)
    try:
        AppKit.NSProcessInfo.processInfo().setProcessName_(APP_NAME)
    except Exception:
        pass


def make_label(text, size=12, weight=0, color=None, mono=False):
    if mono:
        font = NSFont.monospacedSystemFontOfSize_weight_(size, weight)
    else:
        font = NSFont.systemFontOfSize_weight_(size, weight)
    field = NSTextField.labelWithString_(text)
    field.setFont_(font)
    if color is not None:
        field.setTextColor_(color)
    field.setTranslatesAutoresizingMaskIntoConstraints_(False)
    return field


def make_pill_button(controller, title, action, accent=False, compact=False, fixed_width=True):
    size = 12.5 if compact else 13.5
    weight = AppKit.NSFontWeightSemibold if accent else AppKit.NSFontWeightMedium
    font = NSFont.systemFontOfSize_weight_(size, weight)
    h = 28 if compact else 34
    pad = 18 if compact else 24
    text_w = NSAttributedString.alloc().initWithString_attributes_(
        title, {NSFontAttributeName: font}).size().width
    w = int(text_w) + 2 * pad

    btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
    btn.setTitle_(title)
    btn.setBezelStyle_(AppKit.NSBezelStyleRounded)
    btn.setBordered_(not accent)
    btn.setFont_(font)
    btn.setTarget_(controller)
    btn.setAction_(action)
    btn.setTranslatesAutoresizingMaskIntoConstraints_(False)
    btn.setWantsLayer_(True)
    if accent:
        btn.layer().setCornerRadius_(h / 2.0)
    cons = [NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(btn, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, h)]
    if fixed_width:
        cons.append(NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(btn, NSLayoutAttributeWidth, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, w))
    NSLayoutConstraint.activateConstraints_(cons)
    return btn


def make_suggestion_card(controller, label, action, theme):
    btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 480, 50))
    btn.setTitle_("   " + label)
    btn.setAlignment_(AppKit.NSTextAlignmentLeft)
    btn.setBezelStyle_(AppKit.NSBezelStyleRegularSquare)
    btn.setBordered_(False)
    btn.setFont_(NSFont.systemFontOfSize_weight_(14, AppKit.NSFontWeightMedium))
    btn.setTarget_(controller)
    btn.setAction_(action)
    btn.setWantsLayer_(True)
    btn.layer().setCornerRadius_(12.0)
    btn.layer().setBackgroundColor_(rgb_color(theme["surface"]).CGColor())
    btn.layer().setBorderColor_(rgb_color(theme["border"]).CGColor())
    btn.layer().setBorderWidth_(1.0)
    btn.setContentTintColor_(rgb_color(theme["text"]))
    btn.setTranslatesAutoresizingMaskIntoConstraints_(False)
    return btn


def style_suggestion_card(btn, theme):
    btn.layer().setBackgroundColor_(rgb_color(theme["surface"]).CGColor())
    btn.layer().setBorderColor_(rgb_color(theme["border"]).CGColor())
    btn.setContentTintColor_(rgb_color(theme["text"]))


def style_pill_button(btn, theme, accent=False, enabled=True):
    btn.setEnabled_(enabled)
    btn.setBordered_(False)
    h = btn.frame().size.height
    if h <= 0:
        h = 34
    btn.layer().setCornerRadius_(h / 2.0)
    if accent:
        bg = theme["accent"] if enabled else theme["elevated"]
        btn.layer().setBackgroundColor_(rgb_color(bg).CGColor())
        btn.layer().setBorderWidth_(0.0)
        btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                btn.title(),
                {
                    NSForegroundColorAttributeName: rgb_color(theme["accent_text"] if enabled else theme["text_muted"]),
                    NSFontAttributeName: NSFont.systemFontOfSize_weight_(13, AppKit.NSFontWeightSemibold),
                },
            )
        )
    else:
        bg = theme["surface"] if enabled else theme["elevated"]
        btn.layer().setBackgroundColor_(rgb_color(bg).CGColor())
        btn.layer().setBorderColor_(rgb_color(theme["border"]).CGColor())
        btn.layer().setBorderWidth_(1.0)
        btn.setAttributedTitle_(
            NSAttributedString.alloc().initWithString_attributes_(
                btn.title(),
                {
                    NSForegroundColorAttributeName: rgb_color(theme["text"] if enabled else theme["text_muted"]),
                    NSFontAttributeName: btn.font() or NSFont.systemFontOfSize_weight_(13, AppKit.NSFontWeightMedium),
                },
            )
        )


def make_card_box(radius=14):
    box = NSBox.alloc().initWithFrame_(NSMakeRect(0, 0, 100, 100))
    box.setBoxType_(AppKit.NSBoxCustom)
    box.setBorderType_(AppKit.NSLineBorder)
    box.setCornerRadius_(radius)
    box.setBorderWidth_(1.0)
    box.setContentViewMargins_(AppKit.NSMakeSize(0, 0))
    box.setTranslatesAutoresizingMaskIntoConstraints_(False)
    return box


def make_popup(width=180):
    popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(NSMakeRect(0, 0, width, 26), False)
    popup.setTranslatesAutoresizingMaskIntoConstraints_(False)
    popup.setFont_(NSFont.systemFontOfSize_weight_(12.5, AppKit.NSFontWeightSemibold))
    popup.setBordered_(False)
    popup.setControlSize_(AppKit.NSControlSizeRegular)
    cell = popup.cell()
    if cell is not None:
        cell.setArrowPosition_(AppKit.NSPopUpArrowAtBottom)
    return popup


def make_picker_chip(label_text, popup, theme, popup_w):
    chip = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, popup_w + 70, 34))
    chip.setWantsLayer_(True)
    chip.layer().setCornerRadius_(9.0)
    chip.layer().setBackgroundColor_(rgb_color(theme["surface"]).CGColor())
    chip.layer().setBorderColor_(rgb_color(theme["border"]).CGColor())
    chip.layer().setBorderWidth_(1.0)
    chip.setTranslatesAutoresizingMaskIntoConstraints_(False)

    tag = make_label(label_text, 9.5, AppKit.NSFontWeightBold, rgb_color(theme["text_muted"]))
    popup.setContentTintColor_(rgb_color(theme["accent"]))
    chip.addSubview_(tag)
    chip.addSubview_(popup)
    NSLayoutConstraint.activateConstraints_([
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(chip, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 34),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(tag, NSLayoutAttributeLeading, NSLayoutRelationEqual, chip, NSLayoutAttributeLeading, 1, 12),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(tag, NSLayoutAttributeCenterY, NSLayoutRelationEqual, chip, NSLayoutAttributeCenterY, 1, 0),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(popup, NSLayoutAttributeLeading, NSLayoutRelationEqual, tag, NSLayoutAttributeTrailing, 1, 4),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(popup, NSLayoutAttributeTrailing, NSLayoutRelationEqual, chip, NSLayoutAttributeTrailing, 1, -6),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(popup, NSLayoutAttributeCenterY, NSLayoutRelationEqual, chip, NSLayoutAttributeCenterY, 1, 0),
    ])
    return chip


_ROW_ACCENT = (0.0, 0.0, 0.0)


class HCTableRowView(NSTableRowView):
    def drawSelectionInRect_(self, rect):
        if self.selectionHighlightStyle() == AppKit.NSTableViewSelectionHighlightStyleNone:
            return
        inset = AppKit.NSInsetRect(self.bounds(), 8, 2)
        color = NSColor.colorWithRed_green_blue_alpha_(_ROW_ACCENT[0], _ROW_ACCENT[1], _ROW_ACCENT[2], 0.20)
        color.set()
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(inset, 8.0, 8.0)
        path.fill()


def session_subtitle(s):
    import time as _t
    turns = len(s.get("history", [])) // 2
    epoch = session_epoch(s)
    when = ""
    if epoch > 0:
        delta = _t.time() - epoch
        if delta < 60:
            when = "Just now"
        elif delta < 3600:
            when = f"{int(delta // 60)}m ago"
        elif delta < 86400:
            when = f"{int(delta // 3600)}h ago"
        elif delta < 7 * 86400:
            when = f"{int(delta // 86400)}d ago"
        else:
            when = _t.strftime("%b %d", _t.localtime(epoch))
    parts = []
    if when:
        parts.append(when)
    parts.append(f"{turns} turn{'s' if turns != 1 else ''}")
    return "  ·  ".join(parts)


def make_session_row_view(item, theme):
    w = SIDEBAR_W - 24
    cell = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, 56))
    cell.setTranslatesAutoresizingMaskIntoConstraints_(False)

    is_current = item.get("current")
    title_color = rgb_color(theme["accent"]) if is_current else rgb_color(theme["text"])
    title = make_label(item["title"][:46], 13, AppKit.NSFontWeightSemibold, title_color)
    title.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
    sub_text = "Current chat" if is_current else item.get("subtitle", "Saved session")
    sub = make_label(sub_text, 11, 0, rgb_color(theme["text_muted"]))
    sub.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)

    cell.addSubview_(title)
    cell.addSubview_(sub)
    NSLayoutConstraint.activateConstraints_([
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(title, NSLayoutAttributeLeading, NSLayoutRelationEqual, cell, NSLayoutAttributeLeading, 1, 14),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(title, NSLayoutAttributeTrailing, NSLayoutRelationLessThanOrEqual, cell, NSLayoutAttributeTrailing, 1, -12),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(title, NSLayoutAttributeTop, NSLayoutRelationEqual, cell, NSLayoutAttributeTop, 1, 10),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(sub, NSLayoutAttributeLeading, NSLayoutRelationEqual, title, NSLayoutAttributeLeading, 1, 0),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(sub, NSLayoutAttributeTrailing, NSLayoutRelationLessThanOrEqual, cell, NSLayoutAttributeTrailing, 1, -12),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(sub, NSLayoutAttributeTop, NSLayoutRelationEqual, title, NSLayoutAttributeBottom, 1, 3),
    ])
    return cell


def make_slash_row_view(item, theme):
    w = 760
    cell = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, 30))
    cell.setTranslatesAutoresizingMaskIntoConstraints_(False)
    name = make_label(item["label"], 13, AppKit.NSFontWeightSemibold, rgb_color(theme["accent"]), mono=True)
    desc = make_label(item["desc"][:110], 12, 0, rgb_color(theme["text_secondary"]))
    desc.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
    cell.addSubview_(name)
    cell.addSubview_(desc)
    NSLayoutConstraint.activateConstraints_([
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(name, NSLayoutAttributeLeading, NSLayoutRelationEqual, cell, NSLayoutAttributeLeading, 1, 14),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(name, NSLayoutAttributeCenterY, NSLayoutRelationEqual, cell, NSLayoutAttributeCenterY, 1, 0),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(name, NSLayoutAttributeWidth, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 120),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(desc, NSLayoutAttributeLeading, NSLayoutRelationEqual, name, NSLayoutAttributeTrailing, 1, 8),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(desc, NSLayoutAttributeCenterY, NSLayoutRelationEqual, cell, NSLayoutAttributeCenterY, 1, 0),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(desc, NSLayoutAttributeTrailing, NSLayoutRelationLessThanOrEqual, cell, NSLayoutAttributeTrailing, 1, -12),
    ])
    return cell


_ITALIC_CACHE = {}


def italic_font(size):
    f = _ITALIC_CACHE.get(size)
    if f is None:
        base = NSFont.systemFontOfSize_(size)
        f = AppKit.NSFontManager.sharedFontManager().convertFont_toHaveTrait_(
            base, AppKit.NSItalicFontMask) or base
        _ITALIC_CACHE[size] = f
    return f


def make_paragraph(line_height=1.22, spacing_before=0, spacing_after=2, indent=0):
    style = AppKit.NSMutableParagraphStyle.alloc().init()
    style.setLineHeightMultiple_(line_height)
    style.setParagraphSpacingBefore_(spacing_before)
    style.setParagraphSpacing_(spacing_after)
    style.setFirstLineHeadIndent_(indent)
    style.setHeadIndent_(indent)
    return style


def clear_stack(stack):
    for v in list(stack.arrangedSubviews()):
        stack.removeArrangedSubview_(v)
        v.removeFromSuperview()


def attr_string_from_fragments(fragments, theme):
    storage = AppKit.NSMutableAttributedString.alloc().init()
    for style, text in fragments:
        if not text:
            continue
        key = STYLE_MAP.get(style, "text")
        color = rgb_color(theme.get(key, theme["text"]))
        font = NSFont.systemFontOfSize_(15)
        if "code" in style:
            font = NSFont.monospacedSystemFontOfSize_weight_(13, 0)
            color = rgb_color(theme["code_text"])
        elif "strong" in style or "label" in style:
            font = NSFont.systemFontOfSize_weight_(15, AppKit.NSFontWeightSemibold)
        attrs = {NSForegroundColorAttributeName: color, NSFontAttributeName: font}
        storage.appendAttributedString_(NSAttributedString.alloc().initWithString_attributes_(text, attrs))
    return storage


def make_bubble_text_view(text, theme, width, markdown=False):
    tv = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, width, 40))
    tv.setEditable_(False)
    tv.setSelectable_(True)
    tv.setRichText_(True)
    tv.setDrawsBackground_(False)
    tv.setVerticallyResizable_(True)
    tv.setHorizontallyResizable_(False)
    tv.textContainer().setWidthTracksTextView_(True)
    tv.setTextContainerInset_((12, 14))
    tv.setFont_(NSFont.systemFontOfSize_(15))
    if markdown and text.strip():
        frags = md_to_fragments(text, max(40, width // 8), indent=0)
        astr = attr_string_from_fragments(frags, theme)
        tv.textStorage().setAttributedString_(astr)
    else:
        tv.setString_(text.rstrip())
        tv.setTextColor_(rgb_color(theme["text"]))
    tv.sizeToFit()
    h = max(36, int(tv.frame().size.height) + 8)
    tv.setFrame_(NSMakeRect(0, 0, width, h))
    return tv, h


def make_message_bubble(role, title, body, theme, markdown=False):
    """role: user | assistant | system | thinking"""
    row = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, BUBBLE_MAX + 80, 80))
    row.setTranslatesAutoresizingMaskIntoConstraints_(False)

    bubble = make_card_box(16)
    bubble.setTranslatesAutoresizingMaskIntoConstraints_(False)

    if role == "user":
        bubble.setFillColor_(rgb_color(theme["user_bubble"]))
        bubble.setBorderColor_(rgb_color(theme["user_bubble"]))
        title_color = rgb_color(theme["user_bubble_text"])
        body_color = rgb_color(theme["user_bubble_text"])
    elif role == "system":
        bubble.setFillColor_(rgb_color(theme["system_pill"]))
        bubble.setBorderColor_(rgb_color(theme["border"]))
        title_color = rgb_color(theme["text_muted"])
        body_color = rgb_color(theme["text_secondary"])
    elif role == "thinking":
        bubble.setFillColor_(rgb_color(theme["elevated"]))
        bubble.setBorderColor_(rgb_color(theme["border"]))
        title_color = rgb_color(theme["text_muted"])
        body_color = rgb_color(theme["text_muted"])
    else:
        bubble.setFillColor_(rgb_color(theme["asst_bubble"]))
        bubble.setBorderColor_(rgb_color(theme["asst_bubble_border"]))
        title_color = rgb_color(theme["assistant_label"])
        body_color = rgb_color(theme["text"])

    title_lbl = make_label(title, 11, AppKit.NSFontWeightSemibold, title_color)
    body_tv, body_h = make_bubble_text_view(body, theme, BUBBLE_MAX - 28, markdown=markdown and role == "assistant")
    if role == "user":
        body_tv.setTextColor_(body_color)

    for v in (bubble, title_lbl, body_tv):
        row.addSubview_(v)

    pad = 14
    NSLayoutConstraint.activateConstraints_([
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(bubble, NSLayoutAttributeTop, NSLayoutRelationEqual, row, NSLayoutAttributeTop, 1, 0),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(bubble, NSLayoutAttributeBottom, NSLayoutRelationEqual, row, NSLayoutAttributeBottom, 1, 0),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(bubble, NSLayoutAttributeWidth, NSLayoutRelationLessThanOrEqual, None, NSLayoutAttributeNotAnAttribute, 1, BUBBLE_MAX),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(title_lbl, NSLayoutAttributeTop, NSLayoutRelationEqual, bubble, NSLayoutAttributeTop, 1, pad),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(title_lbl, NSLayoutAttributeLeading, NSLayoutRelationEqual, bubble, NSLayoutAttributeLeading, 1, pad),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(title_lbl, NSLayoutAttributeTrailing, NSLayoutRelationEqual, bubble, NSLayoutAttributeTrailing, 1, -pad),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(body_tv, NSLayoutAttributeTop, NSLayoutRelationEqual, title_lbl, NSLayoutAttributeBottom, 1, 6),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(body_tv, NSLayoutAttributeLeading, NSLayoutRelationEqual, bubble, NSLayoutAttributeLeading, 1, 4),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(body_tv, NSLayoutAttributeTrailing, NSLayoutRelationEqual, bubble, NSLayoutAttributeTrailing, 1, -4),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(body_tv, NSLayoutAttributeBottom, NSLayoutRelationEqual, bubble, NSLayoutAttributeBottom, 1, -pad),
        NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(body_tv, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, body_h),
    ])

    if role == "user":
        NSLayoutConstraint.activateConstraints_([
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(bubble, NSLayoutAttributeTrailing, NSLayoutRelationEqual, row, NSLayoutAttributeTrailing, 1, -CHAT_PAD),
        ])
    elif role == "system":
        NSLayoutConstraint.activateConstraints_([
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(bubble, NSLayoutAttributeCenterX, NSLayoutRelationEqual, row, NSLayoutAttributeCenterX, 1, 0),
        ])
    else:
        NSLayoutConstraint.activateConstraints_([
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(bubble, NSLayoutAttributeLeading, NSLayoutRelationEqual, row, NSLayoutAttributeLeading, 1, CHAT_PAD),
        ])
    return row


class SearchFieldDelegate(NSObject):
    controller = objc.ivar("controller")

    def initWithController_(self, controller):
        self = objc.super(SearchFieldDelegate, self).init()
        if self is None:
            return None
        self.controller = controller
        return self

    def controlTextDidChange_(self, notification):
        self.controller.filterSessions_()


class InputTextDelegate(NSObject):
    controller = objc.ivar("controller")

    def initWithController_(self, controller):
        self = objc.super(InputTextDelegate, self).init()
        if self is None:
            return None
        self.controller = controller
        return self

    def textDidChange_(self, notification):
        self.controller.onInputChanged_(notification)

    def textView_doCommandBySelector_(self, text_view, command_selector):
        sel = str(command_selector)
        if sel == "insertNewline:":
            flags = AppKit.NSEvent.modifierFlags()
            if flags & AppKit.NSShiftKeyMask:
                return False
            self.controller.sendClicked_(None)
            return True
        return False


class MacChatUI(NSObject):
    shell = objc.ivar("shell")
    window = objc.ivar("window")
    chat_view = objc.ivar("chat_view")
    chat_column = objc.ivar("chat_column")
    input_view = objc.ivar("input_view")
    input_delegate = objc.ivar("input_delegate")
    model_popup = objc.ivar("model_popup")
    reasoning_popup = objc.ivar("reasoning_popup")
    slash_panel = objc.ivar("slash_panel")
    slash_table = objc.ivar("slash_table")
    slash_items = objc.ivar("slash_items")
    status_field = objc.ivar("status_field")
    status_pill = objc.ivar("status_pill")
    header_bar = objc.ivar("header_bar")
    composer_card = objc.ivar("composer_card")
    _follow_output = objc.ivar("_follow_output")
    _last_render_ver = objc.ivar("_last_render_ver")
    _slash_timer = objc.ivar("_slash_timer")
    _slash_height = objc.ivar("_slash_height")

    def initWithShell_(self, shell):
        self = objc.super(MacChatUI, self).init()
        if self is None:
            return None
        self.shell = shell
        self.slash_items = []
        self.filtered_sessions = []
        self._follow_output = True
        self._last_render_ver = -1
        self._slash_timer = None
        self._attach_height = None
        self.buildMainWindow()
        return self

    # --- Shell UI delegate ---

    @objc.python_method
    def requestRefresh(self):
        self.run_on_main(self.refreshAll)

    @objc.python_method
    def refreshAll(self):
        self.rebuildMessages()
        self.refreshAttachments()
        self.reloadSidebar()
        self.updateSessionTitle()
        self.updateComposerHint()

    @objc.python_method
    def updateComposerHint(self):
        base = "Return to send   ·   Shift-Return for newline   ·   / for commands"
        try:
            stats = self.shell.usage_summary()
        except Exception:
            stats = ""
        text = f"{base}        {stats}" if stats else base
        self.composer_hint.setStringValue_(text)

    @objc.python_method
    def refresh_status_bar(self):
        pass

    @objc.python_method
    def request_exit(self):
        self.run_on_main(self.quitApp)

    @objc.python_method
    def body_width(self):
        try:
            w = self.chat_view.bounds().size.width
            char_w = 8.2
            return max(48, int((w - 2 * CHAT_PAD) / char_w))
        except Exception:
            return 96

    @objc.python_method
    def run_on_main(self, fn):
        AppHelper.callAfter(fn)

    @objc.python_method
    def run_on_main_sync(self, fn):
        done = threading.Event()
        result = {}

        def wrapper():
            try:
                result["value"] = fn()
            finally:
                done.set()

        AppHelper.callAfter(wrapper)
        done.wait(timeout=120)
        return result.get("value")

    @objc.python_method
    def pick_model(self):
        return self.run_on_main_sync(lambda: self.modelIndexToId(self.model_popup.indexOfSelectedItem()))

    @objc.python_method
    def pick_attach_kind_and_path(self):
        return self.run_on_main_sync(self.showAttachDialog)

    @objc.python_method
    def ask_text(self, title, prompt):
        return self.run_on_main_sync(lambda: self.showTextDialog(title, prompt))

    @objc.python_method
    def pick_session(self, session_id=None):
        return self.run_on_main_sync(lambda: self.showSessionDialog(session_id))

    @objc.python_method
    def themeColors(self):
        return THEME["dark" if self.themeIsDark() else "light"]

    @objc.python_method
    def themeIsDark(self):
        return self.shell.theme_name != "light"

    @objc.python_method
    def apply_theme(self, name):
        global _ROW_ACCENT
        t = THEME["dark" if name != "light" else "light"]
        _ROW_ACCENT = t["accent"]
        if name != "light":
            AppKit.NSApp.setAppearance_(AppKit.NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua"))
        else:
            AppKit.NSApp.setAppearance_(AppKit.NSAppearance.appearanceNamed_("NSAppearanceNameAqua"))

        root = self.window.contentView()
        root.setWantsLayer_(True)
        root.layer().setBackgroundColor_(rgb_color(t["window"]).CGColor())

        self.sidebar.setMaterial_(AppKit.NSVisualEffectMaterialSidebar)
        self.top_bar.setMaterial_(AppKit.NSVisualEffectMaterialHeaderView)
        self.composer_dock.setMaterial_(AppKit.NSVisualEffectMaterialUnderWindowBackground)
        self.message_scroll.setBackgroundColor_(rgb_color(t["canvas"]))

        self.composer_card.setFillColor_(rgb_color(t["surface"]))
        self.composer_card.setBorderColor_(rgb_color(t["composer_border"]))
        self.attach_strip.setFillColor_(rgb_color(t["elevated"]))
        self.attach_strip.setBorderColor_(rgb_color(t["border"]))

        self.input_view.setBackgroundColor_(AppKit.NSColor.clearColor())
        self.input_view.setTextColor_(rgb_color(t["text"]))
        self.input_view.setInsertionPointColor_(rgb_color(t["accent"]))

        self.slash_panel.setFillColor_(rgb_color(t["palette_bg"]))
        self.slash_panel.setBorderColor_(rgb_color(t["palette_border"]))
        self.session_title_label.setTextColor_(rgb_color(t["text"]))

        for chip in (getattr(self, "model_chip", None), getattr(self, "reasoning_chip", None)):
            if chip is not None:
                chip.layer().setBackgroundColor_(rgb_color(t["surface"]).CGColor())
                chip.layer().setBorderColor_(rgb_color(t["border"]).CGColor())
        for popup in (self.model_popup, self.reasoning_popup):
            popup.setContentTintColor_(rgb_color(t["accent"]))
        if getattr(self, "clear_all_btn", None) is not None:
            self.clear_all_btn.setContentTintColor_(rgb_color(t["text_muted"]))

        style_pill_button(self.new_chat_btn, t, accent=True, enabled=True)
        style_pill_button(self.send_btn, t, accent=True, enabled=self.send_btn.isEnabled())
        style_pill_button(self.stop_btn, t, accent=False, enabled=self.stop_btn.isEnabled())
        for btn in (self.attach_btn, self.export_btn, self.settings_btn, getattr(self, "rename_chat_btn", None)):
            if btn is not None:
                style_pill_button(btn, t, accent=False, enabled=btn.isEnabled())

        if getattr(self, "welcome_overlay", None) is not None:
            self.welcome_overlay.layer().setBackgroundColor_(rgb_color(t["canvas"]).CGColor())
            self.welcome_title.setTextColor_(rgb_color(t["text"]))
            self.welcome_sub.setTextColor_(rgb_color(t["text_secondary"]))
            for card in self.suggestion_cards:
                style_suggestion_card(card, t)

        self.rebuildMessages()

    def postOkMessage_(self, msg):
        self.shell.ok(msg)
        self._last_render_ver = -1
        self.requestRefresh()

    def postInfoMessage_(self, msg):
        self.shell.info(msg)
        self._last_render_ver = -1
        self.requestRefresh()

    # --- Window ---

    @objc.python_method
    def buildMainWindow(self):
        frame = NSMakeRect(80, 40, 1280, 860)
        style = (
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
            | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable
            | NSWindowStyleMaskFullSizeContentView
        )
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(frame, style, NSBackingStoreBuffered, False)
        self.window.setTitle_(APP_NAME)
        self.window.setMinSize_((960, 620))
        self.window.setDelegate_(self)
        self.window.setTitlebarAppearsTransparent_(True)
        self.window.setTitleVisibility_(AppKit.NSWindowTitleHidden)
        self.window.setBackgroundColor_(rgb_color(THEME["dark"]["window"]))

        root = NSView.alloc().initWithFrame_(frame)
        root.setWantsLayer_(True)
        self.window.setContentView_(root)

        self.sidebar = self.buildSidebar()
        self.main_panel = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 100, 100))
        self.main_panel.setTranslatesAutoresizingMaskIntoConstraints_(False)
        self.top_bar = self.buildTopBar()
        self.message_scroll = self.buildMessageArea()
        self.attach_strip = make_card_box(10)
        self.attach_strip.setHidden_(True)
        self.composer_dock = self.buildComposer()
        self.slash_panel, self.slash_table = self.buildSlashPanel()
        self.welcome_overlay = self.buildWelcomeOverlay()

        for v in (self.top_bar, self.message_scroll, self.attach_strip, self.composer_dock, self.welcome_overlay):
            v.setTranslatesAutoresizingMaskIntoConstraints_(False)
            self.main_panel.addSubview_(v)

        for v in (self.sidebar, self.main_panel, self.slash_panel):
            v.setTranslatesAutoresizingMaskIntoConstraints_(False)
            root.addSubview_(v)

        NSLayoutConstraint.activateConstraints_([
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.sidebar, NSLayoutAttributeTop, NSLayoutRelationEqual, root, NSLayoutAttributeTop, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.sidebar, NSLayoutAttributeBottom, NSLayoutRelationEqual, root, NSLayoutAttributeBottom, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.sidebar, NSLayoutAttributeLeading, NSLayoutRelationEqual, root, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.sidebar, NSLayoutAttributeWidth, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, SIDEBAR_W),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.main_panel, NSLayoutAttributeTop, NSLayoutRelationEqual, root, NSLayoutAttributeTop, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.main_panel, NSLayoutAttributeBottom, NSLayoutRelationEqual, root, NSLayoutAttributeBottom, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.main_panel, NSLayoutAttributeLeading, NSLayoutRelationEqual, self.sidebar, NSLayoutAttributeTrailing, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.main_panel, NSLayoutAttributeTrailing, NSLayoutRelationEqual, root, NSLayoutAttributeTrailing, 1, 0),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.top_bar, NSLayoutAttributeTop, NSLayoutRelationEqual, self.main_panel, NSLayoutAttributeTop, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.top_bar, NSLayoutAttributeLeading, NSLayoutRelationEqual, self.main_panel, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.top_bar, NSLayoutAttributeTrailing, NSLayoutRelationEqual, self.main_panel, NSLayoutAttributeTrailing, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.top_bar, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, TOPBAR_H),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.message_scroll, NSLayoutAttributeTop, NSLayoutRelationEqual, self.top_bar, NSLayoutAttributeBottom, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.message_scroll, NSLayoutAttributeLeading, NSLayoutRelationEqual, self.main_panel, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.message_scroll, NSLayoutAttributeTrailing, NSLayoutRelationEqual, self.main_panel, NSLayoutAttributeTrailing, 1, 0),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.attach_strip, NSLayoutAttributeTop, NSLayoutRelationEqual, self.message_scroll, NSLayoutAttributeBottom, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.attach_strip, NSLayoutAttributeLeading, NSLayoutRelationEqual, self.main_panel, NSLayoutAttributeLeading, 1, 20),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.attach_strip, NSLayoutAttributeTrailing, NSLayoutRelationEqual, self.main_panel, NSLayoutAttributeTrailing, 1, -20),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.attach_strip, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 0),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.composer_dock, NSLayoutAttributeTop, NSLayoutRelationEqual, self.attach_strip, NSLayoutAttributeBottom, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.composer_dock, NSLayoutAttributeLeading, NSLayoutRelationEqual, self.main_panel, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.composer_dock, NSLayoutAttributeTrailing, NSLayoutRelationEqual, self.main_panel, NSLayoutAttributeTrailing, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.composer_dock, NSLayoutAttributeBottom, NSLayoutRelationEqual, self.main_panel, NSLayoutAttributeBottom, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.composer_dock, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, COMPOSER_H),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.slash_panel, NSLayoutAttributeBottom, NSLayoutRelationEqual, self.composer_dock, NSLayoutAttributeTop, 1, -10),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.slash_panel, NSLayoutAttributeLeading, NSLayoutRelationEqual, self.main_panel, NSLayoutAttributeLeading, 1, 24),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.slash_panel, NSLayoutAttributeTrailing, NSLayoutRelationEqual, self.main_panel, NSLayoutAttributeTrailing, 1, -24),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.welcome_overlay, NSLayoutAttributeTop, NSLayoutRelationEqual, self.message_scroll, NSLayoutAttributeTop, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.welcome_overlay, NSLayoutAttributeBottom, NSLayoutRelationEqual, self.message_scroll, NSLayoutAttributeBottom, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.welcome_overlay, NSLayoutAttributeLeading, NSLayoutRelationEqual, self.message_scroll, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.welcome_overlay, NSLayoutAttributeTrailing, NSLayoutRelationEqual, self.message_scroll, NSLayoutAttributeTrailing, 1, 0),
        ])
        self._slash_height = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.slash_panel, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 0)
        self._attach_height = NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(
            self.attach_strip, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 0)
        NSLayoutConstraint.activateConstraints_([self._slash_height, self._attach_height])

        self.apply_theme(self.shell.theme_name)
        self.buildMenus()
        self.syncModelPickers()
        self.reloadSidebar()
        self.refreshAll()

    @objc.python_method
    def buildSidebar(self):
        bar = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, SIDEBAR_W, 100))
        bar.setMaterial_(AppKit.NSVisualEffectMaterialSidebar)
        bar.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
        bar.setState_(AppKit.NSVisualEffectStateActive)

        mark = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 32, 32))
        mark.setWantsLayer_(True)
        mark.layer().setCornerRadius_(9.0)
        mark.layer().setBackgroundColor_(rgb_color(THEME["dark"]["accent"]).CGColor())
        mark.setTranslatesAutoresizingMaskIntoConstraints_(False)
        mark_lbl = make_label("HC", 12, AppKit.NSFontWeightBold, NSColor.whiteColor())
        mark.addSubview_(mark_lbl)
        mark_lbl.setTranslatesAutoresizingMaskIntoConstraints_(False)

        brand = make_label(BANNER, 16, AppKit.NSFontWeightSemibold, NSColor.labelColor())
        sub = make_label("Your AI workspace", 11, 0, NSColor.secondaryLabelColor())
        self.new_chat_btn = make_pill_button(self, "New Chat", "newSession:", accent=True, fixed_width=False)

        self.search_field = NSSearchField.alloc().initWithFrame_(NSMakeRect(0, 0, SIDEBAR_W - 32, 34))
        self.search_field.setPlaceholderString_("Search chats")
        self.search_field.setFont_(NSFont.systemFontOfSize_(13))
        self.search_field.setControlSize_(AppKit.NSControlSizeLarge)
        self.search_field.setTranslatesAutoresizingMaskIntoConstraints_(False)
        self.search_delegate = SearchFieldDelegate.alloc().initWithController_(self)
        self.search_field.setDelegate_(self.search_delegate)

        self.session_table = NSTableView.alloc().initWithFrame_(NSMakeRect(0, 0, SIDEBAR_W, 300))
        col = NSTableColumn.alloc().initWithIdentifier_("session")
        col.setWidth_(SIDEBAR_W - 24)
        self.session_table.addTableColumn_(col)
        self.session_table.setHeaderView_(None)
        self.session_table.setDelegate_(self)
        self.session_table.setDataSource_(self)
        self.session_table.setTarget_(self)
        self.session_table.setAction_("sessionClicked:")
        self.session_table.setDoubleAction_("renameSessionRow_")
        self.session_table.setRowHeight_(56)
        self.session_table.setIntercellSpacing_(AppKit.NSMakeSize(0, 4))
        self.session_table.setBackgroundColor_(AppKit.NSColor.clearColor())
        self.session_table.setSelectionHighlightStyle_(AppKit.NSTableViewSelectionHighlightStyleRegular)
        self.session_table.setUsesAlternatingRowBackgroundColors_(False)
        self.session_table.setStyle_(AppKit.NSTableViewStyleInset) if hasattr(self.session_table, "setStyle_") else None
        self.session_table.setColumnAutoresizingStyle_(AppKit.NSTableViewUniformColumnAutoresizingStyle)

        sess_scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, SIDEBAR_W, 300))
        sess_scroll.setDocumentView_(self.session_table)
        sess_scroll.setHasVerticalScroller_(True)
        sess_scroll.setBorderType_(AppKit.NSNoBorder)
        sess_scroll.setDrawsBackground_(False)
        sess_scroll.setTranslatesAutoresizingMaskIntoConstraints_(False)

        self.recents_label = make_label("RECENTS", 10, AppKit.NSFontWeightBold, NSColor.secondaryLabelColor())
        self.clear_all_btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 44, 18))
        self.clear_all_btn.setTitle_("Clear")
        self.clear_all_btn.setBordered_(False)
        self.clear_all_btn.setFont_(NSFont.systemFontOfSize_weight_(11, AppKit.NSFontWeightSemibold))
        self.clear_all_btn.setTarget_(self)
        self.clear_all_btn.setAction_("clearAllSessions:")
        self.clear_all_btn.setContentTintColor_(rgb_color(THEME["dark"]["text_muted"]))
        self.clear_all_btn.setTranslatesAutoresizingMaskIntoConstraints_(False)

        for v in (mark, mark_lbl, brand, sub, self.new_chat_btn, self.search_field,
                  self.recents_label, self.clear_all_btn, sess_scroll):
            if v is not mark_lbl:
                bar.addSubview_(v)

        NSLayoutConstraint.activateConstraints_([
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(mark, NSLayoutAttributeTop, NSLayoutRelationEqual, bar, NSLayoutAttributeTop, 1, 52),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(mark, NSLayoutAttributeLeading, NSLayoutRelationEqual, bar, NSLayoutAttributeLeading, 1, 16),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(mark, NSLayoutAttributeWidth, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 32),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(mark, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 32),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(mark_lbl, NSLayoutAttributeCenterX, NSLayoutRelationEqual, mark, NSLayoutAttributeCenterX, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(mark_lbl, NSLayoutAttributeCenterY, NSLayoutRelationEqual, mark, NSLayoutAttributeCenterY, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(brand, NSLayoutAttributeLeading, NSLayoutRelationEqual, mark, NSLayoutAttributeTrailing, 1, 10),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(brand, NSLayoutAttributeTop, NSLayoutRelationEqual, mark, NSLayoutAttributeTop, 1, -2),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(sub, NSLayoutAttributeLeading, NSLayoutRelationEqual, brand, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(sub, NSLayoutAttributeTop, NSLayoutRelationEqual, brand, NSLayoutAttributeBottom, 1, -2),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.new_chat_btn, NSLayoutAttributeTop, NSLayoutRelationEqual, mark, NSLayoutAttributeBottom, 1, 16),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.new_chat_btn, NSLayoutAttributeLeading, NSLayoutRelationEqual, bar, NSLayoutAttributeLeading, 1, 16),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.new_chat_btn, NSLayoutAttributeTrailing, NSLayoutRelationEqual, bar, NSLayoutAttributeTrailing, 1, -16),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.search_field, NSLayoutAttributeTop, NSLayoutRelationEqual, self.new_chat_btn, NSLayoutAttributeBottom, 1, 16),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.search_field, NSLayoutAttributeLeading, NSLayoutRelationEqual, bar, NSLayoutAttributeLeading, 1, 16),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.search_field, NSLayoutAttributeTrailing, NSLayoutRelationEqual, bar, NSLayoutAttributeTrailing, 1, -16),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.search_field, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 34),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.recents_label, NSLayoutAttributeTop, NSLayoutRelationEqual, self.search_field, NSLayoutAttributeBottom, 1, 16),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.recents_label, NSLayoutAttributeLeading, NSLayoutRelationEqual, bar, NSLayoutAttributeLeading, 1, 18),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.clear_all_btn, NSLayoutAttributeCenterY, NSLayoutRelationEqual, self.recents_label, NSLayoutAttributeCenterY, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.clear_all_btn, NSLayoutAttributeTrailing, NSLayoutRelationEqual, bar, NSLayoutAttributeTrailing, 1, -14),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(sess_scroll, NSLayoutAttributeTop, NSLayoutRelationEqual, self.recents_label, NSLayoutAttributeBottom, 1, 8),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(sess_scroll, NSLayoutAttributeLeading, NSLayoutRelationEqual, bar, NSLayoutAttributeLeading, 1, 8),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(sess_scroll, NSLayoutAttributeTrailing, NSLayoutRelationEqual, bar, NSLayoutAttributeTrailing, 1, -8),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(sess_scroll, NSLayoutAttributeBottom, NSLayoutRelationEqual, bar, NSLayoutAttributeBottom, 1, -12),
        ])
        return bar

    @objc.python_method
    def buildTopBar(self):
        bar = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, 100, TOPBAR_H))
        bar.setMaterial_(AppKit.NSVisualEffectMaterialHeaderView)
        bar.setBlendingMode_(AppKit.NSVisualEffectBlendingModeWithinWindow)
        bar.setState_(AppKit.NSVisualEffectStateActive)
        bar.setTranslatesAutoresizingMaskIntoConstraints_(False)

        self.session_title_label = make_label("New conversation", 15, AppKit.NSFontWeightSemibold, NSColor.labelColor())
        self.session_title_label.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
        self.rename_chat_btn = make_pill_button(self, "Rename", "renameCurrentSession:", compact=True)

        self.model_popup = make_popup(160)
        for name, _ in MODELS:
            self.model_popup.addItemWithTitle_(name)
        self.model_popup.setTarget_(self)
        self.model_popup.setAction_("modelPopupChanged:")
        self.reasoning_popup = make_popup(116)
        self.reasoning_popup.setTarget_(self)
        self.reasoning_popup.setAction_("reasoningPopupChanged:")
        model_chip = make_picker_chip("MODEL", self.model_popup, THEME["dark"], 160)
        reasoning_chip = make_picker_chip("EFFORT", self.reasoning_popup, THEME["dark"], 116)
        self.model_chip = model_chip
        self.reasoning_chip = reasoning_chip

        self.attach_btn = make_pill_button(self, "Attach", "attachClicked:", compact=True)
        self.export_btn = make_pill_button(self, "Export", "exportChat:", compact=True)
        self.settings_btn = make_pill_button(self, "Settings", "showSettings:", compact=True)

        for v in (self.session_title_label, self.rename_chat_btn, model_chip, reasoning_chip, self.attach_btn, self.export_btn, self.settings_btn):
            bar.addSubview_(v)

        NSLayoutConstraint.activateConstraints_([
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.session_title_label, NSLayoutAttributeLeading, NSLayoutRelationEqual, bar, NSLayoutAttributeLeading, 1, 22),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.session_title_label, NSLayoutAttributeCenterY, NSLayoutRelationEqual, bar, NSLayoutAttributeCenterY, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.rename_chat_btn, NSLayoutAttributeLeading, NSLayoutRelationEqual, self.session_title_label, NSLayoutAttributeTrailing, 1, 10),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.rename_chat_btn, NSLayoutAttributeCenterY, NSLayoutRelationEqual, bar, NSLayoutAttributeCenterY, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.rename_chat_btn, NSLayoutAttributeTrailing, NSLayoutRelationLessThanOrEqual, model_chip, NSLayoutAttributeLeading, 1, -16),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.settings_btn, NSLayoutAttributeTrailing, NSLayoutRelationEqual, bar, NSLayoutAttributeTrailing, 1, -16),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.settings_btn, NSLayoutAttributeCenterY, NSLayoutRelationEqual, bar, NSLayoutAttributeCenterY, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.export_btn, NSLayoutAttributeTrailing, NSLayoutRelationEqual, self.settings_btn, NSLayoutAttributeLeading, 1, -8),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.export_btn, NSLayoutAttributeCenterY, NSLayoutRelationEqual, bar, NSLayoutAttributeCenterY, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.attach_btn, NSLayoutAttributeTrailing, NSLayoutRelationEqual, self.export_btn, NSLayoutAttributeLeading, 1, -8),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.attach_btn, NSLayoutAttributeCenterY, NSLayoutRelationEqual, bar, NSLayoutAttributeCenterY, 1, 0),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(reasoning_chip, NSLayoutAttributeTrailing, NSLayoutRelationEqual, self.attach_btn, NSLayoutAttributeLeading, 1, -14),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(reasoning_chip, NSLayoutAttributeCenterY, NSLayoutRelationEqual, bar, NSLayoutAttributeCenterY, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(model_chip, NSLayoutAttributeTrailing, NSLayoutRelationEqual, reasoning_chip, NSLayoutAttributeLeading, 1, -8),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(model_chip, NSLayoutAttributeCenterY, NSLayoutRelationEqual, bar, NSLayoutAttributeCenterY, 1, 0),
        ])
        return bar

    @objc.python_method
    def buildMessageArea(self):
        scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 600, 400))
        scroll.setHasVerticalScroller_(True)
        scroll.setAutohidesScrollers_(True)
        scroll.setBorderType_(AppKit.NSNoBorder)
        scroll.setDrawsBackground_(True)
        scroll.setTranslatesAutoresizingMaskIntoConstraints_(False)

        content_size = scroll.contentSize()
        tv = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, content_size.width, content_size.height))
        tv.setEditable_(False)
        tv.setSelectable_(True)
        tv.setRichText_(True)
        tv.setDrawsBackground_(False)
        tv.setMinSize_((0, 0))
        tv.setMaxSize_((1.0e7, 1.0e7))
        tv.setVerticallyResizable_(True)
        tv.setHorizontallyResizable_(False)
        tv.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        tv.textContainer().setContainerSize_((content_size.width, 1.0e7))
        tv.textContainer().setWidthTracksTextView_(True)
        tv.textContainer().setLineFragmentPadding_(0)
        tv.setTextContainerInset_(AppKit.NSMakeSize(CHAT_PAD, 28))
        tv.setFont_(NSFont.systemFontOfSize_(15))

        self.chat_view = tv
        scroll.setDocumentView_(tv)
        return scroll

    @objc.python_method
    def buildComposer(self):
        dock = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, 100, COMPOSER_H))
        dock.setMaterial_(AppKit.NSVisualEffectMaterialUnderWindowBackground)
        dock.setBlendingMode_(AppKit.NSVisualEffectBlendingModeWithinWindow)
        dock.setState_(AppKit.NSVisualEffectStateActive)
        dock.setTranslatesAutoresizingMaskIntoConstraints_(False)

        container = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 100, COMPOSER_H - 20))
        container.setTranslatesAutoresizingMaskIntoConstraints_(False)

        self.composer_card = make_card_box(14)
        self.composer_card.setFillColor_(rgb_color(THEME["dark"]["surface"]))
        self.composer_card.setBorderColor_(rgb_color(THEME["dark"]["composer_border"]))

        input_scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 600, 76))
        input_scroll.setBorderType_(AppKit.NSNoBorder)
        input_scroll.setDrawsBackground_(False)
        input_scroll.setHasVerticalScroller_(True)
        input_scroll.setAutohidesScrollers_(True)
        input_scroll.setTranslatesAutoresizingMaskIntoConstraints_(False)

        csize = NSMakeRect(0, 0, 600, 76).size
        self.input_view = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, csize.width, csize.height))
        self.input_view.setEditable_(True)
        self.input_view.setSelectable_(True)
        self.input_view.setRichText_(False)
        self.input_view.setImportsGraphics_(False)
        self.input_view.setDrawsBackground_(False)
        self.input_view.setFont_(NSFont.systemFontOfSize_(15))
        self.input_view.setTextColor_(NSColor.labelColor())
        self.input_view.setInsertionPointColor_(rgb_color(THEME["dark"]["accent"]))
        self.input_view.setTextContainerInset_(AppKit.NSMakeSize(6, 12))
        self.input_view.setMinSize_((0, 0))
        self.input_view.setMaxSize_((1.0e7, 1.0e7))
        self.input_view.setVerticallyResizable_(True)
        self.input_view.setHorizontallyResizable_(False)
        self.input_view.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        self.input_view.textContainer().setContainerSize_((csize.width, 1.0e7))
        self.input_view.textContainer().setWidthTracksTextView_(True)
        self.input_view.setAutomaticQuoteSubstitutionEnabled_(False)
        self.input_view.setAutomaticDashSubstitutionEnabled_(False)
        self.input_view.setAutomaticTextReplacementEnabled_(False)
        self.input_view.setAutomaticSpellingCorrectionEnabled_(False)
        self.input_delegate = InputTextDelegate.alloc().initWithController_(self)
        self.input_view.setDelegate_(self.input_delegate)
        input_scroll.setDocumentView_(self.input_view)

        self.composer_hint = make_label("Return to send  ·  Shift-Return for newline  ·  / for commands", 11, 0, NSColor.secondaryLabelColor())
        hint = self.composer_hint

        self.send_btn = make_pill_button(self, "Send", "sendClicked:", accent=True)
        self.send_btn.setKeyEquivalent_("\r")
        self.stop_btn = make_pill_button(self, "Stop", "stopClicked:", accent=False)
        self.stop_btn.setEnabled_(False)
        self.stop_btn.setHidden_(True)

        dock.addSubview_(container)
        for v in (self.composer_card, input_scroll, hint, self.send_btn, self.stop_btn):
            container.addSubview_(v)

        NSLayoutConstraint.activateConstraints_([
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(container, NSLayoutAttributeCenterX, NSLayoutRelationEqual, dock, NSLayoutAttributeCenterX, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(container, NSLayoutAttributeTop, NSLayoutRelationEqual, dock, NSLayoutAttributeTop, 1, 8),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(container, NSLayoutAttributeWidth, NSLayoutRelationEqual, dock, NSLayoutAttributeWidth, 1, -48),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(container, NSLayoutAttributeBottom, NSLayoutRelationEqual, dock, NSLayoutAttributeBottom, 1, -8),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.composer_card, NSLayoutAttributeTop, NSLayoutRelationEqual, container, NSLayoutAttributeTop, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.composer_card, NSLayoutAttributeLeading, NSLayoutRelationEqual, container, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.composer_card, NSLayoutAttributeTrailing, NSLayoutRelationEqual, container, NSLayoutAttributeTrailing, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.composer_card, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 72),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(input_scroll, NSLayoutAttributeTop, NSLayoutRelationEqual, self.composer_card, NSLayoutAttributeTop, 1, 3),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(input_scroll, NSLayoutAttributeBottom, NSLayoutRelationEqual, self.composer_card, NSLayoutAttributeBottom, 1, -3),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(input_scroll, NSLayoutAttributeLeading, NSLayoutRelationEqual, self.composer_card, NSLayoutAttributeLeading, 1, 4),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(input_scroll, NSLayoutAttributeTrailing, NSLayoutRelationEqual, self.composer_card, NSLayoutAttributeTrailing, 1, -4),

            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.send_btn, NSLayoutAttributeTop, NSLayoutRelationEqual, self.composer_card, NSLayoutAttributeBottom, 1, 10),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.send_btn, NSLayoutAttributeTrailing, NSLayoutRelationEqual, container, NSLayoutAttributeTrailing, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.stop_btn, NSLayoutAttributeCenterY, NSLayoutRelationEqual, self.send_btn, NSLayoutAttributeCenterY, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.stop_btn, NSLayoutAttributeTrailing, NSLayoutRelationEqual, self.send_btn, NSLayoutAttributeLeading, 1, -10),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(hint, NSLayoutAttributeCenterY, NSLayoutRelationEqual, self.send_btn, NSLayoutAttributeCenterY, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(hint, NSLayoutAttributeLeading, NSLayoutRelationEqual, container, NSLayoutAttributeLeading, 1, 4),
        ])
        return dock

    @objc.python_method
    def buildSlashPanel(self):
        panel = make_card_box(12)
        panel.setHidden_(True)

        table = NSTableView.alloc().initWithFrame_(NSMakeRect(0, 0, 100, 140))
        col = NSTableColumn.alloc().initWithIdentifier_("cmd")
        col.setWidth_(760)
        table.addTableColumn_(col)
        table.setHeaderView_(None)
        table.setDelegate_(self)
        table.setDataSource_(self)
        table.setDoubleAction_("slashSelected:")
        table.setTarget_(self)
        table.setRowHeight_(28)
        table.setIntercellSpacing_((8, 4))
        table.setBackgroundColor_(AppKit.NSColor.clearColor())
        table.setSelectionHighlightStyle_(AppKit.NSTableViewSelectionHighlightStyleRegular)

        scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 100, 140))
        scroll.setDocumentView_(table)
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(AppKit.NSNoBorder)
        scroll.setDrawsBackground_(False)
        scroll.setTranslatesAutoresizingMaskIntoConstraints_(False)
        panel.addSubview_(scroll)

        NSLayoutConstraint.activateConstraints_([
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(scroll, NSLayoutAttributeTop, NSLayoutRelationEqual, panel, NSLayoutAttributeTop, 1, 8),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(scroll, NSLayoutAttributeBottom, NSLayoutRelationEqual, panel, NSLayoutAttributeBottom, 1, -8),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(scroll, NSLayoutAttributeLeading, NSLayoutRelationEqual, panel, NSLayoutAttributeLeading, 1, 10),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(scroll, NSLayoutAttributeTrailing, NSLayoutRelationEqual, panel, NSLayoutAttributeTrailing, 1, -10),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(scroll, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 140),
        ])
        return panel, table

    @objc.python_method
    def buildStatusBar(self):
        pill = make_card_box(999)
        pill.setBorderWidth_(1.0)

        field = make_label("Ready", 11, AppKit.NSFontWeightMedium, NSColor.secondaryLabelColor(), mono=True)
        field.setLineBreakMode_(AppKit.NSLineBreakByTruncatingMiddle)
        pill.addSubview_(field)

        NSLayoutConstraint.activateConstraints_([
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(field, NSLayoutAttributeLeading, NSLayoutRelationEqual, pill, NSLayoutAttributeLeading, 1, 16),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(field, NSLayoutAttributeTrailing, NSLayoutRelationEqual, pill, NSLayoutAttributeTrailing, 1, -16),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(field, NSLayoutAttributeCenterY, NSLayoutRelationEqual, pill, NSLayoutAttributeCenterY, 1, 0),
        ])
        return pill, field

    @objc.python_method
    def buildMenus(self):
        menubar = NSMenu.alloc().init()
        app_menu = NSMenu.alloc().init()
        app_menu.addItemWithTitle_action_keyEquivalent_(f"About {APP_NAME}", "showAbout:", "")
        app_menu.addItemWithTitle_action_keyEquivalent_("Settings…", "showSettings:", ",")
        app_menu.addItem_(NSMenuItem.separatorItem())
        app_menu.addItemWithTitle_action_keyEquivalent_(f"Quit {APP_NAME}", "terminate:", "q")
        app_item = NSMenuItem.alloc().init()
        app_item.setSubmenu_(app_menu)
        menubar.addItem_(app_item)

        file_menu = NSMenu.alloc().initWithTitle_("File")
        file_menu.addItemWithTitle_action_keyEquivalent_("Attach File…", "attachFile:", "o")
        file_menu.addItemWithTitle_action_keyEquivalent_("Attach Folder…", "attachFolder:", "O")
        file_menu.addItem_(NSMenuItem.separatorItem())
        file_menu.addItemWithTitle_action_keyEquivalent_("Export Chat…", "exportChat:", "e")
        file_menu.addItemWithTitle_action_keyEquivalent_("New Session", "newSession:", "n")
        file_menu.addItemWithTitle_action_keyEquivalent_("Resume Session…", "resumeSession:", "r")
        file_item = NSMenuItem.alloc().init()
        file_item.setSubmenu_(file_menu)
        menubar.addItem_(file_item)

        view_menu = NSMenu.alloc().initWithTitle_("View")
        view_menu.addItemWithTitle_action_keyEquivalent_("Dark Theme", "themeDark:", "")
        view_menu.addItemWithTitle_action_keyEquivalent_("Light Theme", "themeLight:", "")
        view_menu.addItemWithTitle_action_keyEquivalent_("Toggle Compact", "toggleCompact:", "")
        view_item = NSMenuItem.alloc().init()
        view_item.setSubmenu_(view_menu)
        menubar.addItem_(view_item)

        AppKit.NSApp.setMainMenu_(menubar)

    @objc.python_method
    def activateMainWindow(self, on_ready=None):
        self.window.setInitialFirstResponder_(self.input_view)
        self.window.makeKeyAndOrderFront_(None)
        AppKit.NSApp.activateIgnoringOtherApps_(True)

        def _focus():
            self.window.makeFirstResponder_(self.input_view)
        AppHelper.callAfter(_focus)
        if on_ready:
            AppHelper.callAfter(on_ready)

    # --- Model pickers ---

    @objc.python_method
    def modelIndexToId(self, idx):
        if idx < 0 or idx >= len(MODELS):
            return None
        name, mid = MODELS[idx]
        if mid == "custom":
            return self.showTextDialog("Custom model", "OpenRouter model ID:")
        return mid

    @objc.python_method
    def syncModelPickers(self):
        idx = 0
        for i, (_, mid) in enumerate(MODELS):
            if mid == self.shell.model:
                idx = i
                break
        self.model_popup.selectItemAtIndex_(idx)
        self.populateReasoningPopup()
        self.updateSessionTitle()

    @objc.python_method
    def populateReasoningPopup(self):
        self.reasoning_popup.removeAllItems()
        mid = self.modelIndexToId(self.model_popup.indexOfSelectedItem()) or self.shell.model
        current = normalize_reasoning_for_model(mid, self.shell.reasoning_level)
        select = 0
        for i, (label, effort) in enumerate(reasoning_variants_for_model(mid)):
            self.reasoning_popup.addItemWithTitle_(label)
            if effort == current:
                select = i
        self.reasoning_popup.selectItemAtIndex_(select)

    def modelPopupChanged_(self, sender):
        mid = self.modelIndexToId(self.model_popup.indexOfSelectedItem())
        if mid:
            self.shell._apply_model(mid)
            self.populateReasoningPopup()

    def reasoningPopupChanged_(self, sender):
        idx = self.model_popup.indexOfSelectedItem()
        if idx < 0:
            return
        _, mid = MODELS[idx]
        label = self.reasoning_popup.titleOfSelectedItem()
        if label:
            self.shell._apply_model(mid, reasoning=label)

    # --- Rendering ---

    @objc.python_method
    def colorForStyle(self, style):
        theme = self.themeColors()
        key = STYLE_MAP.get(style, "text")
        return rgb_color(theme[key])

    @objc.python_method
    def attrsForFragment(self, style, text, theme):
        body = NSFont.systemFontOfSize_(15)
        body_medium = NSFont.systemFontOfSize_weight_(15, AppKit.NSFontWeightMedium)
        bold = NSFont.systemFontOfSize_weight_(15, AppKit.NSFontWeightSemibold)
        mono = NSFont.monospacedSystemFontOfSize_weight_(13.5, AppKit.NSFontWeightRegular)
        small = NSFont.systemFontOfSize_weight_(13, AppKit.NSFontWeightMedium)

        para = make_paragraph()
        attrs = {
            NSForegroundColorAttributeName: self.colorForStyle(style),
            NSFontAttributeName: body,
            AppKit.NSParagraphStyleAttributeName: para,
        }

        if style == "class:sep":
            return None
        if style == "class:user_label":
            attrs[NSFontAttributeName] = bold
            attrs[NSForegroundColorAttributeName] = rgb_color(theme["user_label"])
            attrs[AppKit.NSParagraphStyleAttributeName] = make_paragraph(spacing_before=4, spacing_after=2)
        elif style == "class:asst_label":
            attrs[NSFontAttributeName] = bold
            attrs[NSForegroundColorAttributeName] = rgb_color(theme["assistant_label"])
            attrs[AppKit.NSParagraphStyleAttributeName] = make_paragraph(spacing_before=6, spacing_after=2)
        elif style == "class:user_msg":
            attrs[NSFontAttributeName] = body_medium
            attrs[NSForegroundColorAttributeName] = rgb_color(theme["user_text"])
            attrs[AppKit.NSParagraphStyleAttributeName] = make_paragraph(spacing_after=2, indent=2)
        elif style == "class:label":
            attrs[NSFontAttributeName] = NSFont.systemFontOfSize_weight_(24, AppKit.NSFontWeightBold)
            attrs[AppKit.NSParagraphStyleAttributeName] = make_paragraph(spacing_before=4, spacing_after=6)
        elif style == "class:dim":
            attrs[NSFontAttributeName] = NSFont.systemFontOfSize_(13.5)
            attrs[NSForegroundColorAttributeName] = rgb_color(theme["text_secondary"])
            attrs[AppKit.NSParagraphStyleAttributeName] = make_paragraph(spacing_after=2)
        elif style == "class:code":
            attrs[NSFontAttributeName] = mono
            attrs[NSForegroundColorAttributeName] = rgb_color(theme["code_text"])
            attrs[AppKit.NSBackgroundColorAttributeName] = rgb_color(theme["code_bg"])
            attrs[AppKit.NSParagraphStyleAttributeName] = make_paragraph(line_height=1.25, spacing_before=0, spacing_after=0, indent=8)
        elif style == "class:attach":
            attrs[NSFontAttributeName] = small
            attrs[NSForegroundColorAttributeName] = rgb_color(theme["accent"])
            attrs[AppKit.NSParagraphStyleAttributeName] = make_paragraph(spacing_before=8, spacing_after=8, indent=4)
        elif style == "class:ok":
            attrs[NSForegroundColorAttributeName] = rgb_color(theme["success"])
        elif style == "class:warn":
            attrs[NSForegroundColorAttributeName] = rgb_color(theme["warning"])
        elif style == "class:error":
            attrs[NSForegroundColorAttributeName] = rgb_color(theme["error"])
        elif style == "class:think_label":
            attrs[NSFontAttributeName] = NSFont.systemFontOfSize_weight_(11.5, AppKit.NSFontWeightBold)
            attrs[NSForegroundColorAttributeName] = rgb_color(theme["accent"])
            attrs[AppKit.NSKernAttributeName] = 0.6
            attrs[AppKit.NSParagraphStyleAttributeName] = make_paragraph(spacing_before=10, spacing_after=3, indent=14)
        elif style == "class:think":
            attrs[NSFontAttributeName] = italic_font(13)
            attrs[NSForegroundColorAttributeName] = rgb_color(theme["text_muted"])
            attrs[AppKit.NSParagraphStyleAttributeName] = make_paragraph(line_height=1.3, spacing_after=6, indent=20)
        elif style == "class:spin":
            attrs[NSFontAttributeName] = NSFont.monospacedSystemFontOfSize_weight_(13.5, AppKit.NSFontWeightMedium)
            attrs[NSForegroundColorAttributeName] = rgb_color(theme["accent"])
            attrs[AppKit.NSParagraphStyleAttributeName] = make_paragraph(spacing_before=4, spacing_after=4)
        elif "strong" in style:
            attrs[NSFontAttributeName] = bold
        elif "code" in style:
            attrs[NSFontAttributeName] = mono

        return attrs

    @objc.python_method
    def refreshChatIfNeeded(self):
        self.rebuildMessages()

    @objc.python_method
    def hasUserMessages(self):
        with self.shell._frag_lock:
            return any(b.kind == "user" for b in self.shell.blocks)

    @objc.python_method
    def blocksToMessages(self):
        with self.shell._frag_lock:
            blocks = list(self.shell.blocks)
        items = []
        for b in blocks:
            if b.kind == "user":
                items.append({"role": "user", "title": "You", "body": b.text.strip(), "md": False})
            elif b.kind in ("md", "stream") and b.text.strip():
                items.append({"role": "assistant", "title": "Assistant", "body": b.text, "md": True})
            elif b.kind == "think" and b.text.strip():
                items.append({"role": "thinking", "title": "Thinking", "body": b.text.strip(), "md": False})
            elif b.kind == "spin":
                items.append({"role": "thinking", "title": "Assistant", "body": b.text.strip(), "md": False})
            elif b.kind == "attach":
                items.append({"role": "system", "title": "Attached", "body": b.text.strip(), "md": False})
            elif b.kind == "notify":
                items.append({"role": "system", "title": "Notice", "body": b.text.strip(), "md": False, "style": b.style})
        return items

    @objc.python_method
    def buildWelcomeOverlay(self):
        overlay = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 100, 100))
        overlay.setWantsLayer_(True)
        overlay.setTranslatesAutoresizingMaskIntoConstraints_(False)

        mark = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 64, 64))
        mark.setWantsLayer_(True)
        mark.layer().setCornerRadius_(18.0)
        mark.layer().setBackgroundColor_(rgb_color(THEME["dark"]["accent"]).CGColor())
        mark.setTranslatesAutoresizingMaskIntoConstraints_(False)
        mark_lbl = make_label("HC", 24, AppKit.NSFontWeightBold, NSColor.whiteColor())
        mark.addSubview_(mark_lbl)
        mark_lbl.setTranslatesAutoresizingMaskIntoConstraints_(False)

        self.welcome_title = make_label("How can I help?", 28, AppKit.NSFontWeightBold, NSColor.labelColor())
        self.welcome_sub = make_label("Pick a starting point or just type below.", 14, 0, NSColor.secondaryLabelColor())

        grid = NSStackView.alloc().initWithFrame_(NSMakeRect(0, 0, 560, 120))
        grid.setOrientation_(AppKit.NSUserInterfaceLayoutOrientationVertical)
        grid.setSpacing_(12.0)
        grid.setAlignment_(NSLayoutAttributeCenterX)
        grid.setTranslatesAutoresizingMaskIntoConstraints_(False)
        self.suggestion_cards = []
        for label, prompt in SUGGESTIONS:
            card = make_suggestion_card(self, label, "suggestionClicked:", THEME["dark"])
            card.setToolTip_(prompt)
            grid.addArrangedSubview_(card)
            NSLayoutConstraint.activateConstraints_([
                NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(card, NSLayoutAttributeWidth, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 480),
                NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(card, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 50),
            ])
            self.suggestion_cards.append(card)

        for v in (mark, self.welcome_title, self.welcome_sub, grid):
            overlay.addSubview_(v)

        NSLayoutConstraint.activateConstraints_([
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(mark, NSLayoutAttributeCenterX, NSLayoutRelationEqual, overlay, NSLayoutAttributeCenterX, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(mark, NSLayoutAttributeCenterY, NSLayoutRelationEqual, overlay, NSLayoutAttributeCenterY, 1, -150),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(mark, NSLayoutAttributeWidth, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 64),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(mark, NSLayoutAttributeHeight, NSLayoutRelationEqual, None, NSLayoutAttributeNotAnAttribute, 1, 64),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(mark_lbl, NSLayoutAttributeCenterX, NSLayoutRelationEqual, mark, NSLayoutAttributeCenterX, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(mark_lbl, NSLayoutAttributeCenterY, NSLayoutRelationEqual, mark, NSLayoutAttributeCenterY, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.welcome_title, NSLayoutAttributeTop, NSLayoutRelationEqual, mark, NSLayoutAttributeBottom, 1, 20),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.welcome_title, NSLayoutAttributeCenterX, NSLayoutRelationEqual, overlay, NSLayoutAttributeCenterX, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.welcome_sub, NSLayoutAttributeTop, NSLayoutRelationEqual, self.welcome_title, NSLayoutAttributeBottom, 1, 8),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.welcome_sub, NSLayoutAttributeCenterX, NSLayoutRelationEqual, overlay, NSLayoutAttributeCenterX, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(grid, NSLayoutAttributeTop, NSLayoutRelationEqual, self.welcome_sub, NSLayoutAttributeBottom, 1, 28),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(grid, NSLayoutAttributeCenterX, NSLayoutRelationEqual, overlay, NSLayoutAttributeCenterX, 1, 0),
        ])
        return overlay

    @objc.python_method
    def rebuildMessages(self):
        ver = getattr(self.shell, "_body_ver", 0)
        self._last_render_ver = ver
        theme = self.themeColors()
        has = self.hasUserMessages()
        self.welcome_overlay.setHidden_(has)

        storage = self.chat_view.textStorage()
        storage.beginEditing()
        storage.deleteCharactersInRange_(NSMakeRange(0, storage.length()))
        if has:
            pos = 0
            trailing_nl = 2
            for style, text in self.shell.render_body():
                if not text:
                    continue
                attrs = self.attrsForFragment(style, text, theme)
                if attrs is None:
                    continue
                if text.strip() == "" and "\n" in text:
                    allowed = max(0, 2 - trailing_nl)
                    nl = min(text.count("\n"), allowed)
                    if nl <= 0:
                        continue
                    text = "\n" * nl
                    trailing_nl += nl
                elif text.strip() != "":
                    trailing_nl = len(text) - len(text.rstrip("\n"))
                storage.insertAttributedString_atIndex_(
                    NSAttributedString.alloc().initWithString_attributes_(text, attrs), pos)
                pos += len(text)
        storage.endEditing()
        if self._follow_output and has:
            self.scrollChatToBottom()

    @objc.python_method
    def refreshAttachments(self):
        t = self.themeColors()
        for v in list(self.attach_strip.subviews()):
            v.removeFromSuperview()
        atts = list(self.shell.attachments)
        if not atts:
            self.attach_strip.setHidden_(True)
            self._attach_height.setConstant_(0)
            return
        self.attach_strip.setHidden_(False)
        self._attach_height.setConstant_(48)
        self.attach_strip.setFillColor_(rgb_color(t["elevated"]))
        x = 14
        for a in atts:
            label = f"  {a.name}  "
            chip = make_label(label, 11, AppKit.NSFontWeightSemibold, rgb_color(t["accent"]))
            chip.setWantsLayer_(True)
            chip.setDrawsBackground_(True)
            chip.setBackgroundColor_(rgb_color(t["surface"]))
            chip.layer().setCornerRadius_(8.0)
            w = min(240, 22 + len(a.name) * 7)
            chip.setFrame_(NSMakeRect(x, 12, w, 24))
            self.attach_strip.addSubview_(chip)
            x += w + 8

    @objc.python_method
    def reloadSidebar(self):
        q = (self.search_field.stringValue() or "").strip().lower()
        sessions = list_saved_sessions()  # sorted by most recent reply (updated_at desc)
        current = self.shell.session_id
        rows = []
        seen_current = False
        for s in sessions:
            sid = s.get("id")
            title = session_display_title(data=s)
            if q and q not in title.lower() and q not in sid.lower():
                continue
            is_cur = sid == current
            if is_cur:
                seen_current = True
            rows.append({
                "id": sid,
                "title": title,
                "current": is_cur,
                "subtitle": session_subtitle(s),
                "data": None if is_cur else s,
            })
        if current and not seen_current and not q:
            title = self.shell.display_title() if self.shell.history else "New chat"
            rows.insert(0, {"id": current, "title": title, "current": True, "subtitle": "Just now", "data": None})
        self.filtered_sessions = rows
        self.session_table.reloadData()

    @objc.python_method
    def updateSessionTitle(self):
        if self.shell.history or self.shell.custom_title:
            title = self.shell.display_title()
        else:
            title = "New conversation"
        self.session_title_label.setStringValue_(title[:72])

    @objc.python_method
    def scrollChatToBottom(self):
        length = self.chat_view.textStorage().length()
        self.chat_view.scrollRangeToVisible_(NSMakeRange(max(0, length - 1), 1))

    @objc.python_method
    def filterSessions_(self):
        self.reloadSidebar()

    def suggestionClicked_(self, sender):
        prompt = sender.toolTip() or ""
        if not prompt:
            title = sender.title().strip()
            for label, p in SUGGESTIONS:
                if label == title:
                    prompt = p
                    break
        if prompt:
            self.input_view.setString_(prompt if prompt.endswith(" ") else prompt + " ")
            self.window.makeFirstResponder_(self.input_view)

    def sessionClicked_(self, sender):
        row = self.session_table.clickedRow()
        if row < 0:
            row = self.session_table.selectedRow()
        if row < 0 or row >= len(self.filtered_sessions):
            return
        item = self.filtered_sessions[row]
        if item.get("current"):
            return
        data = item.get("data")
        if not data:
            return
        self.shell.apply_saved_session(data)
        self.shell.restore_session_ui()
        self._last_render_ver = -1
        self.requestRefresh()
        self.syncModelPickers()

    def sessionActivated_(self, sender):
        self.sessionClicked_(sender)

    def renameSessionRow_(self, sender):
        row = self.session_table.clickedRow()
        if row < 0:
            row = self.session_table.selectedRow()
        self.renameSessionAtRow_(row)

    def renameSelectedSession_(self, sender):
        self.renameSessionAtRow_(self.session_table.selectedRow())

    def renameCurrentSession_(self, sender):
        if not self.shell.session_id:
            return
        self.renameSessionAtRow_(-1)

    @objc.python_method
    def renameSessionAtRow_(self, row):
        if row >= 0:
            if row >= len(self.filtered_sessions):
                return
            item = self.filtered_sessions[row]
            current_title = item["title"]
            sid = item["id"]
            is_current = item.get("current")
        else:
            current_title = self.shell.display_title()
            sid = self.shell.session_id
            is_current = True
        new_title = self.prompt_rename(current_title)
        if not new_title or new_title == current_title:
            return
        if is_current:
            self.shell.rename_session(new_title)
        else:
            rename_saved_session(sid, new_title)
        self.reloadSidebar()
        self.updateSessionTitle()

    @objc.python_method
    def prompt_rename(self, current_title):
        return self.showTextDialog(
            "Rename chat",
            "Enter a new name for this conversation.",
            default=current_title,
        )

    @objc.python_method
    def setBusyState(self, busy):
        t = self.themeColors()
        self.send_btn.setEnabled_(not busy)
        self.send_btn.setHidden_(busy)
        self.stop_btn.setEnabled_(busy)
        self.stop_btn.setHidden_(not busy)
        style_pill_button(self.send_btn, t, accent=True, enabled=not busy)
        style_pill_button(self.stop_btn, t, accent=False, enabled=busy)
        self.model_popup.setEnabled_(not busy)
        self.reasoning_popup.setEnabled_(not busy)
        self.attach_btn.setEnabled_(not busy)
        if not busy:
            self.window.makeFirstResponder_(self.input_view)

    # --- Input ---

    def onInputChanged_(self, sender):
        if self._slash_timer:
            self._slash_timer.cancel()
        self._slash_timer = threading.Timer(0.12, lambda: AppHelper.callAfter(self.updateSlashPanel))
        self._slash_timer.daemon = True
        self._slash_timer.start()

    def sendClicked_(self, sender):
        if self.shell.busy:
            return
        raw = self.input_view.string()
        line = normalize_input(raw)
        if not line:
            return
        self.input_view.setString_("")
        self.hideSlashPanel()
        self._follow_output = True
        self.shell.submit_line(line)
        self.window.makeFirstResponder_(self.input_view)

    def stopClicked_(self, sender):
        self.shell.stop_generation()

    def attachClicked_(self, sender):
        path = pick_macos_path("file")
        if path:
            self.shell.attach(path)

    def attachFile_(self, sender):
        path = pick_macos_path("file")
        if path:
            self.shell.attach(path)

    def exportChat_(self, sender):
        self.shell.export_chat("")

    def newSession_(self, sender):
        self.shell.begin_session()
        self.shell.show_welcome()
        self._last_render_ver = -1
        self.requestRefresh()
        self.reloadSidebar()

    def clearAllSessions_(self, sender):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Remove all chats?")
        alert.setInformativeText_("This permanently deletes every saved conversation. This cannot be undone.")
        alert.addButtonWithTitle_("Remove All")
        alert.addButtonWithTitle_("Cancel")
        if alert.runModal() != NSAlertFirstButtonReturn:
            return
        delete_all_sessions()
        self.shell.begin_session()
        self.shell.show_welcome()
        self._last_render_ver = -1
        self.requestRefresh()
        self.reloadSidebar()

    def resumeSession_(self, sender):
        data = self.showSessionDialog(None)
        if data:
            self.shell.apply_saved_session(data)
            self.shell.restore_session_ui()
            self._last_render_ver = -1
            self.requestRefresh()

    def themeDark_(self, sender):
        self.shell.apply_theme("dark")

    def themeLight_(self, sender):
        self.shell.apply_theme("light")

    def toggleCompact_(self, sender):
        self.shell.compact = not self.shell.compact
        self._last_render_ver = -1
        self.requestRefresh()

    def showAbout_(self, sender):
        alert = NSAlert.alloc().init()
        alert.setMessageText_(APP_NAME)
        alert.setInformativeText_(
            "A polished native chat experience for the Hack Club AI proxy.\n\n"
            "Choose your model, attach files, and chat — all from a real macOS app."
        )
        alert.runModal()

    def showSettings_(self, sender):
        if not getattr(self, "settings", None):
            self.settings = SettingsController.alloc().initWithShell_ui_(self.shell, self)
        self.settings.showWindow_(self)

    def windowShouldClose_(self, sender):
        self.shell.exit_cmd()
        return False

    def attachFolder_(self, sender):
        path = pick_macos_path("folder")
        if path:
            self.shell.attach(path)

    # --- Slash commands ---

    @objc.python_method
    def slashEntries(self, text):
        line = (text or "").split("\n")[-1].strip()
        if not line.startswith("/"):
            return []
        if " " in line and not line.startswith("/model"):
            return []
        if line == "/model" or line.startswith("/model "):
            q = line[len("/model"):].strip()
            parsed = parse_model_command(q)
            if parsed["kind"] == "variants":
                return [{"insert": f"/model {parsed['display']} {label}", "label": label, "desc": f"effort={effort}"}
                        for label, effort in reasoning_variants_for_model(parsed["model_id"])]
            ql = parsed.get("filter", q.lower())
            return [{"insert": f"/model {name}" if mid != "custom" else "/model custom", "label": name, "desc": mid}
                    for name, mid in MODELS if not ql or ql in name.lower() or ql in mid.lower()]
        if line in COMMANDS:
            return []
        return [{"insert": cmd, "label": cmd, "desc": CMD_DESCRIPTIONS.get(cmd, "")}
                for cmd in sorted(COMMANDS) if cmd.startswith(line.lower())]

    @objc.python_method
    def updateSlashPanel(self):
        entries = self.slashEntries(self.input_view.string())
        self.slash_items = entries
        if not entries:
            self.hideSlashPanel()
            return
        self.slash_table.reloadData()
        self._slash_height.setConstant_(156)
        self.slash_panel.setHidden_(False)

    @objc.python_method
    def hideSlashPanel(self):
        self._slash_height.setConstant_(0)
        self.slash_panel.setHidden_(True)

    def slashSelected_(self, sender):
        row = self.slash_table.selectedRow()
        if row < 0 or row >= len(self.slash_items):
            return
        self.input_view.setString_(self.slash_items[row]["insert"] + " ")
        self.hideSlashPanel()
        self.window.makeFirstResponder_(self.input_view)

    def numberOfRowsInTableView_(self, table):
        if table is self.session_table:
            return len(self.filtered_sessions)
        return len(self.slash_items)

    def tableView_viewForTableColumn_row_(self, table, column, row):
        t = self.themeColors()
        if table is self.session_table:
            if row < 0 or row >= len(self.filtered_sessions):
                return None
            item = self.filtered_sessions[row]
            return make_session_row_view(item, t)
        if row < 0 or row >= len(self.slash_items):
            return None
        return make_slash_row_view(self.slash_items[row], t)

    def tableView_rowViewForRow_(self, table, row):
        rv = HCTableRowView.alloc().init()
        return rv

    def tableView_menuForEvent_(self, table, event):
        if table is not self.session_table:
            return None
        pt = table.convertPoint_fromView_(event.locationInWindow(), None)
        row = table.rowAtPoint_(pt)
        if row < 0 or row >= len(self.filtered_sessions):
            return None
        table.selectRowIndexes_byExtendingSelection_(AppKit.NSIndexSet.indexSetWithIndex_(row), False)
        menu = NSMenu.alloc().init()
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Rename…", "renameSelectedSession:", "")
        item.setTarget_(self)
        menu.addItem_(item)
        return menu

    def tableView_objectValueForTableColumn_row_(self, table, column, row):
        return ""

    # --- Dialogs ---

    @objc.python_method
    def showTextDialog(self, title, prompt, default=""):
        alert = NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(prompt)
        field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 380, 28))
        field.setFont_(NSFont.systemFontOfSize_(14))
        field.setStringValue_(default or "")
        alert.setAccessoryView_(field)
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")
        if alert.runModal() != NSAlertFirstButtonReturn:
            return ""
        return field.stringValue().strip()

    @objc.python_method
    def showAttachDialog(self):
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Attach to conversation")
        alert.setInformativeText_("Include a file or folder in the model context.")
        alert.addButtonWithTitle_("File")
        alert.addButtonWithTitle_("Folder")
        alert.addButtonWithTitle_("Cancel")
        resp = alert.runModal()
        if resp == NSAlertFirstButtonReturn:
            kind = "file"
        elif resp == 1001:
            kind = "folder"
        else:
            return None, None
        return kind, pick_macos_path(kind)

    @objc.python_method
    def showSessionDialog(self, session_id):
        if session_id:
            from hackclub_ai import pick_saved_session as core_pick
            return core_pick(session_id)
        sessions = list_saved_sessions()
        if not sessions:
            NSAlert.alloc().init().runModal()
            return None
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Resume session")
        alert.setInformativeText_("\n".join(format_session_line(s, i) for i, s in enumerate(sessions[:15], 1)))
        field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 420, 28))
        alert.setAccessoryView_(field)
        alert.addButtonWithTitle_("OK")
        alert.addButtonWithTitle_("Cancel")
        if alert.runModal() != NSAlertFirstButtonReturn:
            return None
        val = field.stringValue().strip()
        if val.isdigit():
            idx = int(val) - 1
            if 0 <= idx < len(sessions[:15]):
                return sessions[idx]
        return None

    @objc.python_method
    def quitApp(self):
        AppKit.NSApp.terminate_(None)


class SettingsController(NSObject):
    shell = objc.ivar("shell")
    ui = objc.ivar("ui")
    window = objc.ivar("window")
    hc_field = objc.ivar("hc_field")
    composio_field = objc.ivar("composio_field")

    def initWithShell_ui_(self, shell, ui):
        self = objc.super(SettingsController, self).init()
        if self is None:
            return None
        self.shell = shell
        self.ui = ui
        self.buildSettingsWindow()
        return self

    @objc.python_method
    def buildSettingsWindow(self):
        w, h = 520, 400
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, w, h),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskFullSizeContentView,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("Settings")
        self.window.setReleasedWhenClosed_(False)
        self.window.setTitlebarAppearsTransparent_(True)
        self.window.setBackgroundColor_(rgb_color(THEME["dark"]["window"]))

        content = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, w, h))
        content.setWantsLayer_(True)
        content.layer().setBackgroundColor_(rgb_color(THEME["dark"]["window"]).CGColor())

        title = make_label("Settings", 22, AppKit.NSFontWeightBold, NSColor.labelColor())
        hint = make_label("Keys are stored locally at ~/.hackclub-ai/config.json", 12, 0, NSColor.secondaryLabelColor())

        hc_label = make_label("Hack Club API Key", 13, AppKit.NSFontWeightSemibold, NSColor.labelColor())
        self.hc_field = NSSecureTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 460, 32))
        self.hc_field.setFont_(NSFont.monospacedSystemFontOfSize_weight_(13, 0))
        self.hc_field.setTranslatesAutoresizingMaskIntoConstraints_(False)

        comp_label = make_label("Composio API Key (optional)", 13, AppKit.NSFontWeightSemibold, NSColor.labelColor())
        self.composio_field = NSSecureTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 460, 32))
        self.composio_field.setFont_(NSFont.monospacedSystemFontOfSize_weight_(13, 0))
        self.composio_field.setTranslatesAutoresizingMaskIntoConstraints_(False)

        appearance_label = make_label("Appearance", 13, AppKit.NSFontWeightSemibold, NSColor.labelColor())
        dark_btn = make_pill_button(self, "Dark", "settingsThemeDark:", accent=True)
        light_btn = make_pill_button(self, "Light", "settingsThemeLight:", accent=False)
        compact_btn = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, 200, 24))
        compact_btn.setButtonType_(AppKit.NSSwitchButton)
        compact_btn.setTitle_("Compact message view")
        compact_btn.setState_(AppKit.NSControlStateValueOn if self.shell.compact else AppKit.NSControlStateValueOff)
        compact_btn.setTarget_(self)
        compact_btn.setAction_("toggleCompactSetting:")
        compact_btn.setTranslatesAutoresizingMaskIntoConstraints_(False)

        save_btn = make_pill_button(self, "Save", "saveSettings:", accent=True)
        cancel_btn = make_pill_button(self, "Cancel", "closeWindow:", accent=False)
        self.save_btn = save_btn
        self.cancel_btn = cancel_btn

        for v in (title, hint, hc_label, self.hc_field, comp_label, self.composio_field,
                  appearance_label, dark_btn, light_btn, compact_btn, save_btn, cancel_btn):
            content.addSubview_(v)

        NSLayoutConstraint.activateConstraints_([
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(title, NSLayoutAttributeTop, NSLayoutRelationEqual, content, NSLayoutAttributeTop, 1, 52),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(title, NSLayoutAttributeLeading, NSLayoutRelationEqual, content, NSLayoutAttributeLeading, 1, 28),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(hint, NSLayoutAttributeTop, NSLayoutRelationEqual, title, NSLayoutAttributeBottom, 1, 6),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(hint, NSLayoutAttributeLeading, NSLayoutRelationEqual, title, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(hc_label, NSLayoutAttributeTop, NSLayoutRelationEqual, hint, NSLayoutAttributeBottom, 1, 28),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(hc_label, NSLayoutAttributeLeading, NSLayoutRelationEqual, title, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.hc_field, NSLayoutAttributeTop, NSLayoutRelationEqual, hc_label, NSLayoutAttributeBottom, 1, 8),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.hc_field, NSLayoutAttributeLeading, NSLayoutRelationEqual, title, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.hc_field, NSLayoutAttributeTrailing, NSLayoutRelationEqual, content, NSLayoutAttributeTrailing, 1, -28),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(comp_label, NSLayoutAttributeTop, NSLayoutRelationEqual, self.hc_field, NSLayoutAttributeBottom, 1, 20),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(comp_label, NSLayoutAttributeLeading, NSLayoutRelationEqual, title, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.composio_field, NSLayoutAttributeTop, NSLayoutRelationEqual, comp_label, NSLayoutAttributeBottom, 1, 8),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.composio_field, NSLayoutAttributeLeading, NSLayoutRelationEqual, title, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(self.composio_field, NSLayoutAttributeTrailing, NSLayoutRelationEqual, content, NSLayoutAttributeTrailing, 1, -28),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(appearance_label, NSLayoutAttributeTop, NSLayoutRelationEqual, self.composio_field, NSLayoutAttributeBottom, 1, 20),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(appearance_label, NSLayoutAttributeLeading, NSLayoutRelationEqual, title, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(dark_btn, NSLayoutAttributeTop, NSLayoutRelationEqual, appearance_label, NSLayoutAttributeBottom, 1, 8),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(dark_btn, NSLayoutAttributeLeading, NSLayoutRelationEqual, title, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(light_btn, NSLayoutAttributeCenterY, NSLayoutRelationEqual, dark_btn, NSLayoutAttributeCenterY, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(light_btn, NSLayoutAttributeLeading, NSLayoutRelationEqual, dark_btn, NSLayoutAttributeTrailing, 1, 10),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(compact_btn, NSLayoutAttributeTop, NSLayoutRelationEqual, dark_btn, NSLayoutAttributeBottom, 1, 10),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(compact_btn, NSLayoutAttributeLeading, NSLayoutRelationEqual, title, NSLayoutAttributeLeading, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(cancel_btn, NSLayoutAttributeBottom, NSLayoutRelationEqual, content, NSLayoutAttributeBottom, 1, -24),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(cancel_btn, NSLayoutAttributeTrailing, NSLayoutRelationEqual, content, NSLayoutAttributeTrailing, 1, -28),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(save_btn, NSLayoutAttributeCenterY, NSLayoutRelationEqual, cancel_btn, NSLayoutAttributeCenterY, 1, 0),
            NSLayoutConstraint.constraintWithItem_attribute_relatedBy_toItem_attribute_multiplier_constant_(save_btn, NSLayoutAttributeTrailing, NSLayoutRelationEqual, cancel_btn, NSLayoutAttributeLeading, 1, -10),
        ])
        theme = THEME["dark"]
        style_pill_button(save_btn, theme, accent=True)
        style_pill_button(cancel_btn, theme, accent=False)
        style_pill_button(dark_btn, theme, accent=True)
        style_pill_button(light_btn, theme, accent=False)
        self.window.setContentView_(content)

    def showWindow_(self, sender):
        self.hc_field.setStringValue_(load_api_key())
        self.composio_field.setStringValue_(load_composio_key())
        self.window.center()
        self.window.makeKeyAndOrderFront_(None)

    def closeWindow_(self, sender):
        self.window.orderOut_(None)

    def settingsThemeDark_(self, sender):
        self.shell.apply_theme("dark")
        self.ui.apply_theme("dark")

    def settingsThemeLight_(self, sender):
        self.shell.apply_theme("light")
        self.ui.apply_theme("light")

    def toggleCompactSetting_(self, sender):
        self.shell.compact = sender.state() == AppKit.NSControlStateValueOn
        self.ui._last_render_ver = -1
        self.ui.requestRefresh()

    def saveSettings_(self, sender):
        hc = self.hc_field.stringValue().strip()
        if not hc:
            return
        self.shell.update_api_key(hc)
        self.shell.update_composio_key(self.composio_field.stringValue().strip())
        self.ui.postOkMessage_("Settings saved")
        self.ui._last_render_ver = -1
        self.ui.requestRefresh()
        self.window.orderOut_(None)


class AppDelegate(NSObject):
    def applicationShouldTerminateAfterLastWindowClosed_(self, sender):
        return True


def api_key_startup_dialog():
    alert = NSAlert.alloc().init()
    alert.setMessageText_("Welcome to HackClub AI")
    alert.setInformativeText_(
        "Enter your Hack Club AI API key from https://ai.hackclub.com\n\n"
        "Your key stays on this Mac — never shared."
    )
    field = NSSecureTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 420, 28))
    field.setPlaceholderString_("sk-hc-v1-...")
    field.setFont_(NSFont.monospacedSystemFontOfSize_weight_(13, 0))
    alert.setAccessoryView_(field)
    alert.addButtonWithTitle_("Get Started")
    alert.addButtonWithTitle_("Quit")
    if alert.runModal() != NSAlertFirstButtonReturn:
        return None
    return field.stringValue().strip() or None


def prompt_for_api_key():
    existing = load_api_key()
    if existing:
        return existing
    key = api_key_startup_dialog()
    if key:
        save_api_key(key)
    return key


def main(argv=None):
    if sys.platform != "darwin":
        raise SystemExit(f"{APP_NAME} requires macOS.")

    app = NSApplication.sharedApplication()
    setup_app_branding(app)
    app.setDelegate_(AppDelegate.alloc().init())

    api_key = prompt_for_api_key()
    if not api_key:
        raise SystemExit("API key required. Relaunch to enter your key.")

    args = parse_cli_args(list(argv) if argv is not None else sys.argv[1:])
    shell = Shell(api_key=api_key)
    ui = MacChatUI.alloc().initWithShell_(shell)
    shell.ui_delegate = ui

    resumed = False
    pending = args["prompt"].strip() if args["prompt"] else ""
    if args["resume"] is not None:
        data = pick_saved_session(args["resume"]) if args["resume"] else ui.pick_session(None)
        if data:
            shell.apply_saved_session(data)
            resumed = True
        else:
            shell.begin_session()
    else:
        shell.begin_session()

    def boot():
        if resumed:
            shell.restore_session_ui()
        else:
            shell.show_welcome()
        ui._last_render_ver = -1
        ui.requestRefresh()
        if pending:
            shell.submit_line(normalize_input(pending))

    ui.activateMainWindow(on_ready=boot)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        log = os.path.expanduser("~/Library/Logs/HackClub-AI.log")
        try:
            with open(log, "a", encoding="utf-8") as f:
                f.write(traceback.format_exc() + "\n")
        except Exception:
            pass
        try:
            alert = NSAlert.alloc().init()
            alert.setMessageText_("HackClub AI crashed")
            alert.setInformativeText_(f"{e}\n\nSee {log}")
            alert.runModal()
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
        raise SystemExit(1)
