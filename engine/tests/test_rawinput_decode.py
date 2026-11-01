import importlib

from siegesense_engine.input.events import Button, Key, MouseMove
from siegesense_engine.input.rawinput import decode_keyboard, decode_mouse


def test_module_imports_on_linux():
    importlib.import_module("siegesense_engine.input.rawinput")


def test_relative_move():
    assert decode_mouse(1.0, 0x00, 0, 5, -3) == [MouseMove(1.0, 5, -3)]


def test_absolute_move_ignored():
    assert decode_mouse(1.0, 0x01, 0, 30000, 20000) == []


def test_zero_move_ignored():
    assert decode_mouse(1.0, 0x00, 0, 0, 0) == []


def test_buttons_down_up():
    events = decode_mouse(2.0, 0x00, 0x0001 | 0x0008, 0, 0)
    assert events == [Button(2.0, "left", True), Button(2.0, "right", False)]


def test_move_and_button_same_packet():
    events = decode_mouse(2.0, 0x00, 0x0010, 1, 1)
    assert events == [MouseMove(2.0, 1, 1), Button(2.0, "middle", True)]


def test_side_buttons():
    events = decode_mouse(2.0, 0, 0x0040 | 0x0200, 0, 0)
    assert events == [Button(2.0, "x1", True), Button(2.0, "x2", False)]


def test_key_down_up():
    assert decode_keyboard(3.0, 0x41, 0x00) == Key(3.0, 0x41, True)
    assert decode_keyboard(3.0, 0x41, 0x01) == Key(3.0, 0x41, False)


def test_fake_vkey_ignored():
    assert decode_keyboard(3.0, 0xFF, 0) is None
