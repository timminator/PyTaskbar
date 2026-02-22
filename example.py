import tkinter as tk

import PyTaskbar

root = tk.Tk()
root.title('PyTaskbar Tkinter Example')
root.geometry('300x150')

status_label = tk.Label(root, text="Initializing...", font=("Helvetica", 12))
status_label.pack(pady=40)

root.update()

hwnd = int(root.wm_frame(), 16)
prog = PyTaskbar.Progress(hwnd)
prog.init()


def show_loading():
    status_label.config(text="State: Loading")
    prog.setState('loading')
    root.after(3000, show_normal)


def show_normal():
    status_label.config(text="State: Normal (Progress)")
    prog.setState('normal')

    for i in range(0, 101):
        root.after(i * 30, prog.setProgress, i)

    root.after(3000 + 1000, show_paused)


def show_paused():
    status_label.config(text="State: Paused")
    prog.setProgress(50)
    prog.setState('paused')
    root.after(3000, show_error)


def show_error():
    status_label.config(text="State: Error")
    prog.setState('error')
    root.after(3000, show_done)


def show_done():
    status_label.config(text="State: Done!")
    prog.setState('done')


root.after(1000, show_loading)

root.mainloop()
