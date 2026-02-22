import ctypes
import sys
import warnings

import comtypes.client as cc

parent_dir = __file__.rsplit("\\", 1)[0]
sys.path.append(parent_dir)
cc.GetModule("./TaskbarLib.tlb")

import comtypes.gen.TaskbarLib as tbl  # noqa: E402

taskbar = cc.CreateObject(
    "{56FDF344-FD6D-11d0-958A-006097C9A090}",
    interface=tbl.ITaskbarList3
)


class Progress:
    def __init__(self, hwnd=None):
        super().__init__()
        self.initialised = False
        self.state = None

        if hwnd is None:
            self.win = ctypes.windll.kernel32.GetConsoleWindow()
        else:
            self.win = hwnd

    def init(self):
        self.thisWindow = self.win
        taskbar.HrInit()
        self.state = 'normal'
        self.progress = 0
        self.initialised = True

    def setState(self, value):
        if not self.initialised:
            warnings.warn('Please initialise the object (method: Progress.init())', stacklevel=2)
            return

        if value == 'normal':
            taskbar.SetProgressState(self.thisWindow, 2)
            self.state = 'normal'

        elif value == 'paused':
            taskbar.SetProgressState(self.thisWindow, 8)
            self.state = 'paused'

        elif value == 'error':
            taskbar.SetProgressState(self.thisWindow, 4)
            self.state = 'error'

        elif value == 'loading':
            taskbar.SetProgressState(self.thisWindow, 1)
            self.state = 'loading'

        elif value == 'done':
            ctypes.windll.user32.FlashWindow(self.thisWindow, True)
            taskbar.SetProgressState(self.thisWindow, 0)
            self.state = 'done'

        else:
            warnings.warn(f'Invalid Argument {value}. Please select one from (normal, paused, error, loading, done).', stacklevel=2)

    def setProgress(self, value: int):
        if not self.initialised:
            warnings.warn('Please initialise the object (method: Progress.init())', stacklevel=2)
            return

        if 0 <= value <= 100:
            taskbar.SetProgressValue(self.thisWindow, value, 100)
        else:
            warnings.warn(f'Invalid Argument {value}. Please select a value between 0 and 100.', stacklevel=2)
