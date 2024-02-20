import tkinter as tk
from tkinter import Toplevel, messagebox
import tkinter.ttk as ttk
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from constants import TAGS, BUCKET
import json
from credentials import access_key, secret_key
import boto3
from botocore.exceptions import BotoCoreError, ClientError
import os

class MultiTabFrame(ttk.Notebook):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid()
    
    def add_tab(self, frame, name):
        # we add a tab into the display
        # frame.master = self
        self.add(frame, text=name)

class ScrollableDisplay(tk.Frame):
    # this is pretty much the same as the DeviceCheckbox but populated with a different value
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grid()
        self.canvas = tk.Canvas(self,borderwidth=0)
        self.frame =tk.Frame(self.canvas)
        self.frame = tk.Frame(self.canvas)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set) #associate scrollbar with canvas
        self.scrollbar.pack(side="right",fill="y")
        self.canvas.pack(side="left",fill="both",expand=True)
        self.canvas.create_window((0,0),window=self.frame,anchor="nw")
        self.data = [] # Consider including headers here later
    
    def update(self, data:list):
        # clear frame
        self.data = data #where data is a list of information to be represented. Note that the format of data is dependent on the required input format of the defined populate method 
        for widget in self.frame.winfo_children():
            widget.destroy()
        self.populate()

    # Function to handle mouse scroll on Windows
    def on_mousewheel(self,event, canvas):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    # Function to handle mouse scroll on MacOS or Linux
    def on_mousewheel_linux(self,event, canvas):
        self.canvas.yview_scroll(int(-1*event.delta), "units")

    # Function to update the scrollregion of the canvas
    def on_frame_configure(self):
        '''Reset the scroll region to encompass the inner frame'''
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        # Bind the scrollwheel event to the canvas
        if self.parent.tk.call('tk', 'windowingsystem') == 'win32':
            # For Windows
            self.canvas.bind_all("<MouseWheel>", lambda event: self.on_mousewheel(event, self.canvas))
        else:
            # For MacOS and Linux
            self.canvas.bind_all("<MouseWheel>", lambda event: self.on_mousewheel_linux(event, self.canvas))

    # Function to populate the frame: Note that the ScrollableDisplay is not meant to work out of the box. Please create a subclass that modifies the populate method
    def populate(self):
        pass

class LiveRowDisplay(ScrollableDisplay):
    # this is pretty much the same as the DeviceCheckbox but populated with a different value
    def __init__(self, parent):
        super().__init__(parent) # this rewrites the master as the parent rather than inheriting the parent's master

    # Function to populate the frame with checkboxes
    def populate(self):
        self.checkboxes = []
        for row, device_status in enumerate(self.data):
            row_frame = tk.Frame(self)
            name = tk.Label(row_frame, text=device_status["device_name"])
            name.grid(row=0, column=0)
            connection_status = tk.Label(row_frame, text=device_status["connection_status"])
            connection_status.grid(row=0,column=1)
            log_msg = tk.Label(row_frame,text=device_status["logged_message"])
            log_msg.grid(row=0, column=2)
            row_frame.grid(row=row, sticky="w")
        
class DeviceCheckbox(ScrollableDisplay):
    def __init__(self, parent):
        super().__init__(parent)

    # Function to populate the frame with checkboxes
    def populate(self):
        self.checkboxes = []
        for row, label in enumerate(self.data):
            checkbox = tk.BooleanVar()
            self.checkboxes.append((checkbox,label))
            tk.Checkbutton(self.frame, text=label, variable=checkbox, command=self.enable_connection).grid(row=row, sticky="w")
    
    def enable_connection(self):
        # set button to active
        self.parent.parent.connect_button.config(state = "active")

class UploadPage(tk.Frame):
    def __init__(self, parent, data_handler):
        super().__init__()
        self.grid(sticky="")
        self.parent = parent
        self.data_handler = data_handler
        self.session_cache = self.data_handler.session_config
        self.save_dir = self.data_handler.save_dir
        self.session_list = ttk.Treeview(self, selectmode=tk.EXTENDED)
        self.session_list["columns"] = ["one", "two"]
        self.refresh_button = ttk.Button(self, text="Refresh", command=self.refresh)
        self.refresh_button.grid(row=0, column=1, sticky="e")

        self.session_list.grid(row=1, column=0, columnspan=3)
        self.session_list.column("#0", width=0, stretch=tk.NO)
        self.session_list.column("one", width=250, minwidth=150, stretch=tk.NO)
        self.session_list.column("two", width=150, minwidth=150, stretch=tk.NO)

        self.session_list.heading("#0", text="", anchor=tk.W)
        self.session_list.heading("one", text="File Name", anchor=tk.W)
        self.session_list.heading("two", text="Status", anchor=tk.W)

        for file in self.get_file_status():
            self.session_list.insert("", tk.END, values=file)


        self.comment_button = ttk.Button(self, text="Add Note", command=self.add_comment)
        self.comment_button.grid(row=2, column=0)
        self.upload_files = ttk.Button(self, text="Upload Files", command=self.upload)
        self.upload_files.grid(row=2, column=1)
        self.peek_button = ttk.Button(self, text="Show Graph", command=self.show_graph)
        self.peek_button.grid(row=3, column=0)
        self.delete_button = ttk.Button(self, text="Delete Local", command=self.delete_files)
        self.delete_button.grid(row=3, column=1)

        self.comment_field = tk.Frame(self) # this frame store the comment form
        self.comment_field.grid(row=4, column=0, sticky="", columnspan=3)

    # Function to delete selected items
    def delete_files(self):
        filenames = self.get_selected_filenames()  # Get selected items
        for filename in filenames:
            # Ask for confirmation
            if messagebox.askyesno("Confirmation", "Do you really want to delete?"):
                # Retrieve the filename from the tree item
                row_id = self.get_id_by_name(filename)
                # Remove the item from the treeview
                self.session_list.delete(row_id)
                del self.session_cache[filename]
                # Construct the file path
                file_path = os.path.join(self.save_dir, filename)
                # Remove the file from the local directory
                try:
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                except OSError as e:
                    print(f"Error deleting {file_path}: {e}")
        self.save_state()

    def show_graph(self):
        # creates a pop-up window that displays graph
        # reads in csv data and plots it
        # Read data from CSV
        selected_file = self.get_selected_filenames()[0]

        df = pd.read_csv(os.path.join(self.save_dir, selected_file))  # Make sure to replace 'your_data.csv' with your actual CSV file path
        
        # Create a new popup window
        popup = Toplevel()
        popup.title(selected_file.split(".")[0])
        
        # Create the figure for the plot
        fig, ax = plt.subplots()
        
        # Plot the data (adjust according to your data structure)
        ax.plot(df.iloc[:, 0], df.iloc[:, 1])
        ax.set_title(f'Graph of {selected_file.split(".")[0]}')
        ax.set_xlabel('Time (ms)') 
        ax.set_ylabel('Resistance')
        
        # Create a canvas for the figure
        canvas = FigureCanvasTkAgg(fig, master=popup)
        canvas_widget = canvas.get_tk_widget()
        canvas_widget.pack()
        
        canvas.draw()
    
        # Create a Close button in the popup window
        close_button = tk.Button(popup, text="Close", command=popup.destroy)
        close_button.pack()

    def refresh(self):
        for item in self.session_list.get_children():
            self.session_list.delete(item)
        for file in self.get_file_status():
            self.session_list.insert("", tk.END, values=file)
    
    def get_file_status(self):
        # we iterate through session files
        status_list = []
        for filename in self.data_handler.session_files:
            if self.session_cache.get(filename):
                status_list.append((filename,self.session_cache[filename]["status"]))
            else:
                new_cache = {
                    "name": filename,
                    "tags": None,
                    "devices": None,
                    "notes": None,
                    "status": "No Notes"
                }
                self.session_cache[filename] = new_cache
                status_list.append((filename, "No Notes"))
        # Write over existing values
        with open(self.data_handler.config_fp, "w") as f:
            json.dump(self.session_cache,f)
        return status_list

    def get_selected_filenames(self):
        # return list of selected files --> mainly for uploading purposes
        selected_items = self.session_list.selection()
        filenames = [self.session_list.item(item_id)["values"][0] for item_id in selected_items]
        return filenames

    def get_id_by_name(self, name):
        # get TreeView id by name
        for child_id in self.session_list.get_children():
            if self.session_list.item(child_id)["values"][0] == name:
                return child_id
        return None

    def add_comment(self):
        # get selected file
        filenames = self.get_selected_filenames()
        filename = filenames[0]
        # delete any existing comment entry
        for widget in self.comment_field.winfo_children():
            widget.destroy()
        
        row_id = self.get_id_by_name(filename)
        if row_id:
            # we generate the comment form
            CommentForm(self, filename, row_id)
    
    def save_state(self):
        with open(self.data_handler.config_fp, "w") as f:
            json.dump(self.session_cache,f)
        print("successfully saved")

    def upload(self):
        # upload selected files to remote db
        filenames = self.get_selected_filenames()
        for filename in filenames:
            # we want to attempt to upload
            tags = self.session_cache[filename]["tags"]
            upload_files(BUCKET,os.path.join(self.save_dir,filename),filename, tags=tags,access_key=access_key,secret_key=secret_key)
            print(f"uploaded {filename}")
            # update the upload status
            row_id = self.get_id_by_name(filename)
            self.session_list.item(row_id, values=(filename, "File Uploaded"))
            self.session_cache[filename]["status"] = "File Uploaded"
            self.save_state()

class CommentForm(tk.Frame):
    def __init__(self, parent:UploadPage, filename, row_id):
        super().__init__()
        self.parent = parent
        self.filename = filename
        self.row_id = row_id
        self.label = tk.Label(self.parent.comment_field, text=f"{self.filename} Notes")
        self.label.grid(row=0, column=0, columnspan=3, sticky="")
        self.add_button = ttk.Button(self.parent.comment_field,text="Save", command=self.add_note)
        self.add_button.grid(row=1, column=2)
        self.tag_dd = ttk.Combobox(self.parent.comment_field, values=TAGS)
        self.tag_dd.grid(row=1, column=0)
        self.add_tag_button = ttk.Button(self.parent.comment_field, text="Add Tag", command=self.add_tag)
        self.add_tag_button.grid(row=1, column=1)
        self.tags = [] # stores the selected tags 
        self.tag_buttons = []
        self.tag_display = tk.Frame(self.parent.comment_field) # frame to store tags
        self.tag_display.grid(row=2, column=0, columnspan=4, sticky="NSEW")
        self.text_entry = tk.Text(self.parent.comment_field, height=10, width=64)
        self.text_entry.grid(row=3, column=0, columnspan=3)
        self.load_last_saved()
    
    def load_last_saved(self):
        if self.parent.session_cache.get(self.filename):
            if self.parent.session_cache[self.filename]["status"] == "Notes Added":
                # this means that we have a valid previous session
                # we load in the new values 
                previous_note = self.parent.session_cache[self.filename]
                self.tags = previous_note["tags"]
                for value in self.tags:
                    self.create_button(self.tag_display, value)
                self.arrange_buttons()
                self.text_entry.insert("1.0",previous_note["notes"])

        # do nothing otherwise
    
    def create_button(self,frame,value):
        def destroy_button():
            self.tags.remove(value)
            self.tag_buttons.remove(button)
            button.destroy()
            self.arrange_buttons()

        button = tk.Button(frame, text=value, command=destroy_button)
        self.tag_buttons.append(button)

    def arrange_buttons(self):
        for id, button in enumerate(self.tag_buttons):
            button.grid(row = id//4, column = id%4)

    def add_tag(self):
        # get value of combobox
        value = self.tag_dd.get()
        if value not in self.tags:
            self.tags.append(value)
        
            # Create and pack the button within its frame
            self.create_button(self.tag_display, value)
            self.arrange_buttons()

    def add_note(self):
        # adds the comments to the session notes
        notes = self.parent.session_cache[self.filename]
        notes["tags"] = self.tags
        notes["notes"] = self.text_entry.get("1.0", tk.END)
        notes["status"] = "Notes Added"
       
        self.parent.session_cache[self.filename] = notes
        self.parent.session_list.item(self.row_id, values=(self.filename, "Notes Added"))
        # we save the json with the latest information
        self.parent.save_state()


def frequency_display_format(element):
    return str(element) + "Hz"

def invert_frequency_format(element):
    elem_int = element.replace("Hz","")
    return int(elem_int)

def freq_to_ms(frequency:int):
    return int(1000/frequency)
        
def disable_tk_frame(frame):
    """ Recursively disable all widgets in a Tkinter frame """
    for widget in frame.winfo_children():
        if isinstance(widget, tk.Entry):
            widget.config(state='disabled')
        elif isinstance(widget, tk.Button):
            widget.config(state='disabled')
        elif isinstance(widget, ttk.Combobox):
            widget.config(state='disabled')
        elif isinstance(widget, tk.Frame):
            disable_tk_frame(widget)
        elif isinstance(widget, ttk.Notebook):
            for tab in widget.tabs():
                frame = widget.nametowidget(tab)
                disable_tk_frame(frame)

def enable_tk_frame(frame):
    """ Recursively disable all widgets in a Tkinter frame """
    for widget in frame.winfo_children():
        if isinstance(widget, tk.Entry):
            widget.config(state='normal')
        elif isinstance(widget, tk.Button):
            widget.config(state='normal')
        elif isinstance(widget, ttk.Combobox):
            widget.config(state='normal')
        elif isinstance(widget, tk.Frame):
            enable_tk_frame(widget)
        elif isinstance(widget, ttk.Notebook):
            for tab in widget.tabs():
                frame = widget.nametowidget(tab)
                enable_tk_frame(frame)

def valid_cab(calibration_values):
    # check valid calibration types.
    if all([isinstance(val[1],float) for val in calibration_values.values()]):
        return True
    return False

def upload_files(bucket_name, file_path, object_name, tags:list, access_key, secret_key):
    error = None

    s3 = boto3.client(
        "s3",
        aws_access_key_id = access_key,
        aws_secret_access_key = secret_key
    )

    # Upload the file
    try:
        s3.upload_file(file_path, bucket_name, object_name)

        # attempt to fetch file for upload confirmation
        response = s3.head_object(Bucket=bucket_name, Key=object_name)
        print(f'file upload {response["ResponseMetadata"]["HTTPStatusCode"]}')

    except (BotoCoreError, ClientError) as error:
        # Handle AWS errors here
        print(f"Upload failed: {error}")

    if not error:
        try:
            tag_set = []
            for tag in tags:
                tag_set.append({
                    "Key":tag,
                    "Value":"True"
                })

            response = s3.put_object_tagging(
            Bucket = bucket_name,
            Key = object_name,
            Tagging = {
                'TagSet':tag_set
                }
            )
            print(f'file tag {response["ResponseMetadata"]["HTTPStatusCode"]}')
        except (BotoCoreError, ClientError) as tag_error:
            # Handle potential errors
            print(f'Tagging failed: {tag_error}')