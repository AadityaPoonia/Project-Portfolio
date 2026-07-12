import tkinter as tk

def on_closing(window):
    close = tk.Toplevel(window)
    close.geometry("300x100")
    close.title("Quit?")
    close.resizable(False, False)
    lbl = tk.Label(close, text="Are you sure you want to quit?")
    lbl.pack(pady=10)
    button_frame = tk.Frame(close)
    button_frame.pack()
    lbtn = tk.Button(button_frame, text="No", command=close.destroy)
    lbtn.pack(side=tk.LEFT, padx=10)
    rbtn = tk.Button(button_frame, text="Yes", command=window.quit)
    rbtn.pack(side=tk.RIGHT, padx=10)