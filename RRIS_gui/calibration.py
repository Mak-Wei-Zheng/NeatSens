import tkinter as tk
import tkinter.ttk as ttk # We will need the combobox
from utils import MultiTabFrame, ScrollableDisplay, disable_tk_frame, enable_tk_frame, freq_to_ms
from connection import GUIClient
import time

CALIBRATION_DURATION = 2000 # no. ms

# Updated populate method for CalibrationStatusMenu
class CalibrationStatusMenu(ScrollableDisplay):
    def __init__(self, parent):
        super().__init__(parent)
    
    def populate(self):
        return super().populate()
    
class CalibrationControls(tk.Frame):
    def __init__(self, parent, data_handler):
        super().__init__(parent)
        # Initialize combobox displaying the values
        self.parent = parent
        self.data_handler = data_handler
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.grid()
        self.header = tk.Label(self, text="Calibration Menu")
        self.header.grid(row=0,column=0, sticky="n")
        self.form_frame = tk.Frame(self) # we create an outer frame for holding the calibration form
        self.form_frame.grid(row=2, column=0, sticky="", padx=10)
        self.client_combobox = ttk.Combobox(self, values=[f"{"Calibrated" if client.is_calibrated else "Not Calibrated"}_{client.address}" for client in self.data_handler.clients], state="readonly")
        self.update_calibration_dd()
        self.client_combobox.bind("<<ComboboxSelected>>", self.load_form())
        self.client_combobox.grid(row=1, column=0, sticky="n")
    
    def update_calibration_dd(self):
        # updates the calibration dropdown menu everytime we calibrate something
        # we sort the values of the dd to be displayed
        values = [f"{"Calibrated" if client.is_calibrated else "Not Calibrated"}_{client.address}" for client in self.data_handler.clients]
        values.sort(key=lambda x: x.split("_")[0], reverse="True") # put the uncalibrated clients are the top
        self.client_combobox.config(values=values)
        if values:
            self.client_combobox.set(values[0])

    def get_client(self, address):
        for client in self.data_handler.clients:
            if client.address == address.split("_")[-1]:
                return client
            else:
                return None

    def load_form(self):
        client_address = self.client_combobox.get()
        client = self.get_client(client_address)
        # check for existing frame in outer frame
        if client:
            if self.form_frame.winfo_children():
                for widget in self.form_frame.winfo_children():
                    widget.destroy()
            form = CalibrationForm(self, client) # we display the form in the outer frame
            form.grid(row=0, column=0, sticky="", padx=10) # Fill the entired outer frame
        else:
            form = EmptyForm(self)
            form.grid(row=0, column=0, sticky="", padx=10)
    
    
class CalibrationForm(tk.Frame):
    def __init__(self, parent, client:GUIClient):
        super().__init__()
        self.parent = parent
        self.form_frame = parent.form_frame
        self.client = client # parent in this case would be the GUIClient as each form is unique to the GUIClient
        # load in existing values if any --> this would be important if we are changing the calibrated values...
        self.grid()
        self.values = self.client.calibration_values

        # Title --> The device address
        self.header = tk.Label(self.form_frame, text=self.client.address)
        self.header.grid(row=0,column=0,columnspan=3)

        # Entry for truth values
        self.truth_label = tk.Label(self.form_frame, text="User Input")
        self.truth_label.grid(row=1, column=2)
        self.user_input_max = tk.Entry(self.form_frame, foreground="black", background="white")
        self.user_input_max.insert(0, str(self.values["max"][1]) if self.values["max"][1] else "")
        self.user_input_max.bind("<KeyRelease>", self.check_entries)
        self.user_input_max.bind("<KeyRelease>", self.reset_color, add="+")
        self.user_input_max.grid(row=3, column=2)
        self.user_input_min = tk.Entry(self.form_frame, foreground="black", background="white")
        self.user_input_min.insert(0, str(self.values["max"][1]) if self.values["max"][1] else "")
        self.user_input_min.bind("<KeyRelease>", self.check_entries)
        self.user_input_min.bind("<KeyRelease>", self.reset_color, add="+")
        self.user_input_min.grid(row=2, column=2)

        # Display for raw data
        self.raw_label = tk.Label(self.form_frame, text="Raw Data")
        self.raw_label.grid(row=1, column=1)
        self.raw_min = tk.StringVar(self.form_frame, value=str(self.values["min"][0]))
        self.raw_max = tk.StringVar(self.form_frame, value=str(self.values["max"][0]))
        self.raw_min_label = tk.Label(self.form_frame, textvariable=self.raw_min)
        self.raw_max_label = tk.Label(self.form_frame, textvariable=self.raw_max)
        self.raw_max_label.grid(row=3, column=1)
        self.raw_min_label.grid(row=2, column=1)

        self.max_label = tk.Label(self.form_frame, text="Max Value: ")
        self.max_label.grid(row=3, column=0)
        self.min_label = tk.Label(self.form_frame, text="Min Value: ")
        self.min_label.grid(row=2, column=0)

        # Calibrate Button
        self.min_button = tk.Button(self.form_frame, text="Get Raw Min", command=self.min_calibrate)
        self.min_button.grid(row=4, column=0)
        self.max_button = tk.Button(self.form_frame, text="Get Raw Max", command=self.max_calibrate)
        self.max_button.grid(row=4, column=1)

        # Save button
        self.update_button = tk.Button(self.form_frame, text="Update", state="disabled", command=self.save_calibration)
        self.update_button.grid(row=4,column=2)

    def reset_color(self, event):
        entry = event.widget
        if isinstance(entry, tk.Entry):
            entry.config(foreground="black")

    def calibration_data(self)->list[float]:
        # this function defines how data is collected at the calibration step.
        # As of now it is determined by storing 1 second worth of data
        data = []
        interval = freq_to_ms(self.client.data_handler.frequency)/1000 #interval between updates in seconds
        # print(f"time interval set as {interval}")
        duration = CALIBRATION_DURATION/1000 # duration in seconds
        end_time = time.time() + duration

        while time.time() < end_time:
            data.append(self.client.curr_y)
            time.sleep(interval)
        return [round(float(val),4) for val in data]

    def update_truth(self):
        try:
            self.values["min"][1] = float(self.user_input_min.get())
            try:
                self.values["max"][1] = float(self.user_input_max.get())
            except ValueError:
                self.values["max"][1] = self.user_input_max.get()
                self.user_input_max.config(foreground="red")
        except ValueError:
            # set the entry value to red color
            self.user_input_min.config(foreground="red")
            self.values["min"][1] = self.user_input_max.get()
            try:
                self.values["max"][1] = float(self.user_input_max.get())
            except ValueError:
                self.values["max"][1] = self.user_input_max.get()
                self.user_input_max.config(foreground="red")
            

    def check_entries(self, event):
        # Check if both entries are not empty
        if (self.user_input_max.get() and self.user_input_min.get()) and (self.raw_min.get() != "None" and self.raw_max.get() != "None"):
            if self.user_input_max.get() == self.user_input_min.get():
                raise ValueError("Max and Min Values cannot be the same")
            elif self.raw_min.get() == self.raw_max.get():
                raise ValueError("Please recalibrate raw values")
            else:
                self.update_button.config(state=tk.NORMAL)
        else:
            self.update_button.config(state=tk.DISABLED)


    def min_calibrate(self):
        self.min_button.configure(text="Loading...", state=tk.DISABLED)
        self.max_button.configure(state=tk.DISABLED) # we disable simultaneous calibration
        self.update()
        data = self.calibration_data()
        # for now the logic is just to take the minimum value of the list
        self.min_button.configure(text="Get Raw Min", state=tk.ACTIVE)
        self.max_button.configure(state=tk.ACTIVE)
        self.update()
        self.values["min"][0] = min(data)
        self.raw_min.set(str(self.values["min"][0]))
        self.check_entries(None)
    
    def max_calibrate(self):
        self.max_button.configure(text="Loading...", state=tk.DISABLED)
        self.min_button.configure(state=tk.DISABLED)
        self.update()
        data = self.calibration_data()
        print(f"length of collected data = {len(data)}")
        self.max_button.configure(text="Get Raw Max", state=tk.ACTIVE)
        self.min_button.configure(state=tk.ACTIVE)
        self.update()
        self.values["max"][0] = max(data)
        self.raw_max.set(str(self.values["max"][0]))
        self.check_entries(None)
    

    def save_calibration(self):
        # command associated with the save calibration button
        try:
            self.update_truth()
            self.client.update_calibration(self.values)
            self.parent.update_calibration_dd() # we update the dropdown menu
            self.client.data_handler.update_calibration_status()
            self.client.gen_calib_formula()

        except ValueError:
            self.update_button.config(state=tk.DISABLED)

class EmptyForm(tk.Frame):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.form_frame = parent.form_frame
        self.grid()

        # Title --> The device address
        self.header = tk.Label(self.form_frame, text="No Selected Client")
        self.header.grid(row=0,column=0,columnspan=3)

        # Entry for truth values
        self.truth_label = tk.Label(self.form_frame, text="User Input")
        self.truth_label.grid(row=1, column=2)
        self.user_input_max = tk.Entry(self.form_frame, foreground="black", background="white", state="disabled")
        self.user_input_max.grid(row=2, column=2)
        self.user_input_min = tk.Entry(self.form_frame, foreground="black", background="white", state="disabled")
        self.user_input_min.grid(row=3, column=2)

        # Display for raw data
        self.raw_label = tk.Label(self.form_frame, text="Raw Data")
        self.raw_label.grid(row=1, column=1)
        self.raw_min = tk.StringVar(self.form_frame, value="")
        self.raw_max = tk.StringVar(self.form_frame, value="")
        self.raw_min_label = tk.Label(self.form_frame, textvariable=self.raw_min)
        self.raw_max_label = tk.Label(self.form_frame, textvariable=self.raw_max)
        self.raw_max_label.grid(row=2, column=1)
        self.raw_min_label.grid(row=3, column=1)

        self.max_label = tk.Label(self.form_frame, text="Max Value: ")
        self.max_label.grid(row=2, column=0)
        self.min_label = tk.Label(self.form_frame, text="Min Value: ")
        self.min_label.grid(row=3, column=0)

        # Calibrate Button
        self.min_button = tk.Button(self.form_frame, text="Raw Min")
        self.min_button.grid(row=4, column=0)
        self.max_button = tk.Button(self.form_frame, text="Raw Max")
        self.max_button.grid(row=4, column=1)

        # Save button
        self.update_button = tk.Button(self.form_frame, text="Update", state="disabled")
        self.update_button.grid(row=4,column=2)
        
class CalibrationApp(tk.Frame):
    def __init__(self, parent, data_handler):
        super().__init__(parent) # we inherit the attributes of the parent
        self.grid() # initialize display
        self.data_handler = data_handler
        self.handler = CalibrationHandler(self)
        self.calibration_display = MultiTabFrame(self)
        self.calibration_step_page = CalibrationControls(self.calibration_display, data_handler)
        self.calibration_status_menu = CalibrationStatusMenu(self.calibration_display)
        self.calibration_display.add_tab(self.calibration_step_page,"Calibration Step")
        self.calibration_display.add_tab(self.calibration_status_menu,"Calibration Status Menu")

        # We initialize with everything disabled
        self.handler.nested_disable()
        

class CalibrationHandler:
    def __init__(self, display_frame:CalibrationApp):
        self.data_handler = display_frame.data_handler
        self.data_handler.calibration_handler = self
        self.display = display_frame
        
    def nested_disable(self):
        # we perform a nested disable
        disable_tk_frame(self.display)

    def nested_enable(self):
        # we perform a nested enabling of all functions
        enable_tk_frame(self.display)
        self.update_clients()
    
    def update_clients(self):
        self.display.calibration_step_page.update_calibration_dd()
        self.display.calibration_step_page.load_form()


