"""Windows Raw Input reader.

Reads the player's own mouse and keyboard with ``RIDEV_INPUTSINK``, so input keeps flowing
while Siege (not SiegeSense) has focus. It only *reads* input: nothing is ever sent to the
game, and the game process is never touched.

The decode helpers are pure and tested on every OS; the reader thread only runs on Windows.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
import time

from .events import Button, ButtonName, InputEvent, Key, MouseMove
from .source import InputUnavailable, Sink

log = logging.getLogger(__name__)

MOUSE_MOVE_ABSOLUTE = 0x01
RI_KEY_BREAK = 0x01
_BUTTON_FLAGS: list[tuple[int, ButtonName, bool]] = [
    (0x0001, "left", True),
    (0x0002, "left", False),
    (0x0004, "right", True),
    (0x0008, "right", False),
    (0x0010, "middle", True),
    (0x0020, "middle", False),
    (0x0040, "x1", True),
    (0x0080, "x1", False),
    (0x0100, "x2", True),
    (0x0200, "x2", False),
]


def decode_mouse(
    t: float, flags: int, button_flags: int, last_x: int, last_y: int
) -> list[InputEvent]:
    events: list[InputEvent] = []
    if not flags & MOUSE_MOVE_ABSOLUTE and (last_x or last_y):
        events.append(MouseMove(t, last_x, last_y))
    for bit, name, down in _BUTTON_FLAGS:
        if button_flags & bit:
            events.append(Button(t, name, down))
    return events


def decode_keyboard(t: float, vkey: int, flags: int) -> Key | None:
    if vkey == 0xFF:  # fake key from escaped scan code sequences
        return None
    return Key(t, vkey, not flags & RI_KEY_BREAK)


class RawInputSource:
    """Reads Raw Input on a dedicated thread with a hidden message-only window."""

    reason: str | None = None
    error: str | None = None  # set when the reader thread stops unexpectedly

    def __init__(self) -> None:
        self.available = sys.platform == "win32"
        if not self.available:
            self.reason = "Input tracking works on Windows only"
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None

    def start(self, sink: Sink) -> None:
        if not self.available:
            raise InputUnavailable(self.reason or "unavailable")
        self.error = None
        self._stopping = False
        ready = threading.Event()
        error: list[str] = []
        self._thread = threading.Thread(
            target=_run_reader, args=(sink, ready, error, self), daemon=True, name="raw-input"
        )
        self._thread.start()
        if not ready.wait(timeout=5):
            raise InputUnavailable("Raw input reader did not start in time")
        if error:
            raise InputUnavailable(error[0])

    def stop(self) -> None:
        self._stopping = True
        if self._thread is None or self._thread_id is None:
            return
        _win32().user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT
        self._thread.join(timeout=2)
        self._thread = None
        self._thread_id = None


# --- Windows plumbing (only imported/used on win32) --------------------------------------


class _Win32:
    def __init__(self) -> None:
        from ctypes import wintypes as w

        self.w = w
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class RAWINPUTDEVICE(ctypes.Structure):
            _fields_ = [
                ("usUsagePage", w.USHORT),
                ("usUsage", w.USHORT),
                ("dwFlags", w.DWORD),
                ("hwndTarget", w.HWND),
            ]

        class RAWINPUTHEADER(ctypes.Structure):
            _fields_ = [
                ("dwType", w.DWORD),
                ("dwSize", w.DWORD),
                ("hDevice", w.HANDLE),
                ("wParam", w.WPARAM),
            ]

        class RAWMOUSE(ctypes.Structure):
            _fields_ = [
                ("usFlags", w.USHORT),
                ("_pad", w.USHORT),  # union below is ULONG-aligned
                ("usButtonFlags", w.USHORT),
                ("usButtonData", w.USHORT),
                ("ulRawButtons", w.ULONG),
                ("lLastX", w.LONG),
                ("lLastY", w.LONG),
                ("ulExtraInformation", w.ULONG),
            ]

        class RAWKEYBOARD(ctypes.Structure):
            _fields_ = [
                ("MakeCode", w.USHORT),
                ("Flags", w.USHORT),
                ("Reserved", w.USHORT),
                ("VKey", w.USHORT),
                ("Message", w.UINT),
                ("ExtraInformation", w.ULONG),
            ]

        self.RAWINPUTDEVICE = RAWINPUTDEVICE
        self.RAWINPUTHEADER = RAWINPUTHEADER
        self.RAWMOUSE = RAWMOUSE
        self.RAWKEYBOARD = RAWKEYBOARD

        u = self.user32
        u.CreateWindowExW.argtypes = [
            w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID,
        ]  # fmt: skip
        u.CreateWindowExW.restype = w.HWND
        u.DestroyWindow.argtypes = [w.HWND]
        u.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), w.UINT, w.UINT]
        u.RegisterRawInputDevices.restype = w.BOOL
        u.GetRawInputData.argtypes = [
            w.HANDLE, w.UINT, w.LPVOID, ctypes.POINTER(w.UINT), w.UINT,
        ]  # fmt: skip
        u.GetRawInputData.restype = w.UINT
        u.GetMessageW.argtypes = [ctypes.POINTER(w.MSG), w.HWND, w.UINT, w.UINT]
        u.GetMessageW.restype = w.BOOL
        u.TranslateMessage.argtypes = [ctypes.POINTER(w.MSG)]
        u.DispatchMessageW.argtypes = [ctypes.POINTER(w.MSG)]
        u.PostThreadMessageW.argtypes = [w.DWORD, w.UINT, w.WPARAM, w.LPARAM]
        self.kernel32.GetCurrentThreadId.restype = w.DWORD


_WIN32: _Win32 | None = None


def _win32() -> _Win32:
    global _WIN32
    if _WIN32 is None:
        _WIN32 = _Win32()
    return _WIN32


WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
RIDEV_REMOVE = 0x00000001
RIM_TYPEMOUSE = 0
RIM_TYPEKEYBOARD = 1
HWND_MESSAGE = -3


def _register(win: _Win32, hwnd, flags: int) -> bool:
    devices = (win.RAWINPUTDEVICE * 2)(
        win.RAWINPUTDEVICE(0x01, 0x02, flags, hwnd),  # generic desktop / mouse
        win.RAWINPUTDEVICE(0x01, 0x06, flags, hwnd),  # generic desktop / keyboard
    )
    return bool(win.user32.RegisterRawInputDevices(devices, 2, ctypes.sizeof(win.RAWINPUTDEVICE)))


def _run_reader(
    sink: Sink, ready: threading.Event, error: list[str], owner: RawInputSource
) -> None:
    win = _win32()
    w = win.w
    owner._thread_id = win.kernel32.GetCurrentThreadId()
    hwnd = win.user32.CreateWindowExW(
        0, "STATIC", "SiegeSenseRawInput", 0, 0, 0, 0, 0, w.HWND(HWND_MESSAGE), None, None, None
    )
    if not hwnd:
        error.append(f"Could not create input window (error {ctypes.get_last_error()})")
        ready.set()
        return
    if not _register(win, hwnd, RIDEV_INPUTSINK):
        error.append(f"Windows refused raw input registration (error {ctypes.get_last_error()})")
        win.user32.DestroyWindow(hwnd)
        ready.set()
        return
    ready.set()

    header_size = ctypes.sizeof(win.RAWINPUTHEADER)
    buf = ctypes.create_string_buffer(256)
    msg = w.MSG()
    try:
        while (status := win.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)) > 0:
            if msg.message == WM_INPUT:
                try:
                    _handle_input(win, msg.lParam, buf, header_size, sink)
                except Exception:
                    log.exception("raw input decode failed")
            win.user32.TranslateMessage(ctypes.byref(msg))
            win.user32.DispatchMessageW(ctypes.byref(msg))  # lets Windows clean up WM_INPUT
        if status < 0 and not getattr(owner, "_stopping", False):
            owner.error = f"Raw input reader stopped (error {ctypes.get_last_error()})"
    except Exception as exc:
        owner.error = f"Raw input reader crashed: {exc}"
        log.exception("raw input reader crashed")
    finally:
        _register(win, None, RIDEV_REMOVE)
        win.user32.DestroyWindow(hwnd)


def _handle_input(win: _Win32, lparam, buf, header_size: int, sink: Sink) -> None:
    w = win.w
    size = w.UINT(0)
    handle = w.HANDLE(lparam)
    win.user32.GetRawInputData(handle, RID_INPUT, None, ctypes.byref(size), header_size)
    if size.value > len(buf):
        buf = ctypes.create_string_buffer(size.value)
    got = win.user32.GetRawInputData(handle, RID_INPUT, buf, ctypes.byref(size), header_size)
    if got == 0xFFFFFFFF or got == 0:
        return
    t = time.perf_counter()
    header = win.RAWINPUTHEADER.from_buffer_copy(buf, 0)
    if header.dwType == RIM_TYPEMOUSE:
        m = win.RAWMOUSE.from_buffer_copy(buf, header_size)
        for e in decode_mouse(t, m.usFlags, m.usButtonFlags, m.lLastX, m.lLastY):
            sink(e)
    elif header.dwType == RIM_TYPEKEYBOARD:
        k = win.RAWKEYBOARD.from_buffer_copy(buf, header_size)
        key = decode_keyboard(t, k.VKey, k.Flags)
        if key is not None:
            sink(key)
