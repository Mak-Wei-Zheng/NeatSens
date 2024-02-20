import tkinter as tk
from calibration import CalibrationApp
from display import DisplayApp
from connection import ConnectionApp
from data_handler import DataHandler
from PIL import Image, ImageTk

LOGO_SIZE = (50,50)

class TaskBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.configure(bg="#000b38")
        self.parent = parent
        self.grid()

        logo = Image.open("./images/RRIS_logo_1.png")
        logo = ImageTk.PhotoImage(logo.resize(LOGO_SIZE))
        logo_label = tk.Label(self, image=logo, bg="#000b38")
        logo_label.image = logo
        logo_label.grid(row=0, column=0)

        app_name = tk.Label(self, text="RRIS_GUI v1.0.1", anchor="w", bg="#000b38")
        app_name.grid(row=0, column=1, sticky="w", padx=(0,100))


class RootApp(tk.Frame):
    # handles the organization of microservices and serves as a data cache
    def __init__(self, master=None):
        super().__init__(master)
        self.master = master
        self.grid()
        # Create banner
        self.task_bar = TaskBar(self)
        self.task_bar.grid(row=0,column=0,columnspan=100, sticky="NSEW") # some large column span that ensures the task bar always covers the entire screen
        self.data_handler = DataHandler(self) # initialize data handler which will store global variables
        self.connection_app = ConnectionApp(self, self.data_handler)
        self.connection_app.grid(row=1,column=0, sticky="")
        self.data_handler.connection_handler = self.connection_app.handler
        self.calibration_app = CalibrationApp(self, self.data_handler)
        self.calibration_app.grid(row=2,column=0, sticky="")
        self.data_handler.calibration_handler = self.calibration_app.handler
        self.graph_display = DisplayApp(self, self.data_handler)
        self.graph_display.grid(row=1,column=1, rowspan=2, sticky="NSEW")
        self.data_handler.display_handler = self.graph_display.handler
        

# Create the application window
root = tk.Tk()
root.title("RRIS GUI")

# Create the application
app = RootApp(master=root)

# Start the application
app.mainloop()