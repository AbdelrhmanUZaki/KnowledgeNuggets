#!/usr/bin/env python3
"""Multi-finger touchpad gestures + click mapping for the river-classic session.

    physical click, 1 finger   -> left click
    physical click, 2 fingers  -> right click
    physical click, 3+ fingers -> right click
    3-finger tap               -> back    (BTN_SIDE)
    4-finger tap               -> forward (BTN_EXTRA)
    3-finger swipe up / down   -> volume up / down (wpctl, 3% per step)

Neither river nor libinput can express all of this.  libinput's clickfinger
method is hard-coded to 1 = left, 2 = right, 3 = middle, and river exposes no
button remap.  libinput also ignores every non-left button coming from a
clickpad, so simply forwarding a synthetic right button is not possible.

The daemon therefore mirrors the touchpad as a *non-clickpad* uinput touchpad:

    physical touchpad --EVIOCGRAB--> gestures.py --uinput--> river/libinput

While it runs, river sees the clone instead of the physical pad.  The clone
keeps every capability of the original (MT slots, pressure/size, absinfo,
properties except INPUT_PROP_BUTTONPAD) so libinput still does pointer
acceleration, palm rejection, disable-while-typing, tap-to-click, 2-finger
scrolling and tap-and-drag.  Only the physical button events are translated
(1 finger = left, 2+ = right) before they reach the clone.  Everything else,
including 1/2-finger taps, remains libinput's job.

The physical pad is grabbed only after river has adopted the clone, and the
grab is released automatically when this process dies (the kernel drops the
grab on close), so a crash can never leave a dead touchpad.  If the clone
cannot be created or adopted, the daemon keeps running in gestures-only mode:
taps/swipes still work and physical clicks stay exactly as libinput made them.

1- and 2-finger *taps* are left to libinput (`tap enabled`): it already maps
them to left/right, and only it knows about palm rejection and
disable-while-typing.  That is also why a 3-finger tap still emits libinput's
middle click in addition to the back action -- unavoidable without giving up
libinput's tap handling, which would hurt far more.

Requires read access to the touchpad and write access to /dev/uinput; install
`udev/70-river-classic-input.rules` (see README) or run as root.

Usage:
    gestures.py [--parent PID]   run (3-finger tap back, 4-finger tap forward,
                                 3-finger swipe volume, 3-finger click right)
    gestures.py --gestures-only  no clone/grab: taps + swipes only
    gestures.py --selftest       feed synthetic event streams through the engine
    gestures.py --off            restore stock clickfinger and exit
"""

import fcntl
import glob
import os
import select
import signal
import struct
import subprocess
import sys
import time

# ── input-event codes ────────────────────────────────────────────────────────
EV_SYN, EV_KEY, EV_REL, EV_ABS, EV_MSC = 0x00, 0x01, 0x02, 0x03, 0x04
EV_SW, EV_LED, EV_SND, EV_FF = 0x05, 0x11, 0x12, 0x15
EV_MAX = 0x1F
SYN_REPORT, SYN_DROPPED = 0x00, 0x03
BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 0x110, 0x111, 0x112
BTN_SIDE, BTN_EXTRA = 0x113, 0x114
ABS_MT_SLOT, ABS_MT_POSITION_X, ABS_MT_POSITION_Y = 0x2F, 0x35, 0x36
ABS_MT_TRACKING_ID = 0x39
INPUT_PROP_POINTER, INPUT_PROP_BUTTONPAD = 0x00, 0x01
INPUT_PROP_MAX = 0x1F

EVENT_FMT = "<qqHHi"                     # struct input_event (24 bytes on LP64)
EVENT_SIZE = struct.calcsize(EVENT_FMT)
INPUT_ID_FMT = "<HHHH"                   # struct input_id (8 bytes)


# ── ioctl helpers ────────────────────────────────────────────────────────────
def _IOC(direction, type_, nr, size):
    return (direction << 30) | (size << 16) | (ord(type_) << 8) | nr


def _IOW(type_, nr, size):
    return _IOC(1, type_, nr, size)


def _IOR(type_, nr, size):
    return _IOC(2, type_, nr, size)


EVIOCGBIT = lambda ev, size: _IOR("E", 0x20 + ev, size)
EVIOCGPROP = lambda size: _IOR("E", 0x09, size)
EVIOCGABS = lambda code: _IOR("E", 0x40 + code, 24)
EVIOCGID = _IOR("E", 0x02, 8)
EVIOCGNAME = lambda size: _IOR("E", 0x06, size)
EVIOCGRAB = _IOW("E", 0x90, 4)

UI_SET_EVBIT = _IOW("U", 100, 4)
UI_SET_KEYBIT = _IOW("U", 101, 4)
UI_SET_RELBIT = _IOW("U", 102, 4)
UI_SET_MSCBIT = _IOW("U", 104, 4)
UI_SET_LEDBIT = _IOW("U", 105, 4)
UI_SET_SNDBIT = _IOW("U", 106, 4)
UI_SET_FFBIT = _IOW("U", 107, 4)
UI_SET_SWBIT = _IOW("U", 109, 4)
UI_SET_PROPBIT = _IOW("U", 110, 4)
UI_DEV_SETUP = _IOW("U", 3, 92)          # struct uinput_setup
UI_ABS_SETUP = _IOW("U", 4, 28)          # struct uinput_abs_setup
UI_DEV_CREATE = (ord("U") << 8) | 1      # _IO('U', 1)
UI_DEV_DESTROY = (ord("U") << 8) | 2     # _IO('U', 2)

# ── tunables ─────────────────────────────────────────────────────────────────
TAP_MAX_S = 0.45           # whole gesture must be shorter than this
TAP_MOVE_FRAC = 0.020      # ... and no finger may wander more than 2% of the pad
SWIPE_MIN_FRAC = 0.030     # vertical travel that turns a touch into a swipe
SWIPE_STEP_FRAC = 0.080    # pad travel per volume step
SWIPE_LOCK = 1.6           # |dy| must exceed this * |dx|
SWIPE_HOLD_S = 0.040       # minimum time between volume steps
MAX_STEPS_PER_FRAME = 4
VOLUME_STEP = 3            # percent per step
TAP_ACTIONS = {3: "back", 4: "forward"}

STATE = os.path.join(os.environ.get("XDG_STATE_HOME",
                                    os.path.expanduser("~/.local/state")),
                     "river-classic")
RIVERCTL = next((p for p in (os.path.expanduser("~/.local/bin/riverctl"),
                             "/usr/bin/riverctl", "/usr/local/bin/riverctl")
                 if os.path.exists(p)), "riverctl")

ABS_MAX = {EV_KEY: 0x300, EV_REL: 0x10, EV_ABS: 0x40, EV_MSC: 0x08,
           EV_SW: 0x11, EV_LED: 0x10, EV_SND: 0x08, EV_FF: 0x80}


def bits(fd, ev, nbits):
    """set bits from EVIOCGBIT(ev) as a list of code numbers"""
    size = (nbits + 7) // 8
    buf = fcntl.ioctl(fd, EVIOCGBIT(ev, size), b"\0" * size)
    return [i for i in range(nbits) if buf[i // 8] & (1 << (i % 8))]


def absinfo(fd, code):
    buf = fcntl.ioctl(fd, EVIOCGABS(code), b"\0" * 24)
    return struct.unpack("<6i", buf)     # value, min, max, fuzz, flat, res


def button_for_fingers(count):
    """physical click map: 1 = left, 2+ = right (the user's preference)"""
    return BTN_LEFT if count <= 1 else BTN_RIGHT


# ── the gesture engine (pure: feed ABS events -> high-level actions) ─────────
class Engine:
    """Turns a raw touchpad event stream into tap/swipe actions.

    actions: ("tap", "back"|"forward")
             ("volume", +1|-1)          one volume step
    """

    def __init__(self, x_range=1000, y_range=1000):
        self.x_range = max(200, x_range)
        self.y_range = max(200, y_range)
        self.reset()

    def reset(self):
        self.slot = 0
        self.slots = {}          # slot -> [start_x, start_y, x, y]
        self.started = None
        self.max_count = 0
        self.worst_move = 0.0
        self.saw_click = False
        self.swiping = False
        self.swipe_x0 = None
        self.swipe_y0 = None
        self.fired_steps = 0
        self.last_step_t = 0.0

    # -- helpers ------------------------------------------------------------
    def finger_count(self):
        return len(self.slots)

    def click_count(self):
        """fingers to use for a physical click.

        max_count covers the case where the kernel delivers the button event
        before the final MT slot of the same HID report; slots normally win.
        """
        return max(len(self.slots), self.max_count)

    def note_click(self, pressed):
        if pressed:
            self.saw_click = True
            self.swiping = False
            self.swipe_x0 = self.swipe_y0 = None

    def _coords(self):
        return [s for s in self.slots.values()
                if s[2] is not None and s[3] is not None]

    def _avg_y(self):
        pts = self._coords()
        return sum(s[3] for s in pts) / len(pts) if pts else 0.0

    def _avg_x(self):
        pts = self._coords()
        return sum(s[2] for s in pts) / len(pts) if pts else 0.0

    # -- event entry point --------------------------------------------------
    def feed_abs(self, code, value, now):
        out = []
        if code == ABS_MT_SLOT:
            self.slot = value
            return out

        if code == ABS_MT_TRACKING_ID:
            if value == -1:                     # finger lifted
                self.slots.pop(self.slot, None)
                if not self.slots:
                    tap = self._finish(now)
                    if tap:
                        out.append(("tap", tap))
                    return out
                if len(self.slots) != 3:
                    # a 3-finger swipe only exists while exactly 3 fingers are down
                    self.swipe_x0 = self.swipe_y0 = None
                return out
            # new finger
            self.slots[self.slot] = [None, None, None, None]
            if self.started is None:
                self.started = now
            self.max_count = max(self.max_count, len(self.slots))
            if len(self.slots) != 3:
                self.swipe_x0 = self.swipe_y0 = None
            return out

        if code in (ABS_MT_POSITION_X, ABS_MT_POSITION_Y):
            slot = self.slots.get(self.slot)
            if slot is None:
                return out
            i = 2 if code == ABS_MT_POSITION_X else 3
            slot[i] = float(value)
            if slot[0] is None and slot[2] is not None and slot[3] is not None:
                slot[0], slot[1] = slot[2], slot[3]
            if slot[0] is not None:
                self.worst_move = max(self.worst_move, abs(slot[2] - slot[0]),
                                      abs(slot[3] - slot[1]))
                out.extend(self._swipe_steps(now))

        return out

    def _swipe_steps(self, now):
        if self.saw_click or len(self.slots) != 3:
            return []
        if len(self._coords()) != 3:
            return []
        if self.swipe_x0 is None:
            self.swipe_x0, self.swipe_y0 = self._avg_x(), self._avg_y()
            return []
        dy = self._avg_y() - self.swipe_y0
        dx = self._avg_x() - self.swipe_x0
        if not self.swiping:
            if abs(dy) < SWIPE_MIN_FRAC * self.y_range or \
                    abs(dy) < SWIPE_LOCK * abs(dx):
                return []
            self.swiping = True
        want = int(abs(dy) / (SWIPE_STEP_FRAC * self.y_range))
        if want <= self.fired_steps or now - self.last_step_t < SWIPE_HOLD_S:
            return []
        n = min(want - self.fired_steps, MAX_STEPS_PER_FRAME)
        self.fired_steps = want
        self.last_step_t = now
        step = 1 if dy < 0 else -1          # finger up -> volume up
        return [("volume", step * n)]

    def _finish(self, now):
        tap = None
        if not self.saw_click and not self.swiping and self.started is not None:
            duration = now - self.started
            if duration <= TAP_MAX_S and \
                    self.worst_move <= TAP_MOVE_FRAC * min(self.x_range, self.y_range):
                tap = TAP_ACTIONS.get(self.max_count)
        self.reset()
        return tap


# ── uinput virtual mouse (back/forward only) ─────────────────────────────────
class VirtualMouse:
    def __init__(self, name="river-classic gestures"):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        try:
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
            for b in (BTN_LEFT, BTN_RIGHT, BTN_SIDE, BTN_EXTRA):
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, b)
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_REL)
            fcntl.ioctl(self.fd, UI_SET_RELBIT, 0x00)     # REL_X
            fcntl.ioctl(self.fd, UI_SET_RELBIT, 0x01)     # REL_Y
            setup = struct.pack("<HHHH80sI", 0x03, 0x1D6B, 0x0001, 1,
                                name.encode()[:79], 0)
            fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except Exception:
            os.close(self.fd)
            raise
        self.pressed = set()

    def click(self, button, value):
        self._emit(EV_KEY, button, value)
        self._emit(EV_SYN, SYN_REPORT, 0)
        if value:
            self.pressed.add(button)
        else:
            self.pressed.discard(button)

    def _emit(self, etype, code, value):
        now = time.monotonic()
        sec, usec = int(now), int((now % 1) * 1_000_000)
        os.write(self.fd,
                 struct.pack(EVENT_FMT, sec, usec, etype, code, value))

    def close(self):
        try:
            for b in list(self.pressed):
                self.click(b, 0)
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        except OSError:
            pass
        os.close(self.fd)


# ── uinput touchpad clone (non-clickpad, so all buttons pass through) ────────
class TouchpadClone:
    """Mirror of the physical pad that libinput sees as a normal touchpad.

    INPUT_PROP_BUTTONPAD is deliberately not copied: libinput ignores every
    non-left button on a clickpad, but forwards BTN_LEFT/BTN_RIGHT on a plain
    touchpad.  The daemon translates the physical click into one of those.
    """

    def __init__(self, src_fd):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        self.name = ""
        try:
            self._setup(src_fd)
        except Exception:
            os.close(self.fd)
            raise

    def _setup(self, src_fd):
        name_buf = fcntl.ioctl(src_fd, EVIOCGNAME(256), b"\0" * 256)
        self.name = name_buf.split(b"\0", 1)[0].decode("utf-8", "replace")[:79]
        bustype, vendor, product, version = struct.unpack(
            INPUT_ID_FMT, fcntl.ioctl(src_fd, EVIOCGID, b"\0" * 8))
        self.vendor, self.product = vendor, product

        ev_bits = bits(src_fd, 0, EV_MAX + 1)
        for ev in ev_bits:
            if ev == EV_SYN:
                continue
            fcntl.ioctl(self.fd, UI_SET_EVBIT, ev)
            nbits = ABS_MAX.get(ev)
            if nbits is None:
                continue
            codes = bits(src_fd, ev, nbits)
            if ev == EV_KEY:
                for code in codes + [BTN_RIGHT, BTN_MIDDLE]:
                    fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
            elif ev == EV_ABS:
                for code in codes:
                    info = absinfo(src_fd, code)
                    fcntl.ioctl(self.fd, UI_ABS_SETUP,
                                struct.pack("<H2x6i", code, *info))
            else:
                setter = {EV_REL: UI_SET_RELBIT, EV_MSC: UI_SET_MSCBIT,
                          EV_LED: UI_SET_LEDBIT, EV_SND: UI_SET_SNDBIT,
                          EV_SW: UI_SET_SWBIT, EV_FF: UI_SET_FFBIT}.get(ev)
                if setter:
                    for code in codes:
                        fcntl.ioctl(self.fd, setter, code)

        prop_buf = fcntl.ioctl(src_fd, EVIOCGPROP(4), b"\0" * 4)
        props = [i for i in range(INPUT_PROP_MAX + 1)
                 if prop_buf[i // 8] & (1 << (i % 8))]
        if INPUT_PROP_POINTER not in props:
            props.append(INPUT_PROP_POINTER)
        for prop in props:
            if prop == INPUT_PROP_BUTTONPAD:
                continue                # the whole point: not a clickpad
            fcntl.ioctl(self.fd, UI_SET_PROPBIT, prop)

        setup = struct.pack("<HHHH80sI", bustype, vendor, product, version,
                            self.name.encode(), 0)
        fcntl.ioctl(self.fd, UI_DEV_SETUP, setup)
        fcntl.ioctl(self.fd, UI_DEV_CREATE)

    def identifier(self):
        """river's identifier format: pointer-<vendor>-<product>-<name>"""
        safe = "".join(ch if ch.isprintable() and not ch.isspace() else "_"
                       for ch in self.name.strip())
        return "pointer-%d-%d-%s" % (self.vendor, self.product, safe)

    def write(self, data):
        if data:
            os.write(self.fd, bytes(data))

    def close(self):
        try:
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        except OSError:
            pass
        os.close(self.fd)


# ── session plumbing ─────────────────────────────────────────────────────────
def find_touchpad():
    """first real /dev/input/event* whose sysfs name contains 'touchpad'"""
    for path in sorted(glob.glob("/dev/input/event*"),
                       key=lambda p: int(p.rsplit("event", 1)[1] or 0)):
        name_file = "/sys/class/input/%s/device/name" % os.path.basename(path)
        try:
            with open(name_file) as fh:
                name = fh.read().strip()
        except OSError:
            continue
        if "touchpad" not in name.lower():
            continue
        # never grab our own uinput clone (it has the same name)
        try:
            real = os.path.realpath(
                "/sys/class/input/%s/device" % os.path.basename(path))
        except OSError:
            continue
        if "/virtual/" in real:
            continue
        return path, name
    return None, None


def riverctl(*args):
    try:
        return subprocess.run([RIVERCTL, *args], capture_output=True, text=True,
                              timeout=4, check=False)
    except Exception:
        return None


def river_input_count(identifier):
    result = riverctl("list-inputs")
    if result is None or result.returncode != 0:
        return None
    return sum(1 for line in result.stdout.splitlines() if line.strip() == identifier)


def device_identifier(fd):
    """river's identifier for the physical pad (same IDs/name as the clone)."""
    name_buf = fcntl.ioctl(fd, EVIOCGNAME(256), b"\0" * 256)
    name = name_buf.split(b"\0", 1)[0].decode("utf-8", "replace")[:79].strip()
    _, vendor, product, _ = struct.unpack(
        INPUT_ID_FMT, fcntl.ioctl(fd, EVIOCGID, b"\0" * 8))
    safe = "".join(ch if ch.isprintable() and not ch.isspace() else "_"
                   for ch in name)
    return "pointer-%d-%d-%s" % (vendor, product, safe)


def wait_for_clone(clone, before, timeout=4.0):
    """True once river has adopted the clone as a pointer device."""
    ident = clone.identifier()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        count = river_input_count(ident)
        if count is not None and count > before:
            return True
        time.sleep(0.15)
    return False


def volume(steps):
    if not steps:
        return
    pct = VOLUME_STEP * abs(steps)
    cmd = "%d%%%s" % (pct, "+" if steps > 0 else "-")
    try:
        subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", cmd],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=4, check=False)
    except Exception:
        pass


def dispatch(mouse, action):
    if action is None:
        return
    if action[0] == "volume":
        volume(action[1])
        log("volume %s" % ("up" if action[1] > 0 else "down"))
    elif action[0] == "tap":
        log("tap -> %s" % action[1])
        button = BTN_SIDE if action[1] == "back" else BTN_EXTRA
        mouse.click(button, 1)
        mouse.click(button, 0)


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def parent_alive(pid):
    if not pid:
        return True
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


# ── run / selftest / off ─────────────────────────────────────────────────────
def run(parent=None, gestures_only=False):
    os.makedirs(STATE, exist_ok=True)
    lock_fd = os.open(os.path.join(STATE, "gestures.lock"),
                      os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("another gestures.py instance is already running")
        os.close(lock_fd)
        return 0

    dev, name = find_touchpad()
    if dev is None:
        log("no touchpad found in /dev/input -- nothing to do")
        os.close(lock_fd)
        return 4

    try:
        fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
    except PermissionError:
        log("cannot read %s (%s) -- install udev/70-river-classic-input.rules" %
            (dev, name))
        return 3
    except OSError as exc:
        log("cannot open %s: %s" % (dev, exc))
        return 3

    x_range = absinfo(fd, ABS_MT_POSITION_X)[2] or 1200
    y_range = absinfo(fd, ABS_MT_POSITION_Y)[2] or 1000
    engine = Engine(x_range, y_range)

    mouse = clone = None
    grabbed = False
    try:
        try:
            mouse = VirtualMouse()
        except PermissionError:
            log("cannot write /dev/uinput -- install the udev rule (see README)")
            return 3
        except OSError as exc:
            log("cannot open /dev/uinput: %s" % exc)
            return 3

        if not gestures_only:
            try:
                before = river_input_count(device_identifier(fd))
                if before is None:
                    log("riverctl unavailable -- gestures only")
                else:
                    clone = TouchpadClone(fd)
                    if wait_for_clone(clone, before):
                        fcntl.ioctl(fd, EVIOCGRAB, 1)
                        grabbed = True
                        log("click mirror active: 1 finger = left, 2+ = right")
                    else:
                        log("river did not adopt the virtual touchpad -- gestures only")
                        clone.close()
                        clone = None
            except PermissionError:
                log("cannot write /dev/uinput for the clone -- gestures only")
                if clone:
                    clone.close()
                clone = None
            except Exception as exc:
                log("virtual touchpad failed (%s) -- gestures only" % exc)
                if clone:
                    try:
                        clone.close()
                    except OSError:
                        pass
                clone = None

        log("up: %s (%dx%d) -- 3-tap back, 4-tap forward, 3-swipe volume%s" %
            (name, x_range, y_range,
             ", clicks mirrored" if grabbed else ", stock clicks"))

        stopping = {"now": False}

        def bye(_sig=None, _frm=None):
            stopping["now"] = True

        signal.signal(signal.SIGTERM, bye)
        signal.signal(signal.SIGINT, bye)
        signal.signal(signal.SIGHUP, bye)

        active_btn = None
        last_parent_check = 0.0

        while not stopping["now"]:
            ready, _, _ = select.select([fd], [], [], 0.5)
            if not ready:
                if time.monotonic() - last_parent_check > 1.0:
                    last_parent_check = time.monotonic()
                    if not parent_alive(parent):
                        log("compositor exited -- stopping")
                        break
                continue
            try:
                data = os.read(fd, EVENT_SIZE * 128)
            except BlockingIOError:
                continue
            except OSError as exc:
                log("touchpad read failed: %s" % exc)
                break
            if not data:
                break

            out = bytearray() if (clone and grabbed) else None
            for off in range(0, len(data) - EVENT_SIZE + 1, EVENT_SIZE):
                sec, usec, etype, code, value = struct.unpack(
                    EVENT_FMT, data[off:off + EVENT_SIZE])
                now = sec + usec / 1_000_000.0
                if now <= 0:
                    now = time.monotonic()

                if etype == EV_SYN and code == SYN_DROPPED:
                    log("SYN_DROPPED from the touchpad (events lost)")
                    continue

                if etype == EV_KEY and code == BTN_LEFT:
                    engine.note_click(value != 0)
                    if out is not None:
                        if value:
                            fingers = engine.click_count()
                            active_btn = button_for_fingers(fingers)
                            log("click: %d finger(s) -> %s" %
                                (fingers,
                                 "right" if active_btn == BTN_RIGHT else "left"))
                            out += struct.pack(EVENT_FMT, sec, usec, EV_KEY,
                                               active_btn, 1)
                        elif active_btn is not None:
                            out += struct.pack(EVENT_FMT, sec, usec, EV_KEY,
                                               active_btn, 0)
                            active_btn = None
                    continue

                if etype == EV_ABS:
                    for action in engine.feed_abs(code, value, now):
                        dispatch(mouse, action)

                if out is not None:
                    out += data[off:off + EVENT_SIZE]

            if out is not None and clone is not None:
                try:
                    clone.write(out)
                except OSError as exc:
                    log("clone write failed: %s -- gestures only" % exc)
                    # stop mirroring but keep the session alive
                    if grabbed:
                        try:
                            fcntl.ioctl(fd, EVIOCGRAB, 0)
                        except OSError:
                            pass
                        grabbed = False
                    clone.close()
                    clone = None

    finally:
        if grabbed:
            try:
                fcntl.ioctl(fd, EVIOCGRAB, 0)
            except OSError:
                pass
        if clone is not None:
            try:
                clone.close()
            except OSError:
                pass
        if mouse is not None:
            try:
                mouse.close()
            except OSError:
                pass
        os.close(fd)
        log("stopped")
    return 0


def selftest():
    """synthetic event streams -- no hardware, no root"""
    failures = []

    def gesture(fingers, dy=0, dx=0, click=False, duration=0.2,
                y_range=1000, x_range=1000):
        eng = Engine(x_range, y_range)
        acts = []
        t = 10.0
        for i in range(fingers):
            eng.feed_abs(ABS_MT_SLOT, i, t)
            acts += eng.feed_abs(ABS_MT_TRACKING_ID, 100 + i, t)
            acts += eng.feed_abs(ABS_MT_POSITION_X, 500 + i * 20, t)
            acts += eng.feed_abs(ABS_MT_POSITION_Y, 500, t)
            t += 0.01
        t += 0.05
        if click:
            eng.note_click(True)
        frames = 5
        for f in range(1, frames + 1):
            t += 0.01
            for i in range(fingers):
                eng.feed_abs(ABS_MT_SLOT, i, t)
                acts += eng.feed_abs(ABS_MT_POSITION_X,
                                     500 + i * 20 + dx * f / frames, t)
                acts += eng.feed_abs(ABS_MT_POSITION_Y,
                                     500 + dy * f / frames, t)
        if click:
            eng.note_click(False)
            click_btn = button_for_fingers(eng.click_count())
        else:
            click_btn = None
        t += duration if not click else 0.05
        for i in range(fingers):
            eng.feed_abs(ABS_MT_SLOT, i, t)
            acts += eng.feed_abs(ABS_MT_TRACKING_ID, -1, t)
            t += 0.01
        taps = [a[1] for a in acts if a[0] == "tap"]
        vol = sum(a[1] for a in acts if a[0] == "volume")
        return taps, vol, click_btn

    cases = [
        (3, 0, "3-finger tap -> back", "back", 0),
        (4, 0, "4-finger tap -> forward", "forward", 0),
        (1, 0, "1-finger tap -> nothing (libinput does it)", None, 0),
        (2, 0, "2-finger tap -> nothing (libinput does it)", None, 0),
        (3, -120, "3-finger swipe up -> volume up", None, 1),
        (3, 120, "3-finger swipe down -> volume down", None, -1),
    ]
    for fingers, dy, label, want_tap, want_vol_sign in cases:
        taps, vol, _ = gesture(fingers, dy=dy)
        ok = (taps == ([want_tap] if want_tap else []) and
              (vol == 0 if want_vol_sign == 0 else
               (vol > 0 if want_vol_sign > 0 else vol < 0)))
        print("%-46s %s   taps=%s volume=%+d" %
              (label, "ok " if ok else "FAIL", taps, vol))
        if not ok:
            failures.append(label)

    # a moving 3-finger touch must never also register as a tap
    taps, vol, _ = gesture(3, dy=-45, duration=0.0)
    ok = not taps and vol == 0
    print("%-46s %s   taps=%s volume=%+d" %
          ("moving 3-finger touch is not a tap", "ok " if ok else "FAIL",
           taps, vol))
    if not ok:
        failures.append("moving 3-finger touch is not a tap")

    # physical clicks: 1 = left, 2 = right, 3 = right
    for fingers, want in ((1, BTN_LEFT), (2, BTN_RIGHT), (3, BTN_RIGHT),
                          (4, BTN_RIGHT)):
        taps, vol, btn = gesture(fingers, click=True)
        ok = (taps == [] and btn == want)
        print("%-46s %s   button=%s" %
              ("%d-finger physical click -> %s" %
               (fingers, "left" if want == BTN_LEFT else "right"),
               "ok " if ok else "FAIL", btn))
        if not ok:
            failures.append("%d-finger click" % fingers)

    # slow 3-finger rest is not a tap
    taps, vol, _ = gesture(3, duration=0.8)
    ok = not taps
    print("%-46s %s   taps=%s" %
          ("slow 3-finger rest is not a tap", "ok " if ok else "FAIL", taps))
    if not ok:
        failures.append("slow 3-finger rest")

    # a partial MT frame (all X before any Y) must not crash the daemon
    try:
        eng = Engine(1000, 1000)
        t = 10.0
        for i in range(3):
            eng.feed_abs(ABS_MT_SLOT, i, t)
            eng.feed_abs(ABS_MT_TRACKING_ID, 300 + i, t)
        for i in range(3):
            eng.feed_abs(ABS_MT_SLOT, i, t)
            eng.feed_abs(ABS_MT_POSITION_X, 500 + i * 10, t)
        for i in range(3):
            eng.feed_abs(ABS_MT_SLOT, i, t)
            eng.feed_abs(ABS_MT_POSITION_Y, 500, t)
        ok = True
    except Exception as exc:
        ok = False
        print("partial X-only frame: %s" % exc)
    print("%-46s %s" % ("partial X-only frame does not crash", "ok " if ok else "FAIL"))
    if not ok:
        failures.append("partial X-only frame")

    print("\n%s" % ("all good" if not failures else "FAILURES: %s" % failures))
    return 1 if failures else 0


def off():
    riverctl("input", "*Touchpad", "click-method", "clickfinger")
    print("click-method restored to clickfinger (gestures daemon inactive)")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--selftest" in args:
        sys.exit(selftest())
    if any(a in ("--off", "--restore") for a in args):
        sys.exit(off())
    if any(a in ("-h", "--help") for a in args):
        print(__doc__)
        sys.exit(0)
    parent = None
    if "--parent" in args:
        try:
            parent = int(args[args.index("--parent") + 1])
        except (IndexError, ValueError):
            print("--parent needs a PID", file=sys.stderr)
            sys.exit(2)
    sys.exit(run(parent=parent, gestures_only="--gestures-only" in args))
