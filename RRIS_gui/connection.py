import tkinter as tk
import tkinter.ttk as ttk
from bleak import BleakScanner, BleakClient
import asyncio
import struct
from threading import Thread
from utils import DeviceCheckbox, MultiTabFrame, LiveRowDisplay
from utils import freq_to_ms, invert_frequency_format, frequency_display_format, valid_cab
from constants import RESISTANCE_CHARACTERISTIC_UUID,TIMESTAMP_CHARACTERISTIC_UUID,FREQUENCY_CHARACTERISTIC_UUID,FREQUENCY_CHOICES
import numpy as np

# Global State Values
CONNECT_STATE = "Connect"
CONNECTING_STATE = "Connecting"
DISCONNECT_STATE = "Disconnect"

CONNECTED_STATUS_MESSAGE = "Connected"
CONNECTING_STATUS_MESSAGE = "Connecting"
DISCONNECTED_STATUS_MESSAGE = "Not Connected"

class ConnectionApp(tk.Frame):
    # handles widget and display of information
    def __init__(self, parent, data_handler, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.parent = parent
        self.data_handler = data_handler
        self.grid()
        self.handler = ConnectionHandler(self)

        self.widget_title = tk.Label(self,text="Connection and Calibration")
        self.widget_title.grid(row=0,column=0,columnspan=4)

        self.connection_display = MultiTabFrame(self)
        self.devices_menu = DeviceCheckbox(self.connection_display)
        self.connection_status_menu = LiveRowDisplay(self.connection_display)
        
        self.connection_display.add_tab(self.devices_menu, "Available Devices")
        self.connection_display.add_tab(self.connection_status_menu, "Connection Status Menu")
        self.connection_display.grid(row=3,column=0,sticky="NSEW", columnspan=4)

        # Scan Button
        self.scan_button = tk.Button(self, text="Start Scan", command=self.handler.scan_for_devices)
        self.scan_button.grid(row=1,column=0, padx=(10,0))

        # Connect Button - initialized as disabled until at least one checkbox is ticked
        self.connection_mode = tk.StringVar(value=CONNECT_STATE)
        self.connect_button = tk.Button(self, textvariable=self.connection_mode, command=self.handler.connect_selected_devices, state="disabled")
        self.connect_button.grid(row=1,column=1)

        # Display Connection Status
        self.connection_status_label = tk.Label(self, text="Status: ")
        self.connection_status_label.grid(row=2, column=0, sticky="e", padx=(10,0))
        self.connection_state = tk.StringVar(value=DISCONNECTED_STATUS_MESSAGE)
        self.connection_state_message = tk.Label(self, textvariable=self.connection_state, fg="red")
        self.connection_state_message.grid(row=2, column=1, sticky="w")
    
        # Frequency Combobox
        self.frequency_title = tk.Label(self, text="Select Data Frequency")
        self.frequency_title.grid(row=1, column=2)
        self.frequency_button = tk.Button(self, text="Change Hz", command=self.handler.set_frequency)
        self.frequency_button.grid(row=1, column=3, padx=(0,10))
        self.frequency_combobox = ttk.Combobox(self, values=[frequency_display_format(freq) for freq in FREQUENCY_CHOICES], state="readonly")
        self.frequency_combobox.set(frequency_display_format(FREQUENCY_CHOICES[0])) # Set default value
        self.frequency_combobox.grid(row=2, column=2, columnspan=2)


class GUIClient:
    def __init__(self, address, connection_handler):
        super().__init__() # inherit data handling methods
        self.address = address
        self.connection_handler = connection_handler # we need to pass in the parent handler as a slave node as we will receive instructions from the master/parent
        self.data_handler = connection_handler.data_handler
        self.log = "" # logs the error messages

        # Data variables
        self.calibration_values = {"max":[None, None], "min":[None, None]} # 0th index is the raw data and 1st index is the user input value
        self.y_values = [] # Contains key-value pair as "Label": [raw data] --> here "Label" being the name of the characteristic (angle, temp, etc.)
        self.y_calibrated = [] # Contains key-value pair as "Label": [calibrated] --> shares same label
        self.x_values = [] # Contains key-value pair as "Label" --> shares same label
        self.curr_y = None
        self.curr_x = None
        self.reference_time = None
        
        # state variables
        self.is_calibrated = False # Currently the logic for calibration is not written yet so we just set the flag to be true
        self.connection_status = 0
        self.is_recording = False # flag to check if we should plot values


    def thread_management_connection(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.connect_task = self.loop.create_task(self.async_connect_to_device())
        self.loop.run_until_complete(self.connect_task)
        # we need to wait for all clients to be done running which means that we need to set a global flag that checks for that efficiently
        if self.client and self.client.is_connected:
            self.loop.run_until_complete(self.client.disconnect())
            # update connection state once more
            self.update_connection_status(-1)
        self.loop.close()

    async def async_connect_to_device(self):
        async with BleakClient(self.address) as client:
            self.client = client
            try:
                self.update_connection_status(1)
                print(f"Successful connection of {self.address}")
                self.log = "Connection Successful"
                await self.write_frequency()
                await self.fetch_stream(RESISTANCE_CHARACTERISTIC_UUID, TIMESTAMP_CHARACTERISTIC_UUID) 
                # In the future, we may need to accoomodate for more characteristics
                # we will then change the fetch_stream method to handle this. --> create expandable list to select from during the calibration step then connect to each characteristic from there
                # This will look like Step 1: choose characteristics Step 2: Begin Calibration
                # This would then mean that we need to 
                await self.stop_stream()
            except Exception as e:
                print(self.address, e)
                self.update_connection_status(-1)
                self.log = e

    async def write_frequency(self):
        while not self.connection_handler.frequency:
            await asyncio.sleep(1)
            print("waiting for frequency selection")
        if self.client and self.client.is_connected:
            try:
                # Assuming 'gatt_characteristic_uuid' is the UUID string of the characteristic you want to write to
                gatt_characteristic_uuid = FREQUENCY_CHARACTERISTIC_UUID
                await self.client.write_gatt_char(gatt_characteristic_uuid, freq_to_ms(self.connection_handler.frequency).to_bytes(2, byteorder='little'))
                print(f"Frequency of {self.address} set to {self.connection_handler.frequency} Hz on the BLE device.")
                self.log = "Frequency Written!"
                self.data_handler.frequency = self.connection_handler.frequency # here we update the data_handler's frequency attribute which is used as a flag for allowing calibration and plotting
                self.data_handler.enable_calibration()
            except Exception as e:
                print(f"Failed to set frequency: {e}")
                self.log = e
        else:
            print(self.client)
            print(self.client.is_connected)
            print("client not connected")
            self.log = "Client is Disconnected"
    
    def gen_calib_formula(self):
        self.m = self.calibration_values["max"][1]-self.calibration_values["min"][1]/self.calibration_values["max"][0]-self.calibration_values["min"][0]
        self.c = self.calibration_values["max"][1] - self.m*self.calibration_values["max"][0]
    
    def get_calibrated_value(self, value):
        # we assume linear calibration for now
        cal_val = self.m*value + self.c
        return cal_val
        
    def res_notification_handler(self, sender, data):
        resistance, timestamp = struct.unpack('fI', data)
        if self.data_handler.is_plotting:
            self.y_values.append(resistance)
            print(resistance)
            if self.data_handler.is_calibrated:
                self.y_calibrated.append(self.get_calibrated_value(resistance))

            if not self.reference_time:
                self.reference_time = timestamp
            self.x_values.append(timestamp-self.reference_time)
            print(timestamp)
        self.curr_y = resistance
        self.curr_x = timestamp
        # print(value)

    # def time_notification_handler(self, sender, data):
    #     value = struct.unpack("<I", data)[0]
        
    #     if self.data_handler.is_plotting:
    #         if not self.reference_time:
    #             self.reference_time = value
    #         self.x_values.append(value-self.reference_time)
    #         print(value)

    #     self.curr_x = value
    #     # print(value)
    
    async def get_xy(self,core_characteristic, time_characteristic):
        await self.client.start_notify(core_characteristic, self.res_notification_handler)
        # await self.client.start_notify(time_characteristic, self.time_notification_handler)

    async def fetch_stream(self, core_characteristic, time_characteristic):
        if self.client and self.client.is_connected:
            try:
                await self.get_xy(core_characteristic,time_characteristic)
            except Exception as e:
                print(f"failed to connect to BLECharacteristics")
                self.log = e
                print(e)
        else:
            print(self.client)
            print(self.client.is_connected)
            print("client not connected")

    async def stop_stream(self):
        while self.connection_status != -1:
            # we do not disconnect --> check every second/don't wanna do it too often or it just eats up space in the stack
            await asyncio.sleep(0.5)
    
    def update_connection_status(self, update):
        self.connection_status = update
        # ping the update connection state of parent
        self.connection_handler.check_connection_status()
    
    def update_calibration(self, calibration_values):
        if valid_cab(calibration_values):
            self.calibration_values = calibration_values
            self.is_calibrated = True
        # the format of calibration_values is a dictionary {"min":[raw,reference_truth],"max":[raw,reference_truth]}

    def start_recording(self):
        if self.is_calibrated: # only allow for recording if calibrated --> will set a toggle to turn off this requirement down the road
            # we clear all previous values and start recording again
            self.x_values = {}
            self.y_calibrated = {}
            self.y_values = {}
            self.is_recording = True

    def stop_recording(self):
        self.is_recording = False
    
    def clear_data(self):
        self.x_values = {}
        self.y_calibrated = {}
        self.y_values = {}
    
    def disconnect_client(self):
        self.update_connection_status(-1) # this allows for connection to occur once more
        self.data_handler.clients.remove(self) # we remove self from the recognized devices

class ConnectionHandler:
    # handles the asynchronous connection and data reading
    def __init__(self, display_frame):
        self.devices = []
        self.display = display_frame
        self.data_handler = display_frame.data_handler # inherits the data_handler
        self.data_handler.connection_handler = self # we save a pointer to the connection handler object so other objects can reference it in a more readable manner
        self.is_scanning = False
        self.frequency = None

    def scan_for_devices(self):
        if not self.is_scanning:
            self.is_scanning = True
            self.display.scan_button.config(text="Scanning...", state="disabled")
            Thread(target=self.async_scan_for_devices, daemon=True).start()

    def async_scan_for_devices(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.perform_scan())
        loop.close()
        self.is_scanning = False
    
    async def perform_scan(self):
            try:
                # Run discovery for 10 seconds
                devices = await asyncio.wait_for(BleakScanner.discover(), 10.0) # Scan for 10 sec
                self.devices = [(device.name, device.address) for device in devices if device.name]
                self.data_handler.devices = self.devices # we also save a copy of the available devices to data_handler, this may come in handy when logging errors

                # Update the devices dropdown on the GUI thread
                self.populate_device_checkbox()

            except asyncio.TimeoutError:
                # In case of timeout (which should not happen here), just pass
                self.display.scan_button.config(text="Failed Scan", state="normal") # We allow for another scan but acknowledge a failed scan due to timeout
    
    def populate_device_checkbox(self):
        self.display.devices_menu.update([f"{device[0]} {device[1]}" for device in self.devices if device[0]])
        self.display.scan_button.config(text="Start Scan", state="normal") # we reset the scan button to allow for a new scan
    
    def get_selected_devices(self):
        selected_devices = [device for (checkbox, device) in self.display.devices_menu.checkboxes if checkbox.get()] # list comprehension for getting the indices of selected devices
        # check error
        return selected_devices

    def connect_selected_devices(self):
        if self.display.connection_mode.get() == CONNECT_STATE:
            # we check for selected devices 
            selected_devices = self.get_selected_devices()
            if selected_devices:
                self.display.connection_mode.set(CONNECTING_STATE)
                self.display.connect_button.config(state="disabled")
            for selected_device in selected_devices:
                if isinstance(selected_device,str): # Check that the extracted values are correct
                    address = selected_device.split(" ")[1]  # Extract the address from the dropdown value
                    client = GUIClient(address, self)
                    thread = Thread(target=client.thread_management_connection, daemon=True).start()
                    self.data_handler.clients.append(client) # update global reference of client list
        else:
            # we disconnect all clients
            for client in self.data_handler.clients: # Note that client here is GUIClient. To access BleakClient, we get client.client
                if client.client and client.client.is_connected:
                    client.disconnect_client()

    def check_connection_status(self): # Build this logic in later
        if all([client.connection_status == 1 for client in self.data_handler.clients]):
            status = CONNECTED_STATUS_MESSAGE
            color = "green"
        elif any([client.connection_status == -1 for client in self.data_handler.clients]):
            status = DISCONNECTED_STATUS_MESSAGE
            color = "red"
        else:
            status = CONNECTED_STATUS_MESSAGE
            color = "orange"
        
        self.update_connection_menu()

        self.display.connection_state.set(status)
        self.display.connection_state_message.config(fg=color)

        if status == CONNECTED_STATUS_MESSAGE:
            self.display.connection_mode.set(DISCONNECT_STATE)
            self.display.connect_button.config(state="normal")
        elif status == DISCONNECTED_STATUS_MESSAGE:
            self.display.connection_mode.set(CONNECT_STATE)
            self.display.connect_button.config(state="normal")
        else:
            self.display.connection_mode.set(CONNECTING_STATE)
            self.display.connect_button.config(state="disabled")

    def set_frequency(self):
        self.frequency = invert_frequency_format(self.display.frequency_combobox.get())

    def update_connection_menu(self):
        # this prompts the connection menu to be updated
        pass


if __name__=="__main__":
    # testing the connection logic
    root = tk.Tk()
    root.title("Test Connection Widget")
    connect_app = ConnectionApp(root)
    connect_app.mainloop()