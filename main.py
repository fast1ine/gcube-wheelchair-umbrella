import sys
import tkinter as tk
from tkinter import messagebox

from app import WheelchairUmbrellaApp
from config import AppConfig


def main():
    try:
        config = AppConfig.from_env()
    except Exception as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("설정 오류", str(error))
        root.destroy()
        return 1

    root = tk.Tk()
    WheelchairUmbrellaApp(root, config)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
