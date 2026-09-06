import contextlib
import ctypes
import warnings
from typing import Any, Optional

__version__ = '0.9.0'

ole32 = ctypes.OleDLL("ole32")
kernel32 = ctypes.WinDLL("kernel32")
user32 = ctypes.WinDLL("user32")


# ---------------------------------------------------------------------------
# COM / GUID definitions
# ---------------------------------------------------------------------------

HRESULT = ctypes.c_long
HWND = ctypes.c_void_p
ULONGLONG = ctypes.c_uint64
DWORD = ctypes.c_uint32


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _guid(value: str) -> GUID:
    guid = GUID()

    ole32.CLSIDFromString(
        ctypes.c_wchar_p(value),
        ctypes.byref(guid),
    )

    return guid


# CLSID_TaskbarList
CLSID_TaskbarList = _guid(
    "{56FDF344-FD6D-11D0-958A-006097C9A090}"
)

# IID_ITaskbarList3
IID_ITaskbarList3 = _guid(
    "{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}"
)


# ---------------------------------------------------------------------------
# Windows API declarations
# ---------------------------------------------------------------------------

ole32.CoInitialize.argtypes = [ctypes.c_void_p]
ole32.CoInitialize.restype = HRESULT

ole32.CoUninitialize.argtypes = []
ole32.CoUninitialize.restype = None

ole32.CoCreateInstance.argtypes = [
    ctypes.POINTER(GUID),
    ctypes.c_void_p,
    DWORD,
    ctypes.POINTER(GUID),
    ctypes.POINTER(ctypes.c_void_p),
]
ole32.CoCreateInstance.restype = HRESULT

ole32.CLSIDFromString.argtypes = [
    ctypes.c_wchar_p,
    ctypes.POINTER(GUID),
]
ole32.CLSIDFromString.restype = HRESULT

kernel32.GetConsoleWindow.argtypes = []
kernel32.GetConsoleWindow.restype = HWND

user32.FlashWindow.argtypes = [
    HWND,
    ctypes.c_int,
]
user32.FlashWindow.restype = ctypes.c_int


CLSCTX_INPROC_SERVER = 0x00000001


# ---------------------------------------------------------------------------
# COM vtable helper
# ---------------------------------------------------------------------------

def _com_method(interface: Any, index: int, restype: Any, *argtypes: Any) -> Any:
    vtable = ctypes.cast(
        interface,
        ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
    )[0]

    address = vtable[index]

    prototype = ctypes.WINFUNCTYPE(
        restype,
        ctypes.c_void_p,
        *argtypes,
    )

    return prototype(address)


# ---------------------------------------------------------------------------
# Taskbar progress
# ---------------------------------------------------------------------------

class Progress:
    """
    Controls the Windows Taskbar progress indicator for a specific window.
    """

    def __init__(self, hwnd: Optional[int] = None) -> None:
        """
        Initialize the Progress instance.

        Args:
            hwnd (Optional[int]): The window handle (HWND) to attach the progress bar to.
                                  If None, defaults to the current console window.
        """
        super().__init__()
        self.initialised = False
        self.state: Optional[str] = None

        if hwnd is None:
            self.win = kernel32.GetConsoleWindow()
        else:
            self.win = hwnd

        self.thisWindow: Any = None
        self.progress: int = 0
        self._taskbar: Any = None
        self._com_initialized: bool = False

    def init(self) -> None:
        """
        Initialize the COM interfaces required to communicate with the Windows Taskbar.
        Must be called before setting the state or progress.

        Raises:
            OSError: If COM initialization or Taskbar instance creation fails.
        """
        if self.initialised:
            return

        self.thisWindow = self.win

        RPC_E_CHANGED_MODE = 0x80010106

        hr = ole32.CoInitialize(None)

        if (hr & 0xFFFFFFFF) == RPC_E_CHANGED_MODE:
            # COM was already initialized with a different apartment model.
            # We do not own that initialization.
            self._com_initialized = False
        elif hr < 0:
            raise OSError(f"CoInitialize failed: 0x{hr & 0xFFFFFFFF:08X}")
        else:
            self._com_initialized = True

        # Create ITaskbarList3.
        taskbar = ctypes.c_void_p()

        hr = ole32.CoCreateInstance(
            ctypes.byref(CLSID_TaskbarList),
            None,
            CLSCTX_INPROC_SERVER,
            ctypes.byref(IID_ITaskbarList3),
            ctypes.byref(taskbar),
        )

        if hr < 0:
            self._cleanup_com()
            raise OSError(f"CoCreateInstance failed: 0x{hr & 0xFFFFFFFF:08X}")

        self._taskbar = taskbar

        # ITaskbarList::HrInit()
        # IUnknown:       0 QueryInterface
        #                  1 AddRef
        #                  2 Release
        # ITaskbarList:    3 HrInit
        hr = _com_method(
            self._taskbar,
            3,
            HRESULT,
        )(self._taskbar)

        if hr < 0:
            self._release()

            raise OSError(f"HrInit failed: 0x{hr & 0xFFFFFFFF:08X}")

        self.state = 'normal'
        self.progress = 0
        self.initialised = True

    def setState(self, value: str) -> None:
        """
        Set the state (color/behavior) of the taskbar progress indicator.

        Args:
            value (str): The state to apply. Valid options are:
                         - 'normal': Green progress bar.
                         - 'paused': Yellow progress bar.
                         - 'error': Red progress bar.
                         - 'loading': Indeterminate marquee (moving animation).
                         - 'done': Removes the progress bar and flashes the window.
        """
        if not self.initialised:
            warnings.warn('Please initialise the object (method: Progress.init())', stacklevel=2)
            return

        if value == 'normal':
            self._set_progress_state(2)
            self.state = 'normal'

        elif value == 'paused':
            self._set_progress_state(8)
            self.state = 'paused'

        elif value == 'error':
            self._set_progress_state(4)
            self.state = 'error'

        elif value == 'loading':
            self._set_progress_state(1)
            self.state = 'loading'

        elif value == 'done':
            user32.FlashWindow(self.thisWindow, True)
            self._set_progress_state(0)
            self.state = 'done'

        else:
            warnings.warn(f'Invalid Argument {value}. Please select one from normal, paused, error, loading, done.', stacklevel=2)

    def setProgress(self, value: int) -> None:
        """
        Set the completion percentage of the taskbar progress indicator.

        Args:
            value (int): The progress percentage, from 0 to 100.

        Raises:
            OSError: If setting the progress value through the COM interface fails.
        """
        if not self.initialised:
            warnings.warn('Please initialise the object (method: Progress.init())', stacklevel=2)
            return

        if 0 <= value <= 100:
            method = _com_method(
                self._taskbar,
                9,  # ITaskbarList3::SetProgressValue
                HRESULT,
                HWND,
                ULONGLONG,
                ULONGLONG,
            )

            hr = method(
                self._taskbar,
                self.thisWindow,
                value,
                100,
            )

            if hr < 0:
                raise OSError(f"SetProgressValue failed: 0x{hr & 0xFFFFFFFF:08X}")

            self.progress = value

        else:
            warnings.warn(f'Invalid Argument {value}. Please select a value between 0 and 100.', stacklevel=2)

    def _set_progress_state(self, state: int) -> None:
        # ITaskbarList3::SetProgressState
        method = _com_method(
            self._taskbar,
            10,
            HRESULT,
            HWND,
            DWORD,
        )

        hr = method(
            self._taskbar,
            self.thisWindow,
            state,
        )

        if hr < 0:
            raise OSError(f"SetProgressState failed: 0x{hr & 0xFFFFFFFF:08X}")

    def _release(self) -> None:
        if self._taskbar is not None:
            # IUnknown::Release
            release = _com_method(
                self._taskbar,
                2,
                ctypes.c_ulong,
            )

            release(self._taskbar)
            self._taskbar = None

        self.initialised = False
        self._cleanup_com()

    def _cleanup_com(self) -> None:
        if self._com_initialized:
            ole32.CoUninitialize()
            self._com_initialized = False

    def __del__(self) -> None:
        with contextlib.suppress(Exception):
            self._release()
