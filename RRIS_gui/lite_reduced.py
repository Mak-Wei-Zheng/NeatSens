'''
While waiting for optimization of the full app to be done (target March end deadline)... We produce a lite version of the app

Key Functionality:
- Support multi-knee brace connection with fixed read rate (not variable -- remove frequency BLEWrite characteristic)
- List to display connected devices
- Support Calibration
- Support Live Plotting (start-stop mode, no more timer mode)
- Do not do support dynamic disabling of buttons for now. Just change the text to reduce the number of changes to render along with reducing complexity of logic
- Do not support data clipping (for now)
- Support local file saving
'''

# required imports
import tkinter as tk
import tkinter.ttk as ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
import numpy as np
from bleak import BleakScanner, BleakClient
import asyncio
import struct
from threading import Thread
from constants import RESISTANCE_CHARACTERISTIC_UUID, TIMESTAMP_CHARACTERISTIC_UUID
from display import FixedStream, SaveRecording
from utils import MultiTabFrame, freq_to_ms, UploadPage
from datetime import date
import os
import json


save_dir = "save_lite"

# Global State Values
CONNECT_STATE = "Connect"
CONNECTING_STATE = "Connecting"
DISCONNECT_STATE = "Disconnect"

CONNECTED_STATUS_MESSAGE = "Connected"
CONNECTING_STATUS_MESSAGE = "Connecting"
DISCONNECTED_STATUS_MESSAGE = "Not Connected"
CALIBRATED_STATUS_MESSAGE = "Calibrated"

class LiteClient:
    def __init__(self, address, parent):
        self.address = address
        self.parent = parent
        self.connection_status = DISCONNECTED_STATUS_MESSAGE
        self.calibration_values = {"max":[None, None], "min":[None, None]}
        self.x_values = []
        self.y_values = []
        self.y_calibrated = []
        self.x_values_full = []
        self.y_values_full = []
        self.y_calibrated_full = []


        self.curr_y = None
        self.curr_x = None
        self.reference_time = None
        self.is_calibrated = False

    def thread_management_connection(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.connect_task = self.loop.create_task(self.async_connect_to_device())
        self.loop.run_until_complete(self.connect_task)
        # we need to wait for all clients to be done running which means that we need to set a global flag that checks for that efficiently
        if self.client and self.client.is_connected:
            self.loop.run_until_complete(self.client.disconnect())
            # update connection state once more
            self.update_connection_status(DISCONNECTED_STATUS_MESSAGE)
        self.loop.close()

    async def async_connect_to_device(self):
        async with BleakClient(self.address) as client:
            self.client = client
            try:
                self.update_state(CONNECTED_STATUS_MESSAGE)
                print(f"Successful connection of {self.address}")
                self.log = "Connection Successful"
                await self.fetch_stream(RESISTANCE_CHARACTERISTIC_UUID, TIMESTAMP_CHARACTERISTIC_UUID) 
                # In the future, we may need to accoomodate for more characteristics
                # we will then change the fetch_stream method to handle this. --> create expandable list to select from during the calibration step then connect to each characteristic from there
                # This will look like Step 1: choose characteristics Step 2: Begin Calibration
                # This would then mean that we need to
                while self.connection_status != DISCONNECTED_STATUS_MESSAGE:
            # we do not disconnect --> check every second/don't wanna do it too often or it just eats up space in the stack
                    await asyncio.sleep(0.5)
            except Exception as e:
                print(self.address, e)
                self.update_state(DISCONNECTED_STATUS_MESSAGE)
                self.log = e

    def update_state(self, status):
        self.connection_status = status
        self.parent.update_connection_status(self.address, status)
    
    def update_calibration_state(self, status):
        self.is_calibrated = True
        self.parent.update_calibration_status(self.address, status)
    
    def gen_calib_formula(self):
        self.m = (self.calibration_values["max"][1]-self.calibration_values["min"][1])/(self.calibration_values["max"][0]-self.calibration_values["min"][0])
        self.c = self.calibration_values["max"][1] - self.m*self.calibration_values["max"][0]
    
    def get_calibrated_value(self, value):
        # we assume linear calibration for now
        cal_val = self.m*value + self.c
        return cal_val
    
def res_notification_handler(self, sender, data):
    # Unpack the 2-byte half-precision float and 3-byte timestamp
    half_precision, timestamp_bytes = data[:2], data[2:]
    
    # Convert half-precision bytes to float
    resistance = np.frombuffer(half_precision, dtype=np.float16)[0]
    
    # Convert 3-byte timestamp to integer
    timestamp = int.from_bytes(timestamp_bytes, byteorder='big')
    
    if self.data_handler.is_plotting:
        self.y_values.append(resistance)
        print(resistance)
        if self.data_handler.is_calibrated:
            self.y_calibrated.append(self.get_calibrated_value(resistance))

        if not self.reference_time:
            self.reference_time = timestamp
        self.x_values.append(timestamp - self.reference_time)
        print(timestamp)
    
    self.curr_y = resistance
    self.curr_x = timestamp

    # def time_notification_handler(self, sender, data):
    #     value = struct.unpack("<I", data)[0]
    #     if self.parent.is_plotting:
    #         if not self.reference_time:
    #             self.reference_time = value
    #         self.x_values.append(round((value-self.reference_time)/1000,3))

    async def fetch_stream(self, core_characteristic, time_characteristic):
        pass
        if self.client and self.client.is_connected:
            try:
                await self.client.start_notify(core_characteristic, self.res_notification_handler)
                # await self.client.start_notify(time_characteristic, self.time_notification_handler)
            except Exception as e:
                print(f"failed to connect to BLECharacteristics")
                self.log = e
                print(e)
        else:
            print(self.client)
            print(self.client.is_connected)
            print("client not connected")

    def disconnect_client(self):
        self.update_state(DISCONNECTED_STATUS_MESSAGE)
    
    def get_index(self,values,target)->int:
        if target >= values[-1]: 
            return len(values)
        elif target <= values[0]:
            return 0
        else:
            idx = 0
            while values[idx]<target:
                idx += 1
            return idx
    
    def gen_temp(self,x_min, x_max):
        # align the length of the lists
        if self.is_calibrated:
            min_len = min([len(self.x_values), len(self.y_values),len(self.y_calibrated)])
            self.x_values = self.x_values[:min_len]
            self.y_values = self.y_values[:min_len]
            self.y_calibrated = self.y_calibrated[:min_len]
        else:
            min_len = min([len(self.x_values), len(self.y_values)])
            self.x_values = self.x_values[:min_len]
            self.y_values = self.y_values[:min_len]
        # find left_pointer
        start = self.get_index(self.x_values, x_min)
        # find right_pointer
        end = self.get_index(self.x_values, x_max)
        # generate new values and save "full" values
        try:
            self.x_values_full = self.x_values.copy()
            self.y_values_full = self.y_values.copy()
            self.y_calibrated_full = self.y_calibrated.copy()
            self.x_values = self.x_values[start:end]
            self.y_values = self.y_values[start:end]
            self.y_calibrated = self.y_calibrated[start:end]
        except IndexError:
            # we do not bother to plot any difference...
            self.x_values = self.x_values_full
            self.y_values = self.y_values_full
            self.y_calibrated = self.y_calibrated_full


class LiteForm(tk.Frame):
    def __init__(self, parent, client:LiteClient):
        super().__init__()
        self.parent = parent
        self.client = client # parent in this case would be the GUIClient as each form is unique to the GUIClient
        # load in existing values if any --> this would be important if we are changing the calibrated values...
        self.grid()
        self.values = self.client.calibration_values

        # Title --> The device address
        self.header = tk.Label(self.parent, text=self.client.address)
        self.header.grid(row=0,column=0,columnspan=3)

        # Entry for truth values
        self.truth_label = tk.Label(self.parent, text="User Input")
        self.truth_label.grid(row=1, column=2)
        self.user_input_max = tk.Entry(self.parent, foreground="black", background="white")
        self.user_input_max.grid(row=3, column=2)
        self.user_input_min = tk.Entry(self.parent, foreground="black", background="white")
        self.user_input_min.grid(row=2, column=2)

        # Display for raw data
        self.raw_label = tk.Label(self.parent, text="Raw Data")
        self.raw_label.grid(row=1, column=1)
        self.raw_min = tk.StringVar(self.parent, value=str(self.values["min"][0]))
        self.raw_max = tk.StringVar(self.parent, value=str(self.values["max"][0]))
        self.raw_min_label = tk.Label(self.parent, textvariable=self.raw_min)
        self.raw_max_label = tk.Label(self.parent, textvariable=self.raw_max)
        self.raw_max_label.grid(row=3, column=1)
        self.raw_min_label.grid(row=2, column=1)

        self.max_label = tk.Label(self.parent, text="Max Value: ")
        self.max_label.grid(row=3, column=0)
        self.min_label = tk.Label(self.parent, text="Min Value: ")
        self.min_label.grid(row=2, column=0)

        # Calibrate Button
        self.min_button = tk.Button(self.parent, text="Get Raw Min", command=self.min_calibrate)
        self.min_button.grid(row=4, column=0)
        self.max_button = tk.Button(self.parent, text="Get Raw Max", command=self.max_calibrate)
        self.max_button.grid(row=4, column=1)

        # Save button
        self.update_button = tk.Button(self.parent, text="Update", command=self.save_calibration)
        self.update_button.grid(row=4,column=2)

    def calibration_data(self)->list[float]:
        data = [self.client.curr_y]
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

    def min_calibrate(self):
        data = self.calibration_data()
        # for now the logic is just to take the minimum value of the list
        self.values["min"][0] = min(data)
        self.raw_min.set(str(self.values["min"][0]))
    
    def max_calibrate(self):
        data = self.calibration_data()
        self.values["max"][0] = max(data)
        self.raw_max.set(str(self.values["max"][0]))
    

    def save_calibration(self):
        # command associated with the save calibration button
        try:
            self.update_truth() # checks calibration values and saves them
            self.client.calibration_values = self.values # pushes the values to the client 
            self.client.gen_calib_formula()
            self.client.update_calibration_state(CALIBRATED_STATUS_MESSAGE)

        except ValueError:
            pass


class GUIApp(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.grid()
        self.clients = [] # list to store connected devices
        self.selected_devices = []
        self.save_dir = "save_lite"
        self.config_dir = "save_lite/session_notes"
        self.session_config, self.config_fp = self.get_config()
        self.session_files = self.get_session_files() # stores the files of the session

        self.scan_status = tk.StringVar(value="Device Scan")
        self.scan_button = ttk.Button(self, textvariable=self.scan_status, command=self.scan_for_devices)
        self.scan_button.grid(row=0, column=0)
        self.connection_type = tk.StringVar(value=CONNECT_STATE)
        self.connect_button = ttk.Button(self, textvariable=self.connection_type, command=self.connect_selected_devices)
        self.connect_button.grid(row=0, column=1)
        self.connection_status = tk.StringVar(value=DISCONNECTED_STATUS_MESSAGE)
        self.connection_label = ttk.Label(self, textvariable=self.connection_status)
        self.connection_label.grid(row=0, column=2)

        # create treeview to display connected devices
        self.client_status = ttk.Treeview(self, selectmode=tk.EXTENDED)
        self.client_status["columns"] = ("one", "two", "three")
        self.client_status.grid(row=1, column=0, columnspan=3)
        self.client_status.column("#0", width=0, stretch=tk.NO)
        self.client_status.column("one", width=150, minwidth=150, stretch=tk.NO)
        self.client_status.column("two", width=150, minwidth=150, stretch=tk.NO)
        self.client_status.column("three", width=150, minwidth=150, stretch=tk.NO)

        # Define headings
        self.client_status.heading("#0", text="", anchor=tk.W)
        self.client_status.heading("one", text="Name", anchor=tk.W)
        self.client_status.heading("two", text="Address", anchor=tk.W)
        self.client_status.heading("three", text="Status", anchor=tk.W)

        # Create form to load in calibration menu
        self.calibration_label = tk.Label(self, text="Calibration Form")
        self.calibration_label.grid(row=2, column=0, columnspan=2, sticky="w")
        self.calibration_button = tk.Button(self, text="Calibrate", command=self.load_form)
        self.calibration_button.grid(row=2, column=2)
        self.calibration_form = tk.Frame(self)
        self.calibration_form.grid(row=3, column=0, columnspan=3)

        self.client_status.bind("<<TreeviewSelect>>", self.on_item_selected)

        self.graph_book = MultiTabFrame(self)
        self.graph_book.grid(row=0, column=4, rowspan=100)
        self.graph = FixedStream(self.graph_book,self)
        self.graph_book.add_tab(self.graph, "Live Plot")
        self.edit_graph = SaveRecording(self.graph_book, self)
        self.graph_book.add_tab(self.edit_graph, "Save Data")
        self.save_page = UploadPage(self.graph_book, self)
        self.graph_book.add_tab(self.save_page, "Upload Files")
        self.graph_book.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # State Variables
        self.is_scanning = False
        self.is_calibrated = False
        self.is_connected = False
        self.is_plotting = False
    
    def get_config(self):
        for filename in os.listdir(self.config_dir):
            if filename == f"{date.today()}.json":
                with open(os.path.join(self.config_dir, filename),"r") as f:
                    config = json.load(f)
                    return config, os.path.join(self.config_dir,filename)
        # if no prior config has been established, then we create a file for it along with a dictionary
        config = {"session_id": str(date.today())}
        with open(os.path.join(self.config_dir,f"{date.today()}.json"), "w") as f:
            json.dump(config,f)
        return config,os.path.join(self.config_dir,f"{date.today()}.json")

    def get_session_files(self):
        session_files = []
        date_str = str(date.today())
        for filename in os.listdir(self.save_dir):
            if date_str in filename:
                session_files.append(filename)
        return session_files

    def on_item_selected(self,event):
        self.selected_devices = [self.client_status.item(item_id)["values"] for item_id in self.client_status.selection()]
        # print(self.selected_devices)
    
    def scan_for_devices(self):
        if not self.is_scanning:
            self.is_scanning = True
            self.scan_status.set("Scanning...")
            Thread(target=self.async_scan_for_devices, daemon=True).start()

    def async_scan_for_devices(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.perform_scan())
        loop.close()
        self.scan_status.set("Device Scan")
        self.is_scanning = False

    async def perform_scan(self):
        try:
            # Run discovery for 10 seconds
            for item in self.client_status.get_children():
                self.client_status.delete(item)
            devices = await asyncio.wait_for(BleakScanner.discover(), 10.0) # Scan for 10 sec
            self.devices = [(device.name, device.address, DISCONNECTED_STATUS_MESSAGE) for device in devices if device.name]

            for item in self.devices:
                self.client_status.insert("", tk.END, values=item)

        except asyncio.TimeoutError:
            # In case of timeout (which should not happen here), just pass
            self.scan_button.config(text="Failed Scan", state="normal") # We allow for another scan but acknowledge a failed scan due to timeout

    def connect_selected_devices(self):
        # clear all unselected values 
        selected_devices = self.selected_devices.copy()
        for item in self.client_status.get_children():
            self.client_status.delete(item)
        for item in selected_devices:
            self.client_status.insert("", tk.END, values=item)

        if self.connection_type.get() == CONNECT_STATE:
            # we check for selected devices 
            if selected_devices:
                self.connection_type.set(CONNECTING_STATE)
            for selected_device in selected_devices:
                if isinstance(selected_device[1],str): # Check that the extracted values are correct
                    address = selected_device[1]  # Extract the address from the dropdown value
                    client = LiteClient(address, self)
                    thread = Thread(target=client.thread_management_connection, daemon=True).start()
                    self.clients.append(client) # update global reference of client list

        else:
            # we disconnect all clients
            for client in self.clients: # Note that client here is GUIClient. To access BleakClient, we get client.client
                if client.client and client.client.is_connected:
                    client.disconnect_client()
            self.connection_type.set(CONNECT_STATE)
    
    def update_connection_status(self, address, status):
        updated_item = None
        for item_id in self.client_status.get_children():
            if self.client_status.item(item_id)["values"][1] == address:
                self.client_status.item(item_id, values=(self.client_status.item(item_id)["values"][0],address, status))
                updated_item = self.client_status.item(item_id)["values"]
        if updated_item:
            if all([(self.client_status.item(item_id)["values"][2]==CONNECTED_STATUS_MESSAGE or self.client_status.item(item_id)["values"][2]==CALIBRATED_STATUS_MESSAGE)
                     for item_id in self.client_status.get_children()]):
                self.connection_status.set(CONNECTED_STATUS_MESSAGE)
                self.connection_type.set(DISCONNECT_STATE)
            else:
                self.connection_status.set(DISCONNECTED_STATUS_MESSAGE)
    
    def load_form(self):
        # get selected client
        print("test")
        selection = [self.client_status.item(item_id)["values"] for item_id in self.client_status.selection()]

        print(f"these are the selected devices {selection}")
        if selection:
            selected_address = selection[0][1]
            selected_device = None
            for client in self.clients:
                if client.address == selected_address:
                    selected_device = client
            
            # we delete the existing form if any
            if self.calibration_form.winfo_children():
                for widget in self.calibration_form.winfo_children():
                    widget.destroy()
            LiteForm(self.calibration_form,selected_device)

    def update_calibration_status(self, address, status):
        updated_item = None
        for item_id in self.client_status.get_children():
            if self.client_status.item(item_id)["values"][1] == address:
                self.client_status.item(item_id, values=(self.client_status.item(item_id)["values"][0],address, status))
                updated_item = self.client_status.item(item_id)["values"]
                self.graph.radio_both.config(state=tk.ACTIVE)
                self.graph.radio_calibrated.config(state=tk.ACTIVE)

        if updated_item:
            if all([self.client_status.item(item_id)["values"][2]==CALIBRATED_STATUS_MESSAGE for item_id in self.client_status.get_children()]):
                self.is_calibrated = True
                # insert logic to turn plot option radio buttons active...
            else:
                self.is_calibrated = False

    def on_tab_changed(self,event):
        selected_tab_index = self.graph_book.index(self.graph_book.select())
        selected_tab_text = self.graph_book.tab(selected_tab_index, "text")
        if selected_tab_text == "Save Data":
            selected_frame = self.graph_book.nametowidget(self.graph_book.select())
            if hasattr(selected_frame, 'graph'):
                selected_frame.file_name_entry.delete(0,tk.END)
                selected_frame.file_name_entry.insert(0,selected_frame.default_name())
                selected_frame.plot_type = self.graph.plot_type
                selected_frame.graph.update_plot()

root = tk.Tk()
app = GUIApp(master=root)
app.mainloop()


