import numpy as np
import tkinter as tk
import json
import csv

class DataHandler:
    # handles the data after one pass
    def __init__(self, parent):
        self.clients = []
        
        # object references
        self.connection_handler = None
        self.calibration_handler = None
        self.display_handler = None

        # data variables
        self.frequency = None

        # state variables
        self.is_connected = False
        self.is_calibrated = False
        self.is_plotting = False
        
    def enable_calibration(self):
        if all([client.connection_status == 1 for client in self.clients]) and self.frequency:
            self.calibration_handler.nested_enable() # if all clients have connected and we have a recognized frequency, we enable calibration
        
    def update_calibration_status(self):
        if all([client.is_calibrated for client in self.clients]):
            self.is_calibrated = True
            self.display_handler.update_plot_options()
        else:
            self.is_calibrated = False
            self.display_handler.update_plot_options()