import tkinter as tk
import tkinter.ttk as ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
import numpy as np
import seaborn as sns
import asyncio
from utils import MultiTabFrame
import time
import os
from datetime import date
import csv
from itertools import zip_longest

VIEW_MODE = "View Mode"
CLIPPING_MODE = "Clipping Mode"

class DisplayApp(tk.Frame):
    # handles the data display and refresh
    def __init__(self, parent, data_handler):
        super().__init__(parent)
        self.grid()
        self.screen_title = tk.Label(self, text="Graphing Screen")
        self.screen_title.grid(row=0, column=0, sticky="")
        self.data_handler = data_handler
        self.handler = GraphHandler(self, data_handler)

        self.display_screen = MultiTabFrame(self)
        self.display_screen.bind("<<NotebookTabChanged>>", self.handler.on_tab_switch)
        self.non_stop_stream = NonstopStream(self.display_screen, self.data_handler)
        self.fixed_stream = FixedStream(self.display_screen, self.data_handler)
        self.edit_stream = SaveRecording(self.display_screen,self.data_handler)

        
        self.display_screen.add_tab(self.non_stop_stream, "Free-Mode")
        self.display_screen.add_tab(self.fixed_stream, "Fixed-Mode")
        self.display_screen.add_tab(self.edit_stream, "Save Data")

        self.display_screen.grid(row=1, column=0, sticky="NSEW")

class SaveRecording(tk.Frame):
    def __init__(self, parent:MultiTabFrame, data_handler):
        super().__init__(parent)
        self.parent = parent
        self.data_handler = data_handler
        self.plot_type = None
        self.graph = GraphDisplay(self, self.data_handler)
        self.graph.grid(row=0, column=0, columnspan=3)
        self.clip_mode = tk.StringVar(self, value="Clip Data")
        self.change_state = tk.StringVar(self, value="Show Change")
        self.clip_button = ttk.Button(self, textvariable=self.clip_mode, command=self.clip_data)
        self.clip_button.grid(row=1, column=0)
        self.save_changes_button = ttk.Button(self, text="Save Changes", command=self.graph.save_changes) # overwrites the data and replots
        self.save_changes_button.grid(row=1, column=1)
        self.del_changes_button = ttk.Button(self, text="Delete Changes", command=self.graph.delete_changes) # replots the previous data and clears rectangle
        self.del_changes_button.grid(row=1, column=2)

        self.save_file_button = ttk.Button(self, text="Save File (.csv)", command=self.save_file)
        self.save_file_button.grid(row=2, column=2)
        self.file_name_entry = ttk.Entry(self)
        self.file_name_entry.insert(0,self.default_name())
        self.file_name_entry.grid(row=2, column=0, columnspan=2)
    
    def clip_data(self):
        if self.clip_mode.get()=="Clip Data":
            self.graph.plot_interactor.disconnect_regular_events()
            self.graph.plot_interactor.connect_clipping_event()
            self.graph.interaction_mode.set(CLIPPING_MODE)
            self.clip_mode.set("Exit Clip Mode")
        elif self.clip_mode.get()=="Exit Clip Mode":
            if self.graph.plot_interactor.x_min and self.graph.plot_interactor.x_max:
                self.graph.plot_interactor.disconnect_clipping_event()
                self.graph.plot_interactor.connect_regular_events()
                self.graph.interaction_mode.set(VIEW_MODE)
                self.clip_mode.set("Clip Data")

    def default_name(self):
        # default name is date_session_no._descriptor.csv
        current_date = date.today()
        self.data_handler.session_files.sort() # last value now has the highest index
        try:
            max_index = int(self.data_handler.session_files[-1].split("_")[1])
        except IndexError:
            max_index = 0
        return f"{current_date}_{max_index+1}_{len(self.data_handler.clients)}_Devices.csv"

    def save_file(self):
        file_name = self.file_name_entry.get()
        if ".csv" not in file_name:
            file_name = file_name.split(".")[0]+".csv"
        self.data_handler.session_files.append(file_name)

        data = []
        col_names = []
        for client in self.data_handler.clients:
            name = client.address
            data.append(client.x_values)
            col_names.append(f"{name}_time (s)")
            data.append(client.y_values)
            col_names.append(f"{name}_raw_resistance")
            if client.y_calibrated:
                data.append(client.y_calibrated)
                col_names.append(f"{name}_calibrated_angle")
        data_transposed = zip_longest(*data, fillvalue="")

        with open(os.path.join(self.data_handler.save_dir, file_name),"w", newline="") as f:
            writer = csv.writer(f)

            writer.writerow(col_names)
            writer.writerows(data_transposed)
        
        print(f"Saved {file_name}")


class NonstopStream(tk.Frame):
    # this class hold the graph display along with logic for starting and stopping stream
    def __init__(self, parent:MultiTabFrame, data_handler):
        super().__init__(parent)
        self.parent = parent # parent here is ttk.Notebook
        self.data_handler = data_handler
        self.graph = GraphDisplay(self, self.data_handler)
        self.graph.grid(row=4, column=0, columnspan=4)

        # StringVar to track the selection
        self.plot_type = tk.StringVar(value="Raw")

        # Label for "Plot Type"
        label = tk.Label(self, text="Plot Type: ")
        label.grid(row=3, column=0)

        # Radio buttons
        self.radio_raw = tk.Radiobutton(self, text="Raw", variable=self.plot_type, value="Raw")
        self.radio_calibrated = tk.Radiobutton(self, text="Calibrated", variable=self.plot_type, value="Calibrated", state=tk.DISABLED)
        self.radio_both = tk.Radiobutton(self, text="Both", variable=self.plot_type, value="Both", state=tk.DISABLED)

        # Arrange radio buttons horizontally using grid
        self.radio_raw.grid(row=3, column=1)
        self.radio_calibrated.grid(row=3, column=2)
        self.radio_both.grid(row=3, column=3)
    
    def update_options(self):
        self.radio_calibrated.config(state=tk.ACTIVE)
        self.radio_both.config(state=tk.ACTIVE)

class FixedStream(tk.Frame):
    # this class hold the graph display along with logic for starting a stream for a set duration
    def __init__(self, parent:MultiTabFrame, data_handler):
        super().__init__(parent)
        self.parent = parent # parent here is ttk.Notebook
        self.data_handler = data_handler
        self.graph = GraphDisplay(self, self.data_handler)
        self.graph.grid(row=4, column= 0, columnspan=4,sticky="")

        self.duration_label = tk.Label(self, text="Set Stream Duration (s): ")
        self.duration_label.grid(row=0, column=0, sticky="e")
        self.duration_entry = tk.Entry(self)
        self.duration_entry.bind("<Return>", self.on_return)
        self.duration_entry.grid(row=0, column=1, sticky="w", columnspan=2)
        self.countdown = tk.StringVar(value="Start Stream")
        self.start_button = tk.Button(self, textvariable=self.countdown, state=tk.DISABLED, command=self.start_stream)
        self.start_button.grid(row=1,column=0, sticky="")
        self.clear_button = tk.Button(self, text="Clear Graph", command=self.graph.clear_graph, state=tk.DISABLED) # initialized as disabled because there is no graph to clear
        self.clear_button.grid(row=1, column=1, sticky="")

        self.refresh_rate_label = tk.Label(self, text="Frame Rate: ")
        self.refresh_rate_label.grid(row=2, column=0, sticky="e")
        self.speed_scale = tk.Scale(self,from_=1,to=20,orient="horizontal",command=self.on_scale_change)
        self.speed_scale.grid(row=2, column=1, sticky="")
        self.frame_rate = 1

        # StringVar to track the selection
        self.plot_type = tk.StringVar(value="Raw")

        # Label for "Plot Type"
        label = tk.Label(self, text="Plot Type: ")
        label.grid(row=3, column=0)

        # Radio buttons
        self.radio_raw = tk.Radiobutton(self, text="Raw", variable=self.plot_type, value="Raw")
        self.radio_calibrated = tk.Radiobutton(self, text="Calibrated", variable=self.plot_type, value="Calibrated", state=tk.DISABLED)
        self.radio_both = tk.Radiobutton(self, text="Both", variable=self.plot_type, value="Both", state=tk.DISABLED)

        # Arrange radio buttons horizontally using grid
        self.radio_raw.grid(row=3, column=1)
        self.radio_calibrated.grid(row=3, column=2)
        self.radio_both.grid(row=3, column=3)

    def start_stream(self):
        counter = int(self.duration_entry.get())
        self.data_handler.is_plotting = True
        self.graph.update_plot()
        while counter > 0:
            self.countdown.set(str(counter))
            self.start_button.config(textvariable=self.countdown)
            self.update()
            counter -= 1
            time.sleep(1)
        self.data_handler.is_plotting = False
        self.countdown.set("Start Stream")
        self.clear_button.config(state=tk.ACTIVE)
            
    def on_scale_change(self,value):
        self.frame_rate = int(value)
        print(self.frame_rate)
    

    def on_return(self,event):
        try:
            value = self.duration_entry.get()
            self.duration = int(value)
            self.start_button.config(state=tk.ACTIVE)
        except ValueError:
            self.duration_entry.delete(0, tk.END)
            self.duration_entry.insert(0, "Please Enter a valid number")
    
    def update_options(self):
        self.radio_calibrated.config(state=tk.ACTIVE)
        self.radio_both.config(state=tk.ACTIVE)
    
class GraphDisplay(tk.Frame):
    def __init__(self,parent:tk.Frame, data_handler):
        super().__init__(parent)
        self.data_handler = data_handler
        self.parent = parent
        self.grid()
        self.x = []
        self.y = []

        # Graphing Variables
        self.fig = Figure()
        self.ax = self.fig.add_subplot(111)
        self.line = self.ax.plot(self.x, self.y, "r-", label = "Test Line")
        self.ax.autoscale(enable=True, axis='y', tight=True)
        self.ax.autoscale(enable=False, axis='x')

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=1, column=0, columnspan=3)

        # Create button for interacting with the plot
        self.interaction_mode = tk.StringVar(value=VIEW_MODE)

        # initialize plot interaction behaviour
        self.plot_interactor = DataInteractor(self)
        self.plot_interactor.connect_regular_events()

        # State variables
        self.is_plotting = False
        self.lines = []
    
    def clear_graph(self):
        # clear all client data
        for client in self.data_handler.clients:
            client.x_values = []
            client.y_values = []
            client.y_calibrated = []
            client.reference_time = None # reset the time reference
            
        self.update_plot()
    
    def update_plot(self): # this function has to be adapted to plot multiple lines based on client.x and client.y in self.clients
        # Update the plot's data
        # we clip the data such that the length of x and y are consistent
        clients = self.parent.data_handler.clients
        # print(self.parent.plot_type.get())
        if self.lines:
        # we set data instead of plotting over it
            if self.parent.plot_type.get() == "Both":
                for index, client in enumerate(clients):
                    min_length = min(len(client.x_values), len(client.y_values), len(client.y_calibrated))
                    x_data = client.x_values[:min_length]
                    y_data = client.y_values[:min_length]
                    y_calibrated = client.y_calibrated[:min_length]
                    self.lines[index].set_data(x_data, y_data)
                    self.lines[index+1].set_data(x_data, y_calibrated)

            elif self.parent.plot_type.get() == "Raw":
                for index, client in enumerate(clients):
                    min_length = min(len(client.x_values), len(client.y_values))
                    x_data = client.x_values[:min_length]
                    y_data = client.y_values[:min_length]
                    self.lines[index].set_data(x_data, y_data)
            else:
                for index, client in enumerate(clients):
                    min_length = min(len(client.x_values), len(client.y_calibrated))
                    x_data = client.x_values[:min_length]
                    y_calibrated = client.y_calibrated[:min_length]
                    self.lines[index].set_data(x_data, y_calibrated)
        else:
            # we plot new lines and append them to self.lines
            if self.parent.plot_type.get() == "Both":
                for index, client in enumerate(clients):
                    min_length = min(len(client.x_values), len(client.y_values), len(client.y_calibrated))
                    x_data = client.x_values[:min_length]
                    y_data = client.y_values[:min_length]
                    y_calibrated = client.y_calibrated[:min_length]
                    raw_line, = self.ax.plot(x_data,y_data)
                    calib_line, = self.ax.plot(x_data, y_calibrated)
                    self.lines.append(raw_line)
                    self.lines.append(calib_line)

            elif self.parent.plot_type.get() == "Raw":
                for index, client in enumerate(clients):
                    min_length = min(len(client.x_values), len(client.y_values))
                    x_data = client.x_values[:min_length]
                    y_data = client.y_values[:min_length]
                    line, = self.ax.plot(x_data, y_data)
                    self.lines.append(line)
            else:
                for index, client in enumerate(clients):
                    min_length = min(len(client.x_values), len(client.y_calibrated))
                    x_data = client.x_values[:min_length]
                    y_calibrated = client.y_calibrated[:min_length]
                    line, = self.ax.plot(x_data, y_calibrated)
                    self.lines.append(line)


        # Adjust the plot's x-axis limits for sliding effect
        try:
            self.ax.set_xlim(max([0, x_data[-1] - 10,x_data[0]]), x_data[-1])
        except:
            pass
        
        self.ax.relim()  # Recalculate limits
        self.ax.autoscale_view(scalex=False, scaley=True)  # Autoscale only y-axis

        # Re-draw the plot
        self.canvas.draw()
        
        # Call this function again after some time
        if self.data_handler.is_plotting:
            self.after(int(1000/self.parent.frame_rate), self.update_plot)

    def save_changes(self):
        # we do erase all the full values
        self.plot_temp()
        for client in self.data_handler.clients:
            if client.x_values_full and client.y_values_full:
                client.x_values_full = []
                client.y_values_full = []
        self.plot_interactor.x_max = None
        self.plot_interactor.x_min = None
        while self.plot_interactor.lines:
            self.plot_interactor.lines.pop().remove()
        if self.plot_interactor.shaded_area:
            self.plot_interactor.shaded_area.remove()
            self.plot_interactor.shaded_area = None
        self.update_plot()
        self.parent.clip_mode.set("Clip Data")
        self.interaction_mode.set(VIEW_MODE)

    def delete_changes(self):
        # we reset the data
        for client in self.data_handler.clients:
            if client.x_values_full and client.y_values_full:
                client.x_values = client.x_values_full
                client.y_values = client.y_values_full
                client.y_calibrated = client.y_calibrated_full
                client.x_values_full = []
                client.y_values_full = []
        self.plot_interactor.x_max = None
        self.plot_interactor.x_min = None
        while self.plot_interactor.lines:
            self.plot_interactor.lines.pop().remove()
        if self.plot_interactor.shaded_area:
            self.plot_interactor.shaded_area.remove()
            self.plot_interactor.shaded_area = None
        # we redraw the values
        self.update_plot()
        self.parent.clip_mode.set("Clip Data")
        self.interaction_mode.set(VIEW_MODE)

    def plot_temp(self):
        # we plot the temporary data
        x_min = self.plot_interactor.x_min
        x_max = self.plot_interactor.x_max
        if x_min and x_max:
            # get the left index
            # get the right index
            for client in self.data_handler.clients:
                # we get temp values for the plot
                client.gen_temp(x_min, x_max) # we overwrite the current data with the clipped data while saving the current data in another variable called values_full
        


# The DataCursor and DataInteractor objects are for controlling the interactivity of the graph
class DataCursor(object):
    def __init__(self, parent):
        self.ax = parent.ax
        self.mode = parent.mode
        self.line, = self.ax.plot(np.nan, np.nan, 'ro', markersize=10)
        self.vline = self.ax.axvline(color='blue', lw=1, alpha=0.3)
        self.annotation = self.ax.annotate(
            '', xy=(0, 0), xytext=(20, 20),
            textcoords='offset points', arrowprops=dict(arrowstyle='->'),
            bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="black", alpha=0.5))

        self.annotation.set_visible(False)
        self.previous_point = (None, None)
        self.ax.figure.canvas.mpl_connect('motion_notify_event', self)

    def __call__(self, event):
        if event.inaxes != self.ax or self.mode.get() != CLIPPING_MODE:
            return
        x, y = event.xdata, event.ydata
        self.vline.set_xdata(x)
        line = self.ax.get_lines()[0]
        xdata, ydata = line.get_data()
        index = np.abs(xdata - x).argmin()
        y = ydata[index]
        self.line.set_data(x, y)
        if (x, y) != self.previous_point:
            self.previous_point = (x, y)
            self.annotation.xy = (x, y)
            self.annotation.set_text(f'({x:.2f}ms, {y:.2f}\u00b0)')
            self.annotation.set_visible(True)
        else:
            self.annotation.set_visible(False)
        self.line.figure.canvas.draw_idle()

class DataInteractor:
    def __init__(self, parent):
        self.ax = parent.ax
        self.canvas = parent.canvas
        self.canvas_widget = parent.canvas_widget
        self.parent = parent
        self.mode = parent.interaction_mode  # Start in 'rectangle' mode
        self.rect = None
        self.lines = []
        self.shaded_area = None
        self._press_x = None
        self.clip_start = True # State variable that identifies if I am clipping the start of the line or not
        self.connect_regular_events()
        # self.cursor = DataCursor(self) # initialize the cursor

        self.x_min = None
        self.x_max = None

    def connect_clipping_event(self):
        self.cid_click = self.canvas.mpl_connect('button_press_event', self.on_click)
        self.cid_scroll = self.canvas.mpl_connect('scroll_event', self.on_scroll)
        self.cid_motion = self.canvas.mpl_connect("motion_notify_event", self.on_clip_motion)
    
    def disconnect_clipping_event(self):
        self.canvas.mpl_disconnect(self.cid_click)
        self.canvas.mpl_disconnect(self.cid_scroll)
        # reset the cursor mode
        self.canvas.mpl_disconnect(self.cid_motion)

    def toggle_mode(self):
        if self.parent.interaction_mode.get() == VIEW_MODE:
            self.parent.interaction_mode.set(CLIPPING_MODE)
            self.disconnect_regular_events()
            self.connect_clipping_event()
        else:
            self.parent.interaction_mode.set(VIEW_MODE)
            self.disconnect_regular_events
            self.connect_regular_events()

    def connect_regular_events(self):
        self.cid_press = self.canvas.mpl_connect('button_press_event', self.on_press)
        self.cid_motion = self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.cid_release = self.canvas.mpl_connect('button_release_event', self.on_release)
        self.cid_scroll = self.canvas.mpl_connect('scroll_event', self.on_scroll)

    def disconnect_regular_events(self):
        self.canvas.mpl_disconnect(self.cid_press)
        self.canvas.mpl_disconnect(self.cid_motion)
        self.canvas.mpl_disconnect(self.cid_release)
        self.canvas.mpl_disconnect(self.cid_scroll)

    def on_click(self, event):
        if self.parent.interaction_mode.get() == CLIPPING_MODE and event.inaxes == self.ax:
            # Add a vertical line at the x-coordinate of the mouse click
            if self.clip_start:
                line = self.ax.axvline(x=event.xdata, color='green', lw=2, linestyle="--")
                self.clip_start_x = event.xdata
                self.lines.insert(0, line)
            else:
                line = self.ax.axvline(x=event.xdata, color='blue', lw=2, linestyle="--")
                self.clip_start_end = event.xdata
                self.lines.append(line)

            # If we have two lines, draw the shaded area
            if len(self.lines) == 2:
                self.shade_area_between_lines()
            elif len(self.lines) > 2:
                # We replace the lines based on the mode
                self.lines.pop(1).remove() # we replace the second line

                self.shade_area_between_lines()
            
            self.clip_start = not self.clip_start # we toggle the mode

            self.canvas.draw()

    def shade_area_between_lines(self):
        if self.shaded_area:
            self.shaded_area.remove()
        x1 = self.lines[0].get_xdata()[0]
        x2 = self.lines[1].get_xdata()[0]
        self.x_min = min(x1, x2)
        self.x_max = max(x1, x2)
        y_min, y_max = self.ax.get_ylim()
        self.shaded_area = Rectangle((self.x_min, y_min), self.x_max - self.x_min, y_max - y_min, color='gray', alpha=0.5)
        self.ax.add_patch(self.shaded_area)

    def on_press(self, event):
        if event.inaxes != self.ax: return
        self._press_x = event.xdata
        self._press_xlim = self.ax.get_xlim()

    def on_motion(self, event):
        if event.inaxes != self.ax: return
        if self._press_x is None: return
        dx = event.xdata - self._press_x
        xlim = self._press_xlim
        self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
        self.ax.figure.canvas.draw_idle()
    
    def on_clip_motion(self, event):
        if self.parent.interaction_mode.get() == CLIPPING_MODE and event.inaxes == self.ax:
            # Set the cursor to a pair of scissors when in 'line' mode and inside the axes
            self.canvas_widget.config(cursor="cross")  # 'cross' is a placeholder for a scissor-like cursor
        else:
            # Set the cursor back to the default arrow
            self.canvas_widget.config(cursor="arrow")

    def on_release(self, event):
        self._press_x = None
        self._press_xlim = None
        self.autoscale_y_axis()

    def autoscale_y_axis(self):
        self.ax.relim()
        self.ax.autoscale_view(scalex=False, scaley=True)
        self.canvas.draw_idle()
    
    def on_scroll(self, event):
        if event.inaxes != self.ax: return
        factor = 0.1  # Determines the scroll speed
        xlim = self.ax.get_xlim()
        dx = factor * (xlim[1] - xlim[0])
        if event.button == 'up':  # Scroll up, move view to the right
            self.ax.set_xlim(xlim[0] - dx, xlim[1] - dx)
        elif event.button == 'down':  # Scroll down, move view to the left
            self.ax.set_xlim(xlim[0] + dx, xlim[1] + dx)
        self.ax.figure.canvas.draw_idle()

class GraphHandler:
    # handles the asynchronous recording of incoming data from multiple devices, parent is DisplayApp
    def __init__(self, parent, data_handler):
        self.parent = parent
        self.data_handler = data_handler
    
    def update_plot_options(self):
        for tab in self.parent.display_screen.tabs()[:2]:
            selected_frame = self.parent.display_screen.nametowidget(tab)
            if hasattr(selected_frame,"graph"):
                selected_frame.update_options()
    
    def on_tab_switch(self, event):
        # we trigger this function when we navigate to the save tab
        # we want to plot the last graph each time we switch the tab
        selected_tab = event.widget.select()
        selected_frame = self.parent.display_screen.nametowidget(selected_tab)
        if hasattr(selected_frame, 'graph'):
            selected_frame.graph.update_plot()