#!/usr/bin/env python3
"""
Arduino Syringe-Pump Manager - Pump Manager Module
==================================================

This module contains the PumpManager class which provides the main interface
for managing multiple Arduino syringe pumps.

Features:
- Multi-pump management interface
- Pump window creation and management
- System-wide logging
- Pump status tracking

Author: Beidaghi Lab
Version: 2.0
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog
import uuid
from pump_window import PumpWindow

class PumpManager:
    """
    Main pump manager that provides the interface for managing multiple
    Arduino syringe pumps.
    """
    
    def __init__(self, root):
        """
        Initialize the pump manager.
        
        Args:
            root: The main tkinter root window
        """
        self.root = root
        self.root.title("Arduino Pump Manager")
        self.root.geometry("600x500")
        
        # Store pump windows
        self.pump_windows = {}  # pump_id: PumpWindow
        
        # Create manager interface
        self.create_manager_interface()
        
        # Handle main window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_manager_interface(self):
        """Create the main manager interface"""
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Arduino Syringe-Pump Manager", 
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Description
        desc_text = """

Each pump operates in its own independent window with:

• Individual COM port connections
• Separate dispense controls and tracking  
• Independent communication logs

Click 'Add New Pump' to create a new pump control window."""
        
        desc_label = ttk.Label(main_frame, text=desc_text, justify="left", 
                              font=("Arial", 11))
        desc_label.pack(pady=(0, 30))
        
        # Add pump button
        add_pump_frame = ttk.Frame(main_frame)
        add_pump_frame.pack(pady=20)
        
        self.add_pump_btn = ttk.Button(add_pump_frame, text="+ Add New Pump", 
                                      command=self.add_pump, 
                                      style="Accent.TButton")
        self.add_pump_btn.pack(side="left", padx=(0,10))

        self.dispense_all_btn = ttk.Button(add_pump_frame, text = "Dispense All",
                                           command=self.dispense_all)
        
        self.dispense_all_btn.pack(side="left", padx=5)

        self.stop_all_btn = ttk.Button(add_pump_frame, text="Stop All",
                               command=self.stop_all)
        
        self.stop_all_btn.pack(side="left", padx=5)

        
        # Active pumps list
        pumps_frame = ttk.LabelFrame(main_frame, text="Active Pumps", padding=15)
        pumps_frame.pack(fill="both", expand=True, pady=20)
        
        # Treeview for pump list
        columns = ("Name", "Status", "Connection", "Activity")
        self.pump_tree = ttk.Treeview(pumps_frame, columns=columns, show="headings", height=8)
        
        # Define column headings and widths
        self.pump_tree.heading("Name", text="Pump Name")
        self.pump_tree.heading("Status", text="Status")
        self.pump_tree.heading("Connection", text="COM Port")
        self.pump_tree.heading("Activity", text="Current Activity")
        
        self.pump_tree.column("Name", width=150)
        self.pump_tree.column("Status", width=100)
        self.pump_tree.column("Connection", width=100)
        self.pump_tree.column("Activity", width=150)
        
        # Scrollbar for treeview
        tree_scroll = ttk.Scrollbar(pumps_frame, orient="vertical", command=self.pump_tree.yview)
        self.pump_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.pump_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        
        # Pump control buttons
        pump_control_frame = ttk.Frame(main_frame)
        pump_control_frame.pack(fill="x", pady=10)
        
        self.focus_btn = ttk.Button(pump_control_frame, text="Focus Window", 
                                   command=self.focus_pump_window, state="disabled")
        self.focus_btn.pack(side="left", padx=(0, 10))
        
        self.close_pump_btn = ttk.Button(pump_control_frame, text="Close Pump", 
                                        command=self.close_selected_pump, state="disabled")
        self.close_pump_btn.pack(side="left", padx=5)
        
        # Bind treeview selection
        self.pump_tree.bind("<<TreeviewSelect>>", self.on_pump_select)
        self.pump_tree.bind("<Double-1>", self.focus_pump_window)
        
        # Global log
        log_frame = ttk.LabelFrame(main_frame, text="System Log", padding=10)
        log_frame.pack(fill="x", pady=10)
        
        self.system_log = scrolledtext.ScrolledText(log_frame, height=6)
        self.system_log.pack(fill="x")
        
        # Initial log message
        self.log_system_message("Pump Manager started. Click 'Add New Pump' to begin.")
    
    def add_pump(self):
        """Add a new pump window"""
        pump_name = simpledialog.askstring("Add Pump", "Enter pump name:", 
                                          initialvalue=f"Pump {len(self.pump_windows) + 1}")
        if not pump_name:
            return
        
        # Create unique pump ID
        pump_id = str(uuid.uuid4())
        
        # Create pump window
        pump_window = PumpWindow(pump_id, pump_name, self.pump_callback)
        self.pump_windows[pump_id] = pump_window
        
        # Add to treeview
        self.pump_tree.insert("", "end", iid=pump_id, values=(pump_name, "Disconnected", "None", "Ready"))
        
        # Enable buttons if this is first pump
        if len(self.pump_windows) == 1:
            self.focus_btn.config(state="normal")
            self.close_pump_btn.config(state="normal")
        
        self.log_system_message(f"Added new pump: {pump_name}")
    
    def pump_callback(self, event_type, pump_id, data):
        """
        Handle callbacks from pump windows.
        
        Args:
            event_type: Type of event (connect, disconnect, rename, etc.)
            pump_id: Unique identifier for the pump
            data: Additional data for the event
        """
        if pump_id not in self.pump_windows:
            return
        
        pump = self.pump_windows[pump_id]
        
        # Update treeview based on event
        if event_type == 'connect':
            self.pump_tree.set(pump_id, "Status", "Connected")
            self.pump_tree.set(pump_id, "Connection", data['port'])
            self.log_system_message(f"{pump.name}: Connected to {data['port']}")
        
        elif event_type == 'disconnect':
            self.pump_tree.set(pump_id, "Status", "Disconnected")
            self.pump_tree.set(pump_id, "Connection", "None")
            self.pump_tree.set(pump_id, "Activity", "Ready")
            self.log_system_message(f"{pump.name}: Disconnected")
        
        elif event_type == 'rename':
            self.pump_tree.set(pump_id, "Name", data['new_name'])
            self.log_system_message(f"Pump renamed: {data['old_name']} → {data['new_name']}")
        
        elif event_type == 'dispense_start':
            self.pump_tree.set(pump_id, "Activity", f"Dispensing {data['volume']}mL")
            self.log_system_message(f"{pump.name}: Started dispensing {data['volume']}mL at {data['rate']}mL/min")
        
        elif event_type == 'dispense_complete':
            self.pump_tree.set(pump_id, "Activity", "Complete")
            self.log_system_message(f"{pump.name}: Dispensing completed")
        
        elif event_type == 'dispense_cancel':
            self.pump_tree.set(pump_id, "Activity", "Cancelled")
            self.log_system_message(f"{pump.name}: Dispensing cancelled")
        
        elif event_type == 'close':
            # Remove from treeview and dictionary
            self.pump_tree.delete(pump_id)
            del self.pump_windows[pump_id]
            self.log_system_message(f"{pump.name}: Window closed")
            
            # Disable buttons if no pumps left
            if not self.pump_windows:
                self.focus_btn.config(state="disabled")
                self.close_pump_btn.config(state="disabled")
    
    def on_pump_select(self, event):
        """Handle pump selection in treeview"""
        pass  # Buttons are always enabled when pumps exist
    
    def focus_pump_window(self, event=None):
        """Bring selected pump window to front"""
        selection = self.pump_tree.selection()
        if not selection:
            return
        
        pump_id = selection[0]
        if pump_id in self.pump_windows:
            pump_window = self.pump_windows[pump_id]
            pump_window.window.lift()
            pump_window.window.focus_force()
    
    def close_selected_pump(self):
        """Close selected pump window"""
        selection = self.pump_tree.selection()
        if not selection:
            return
        
        pump_id = selection[0]
        if pump_id in self.pump_windows:
            pump_window = self.pump_windows[pump_id]
            pump_window.on_closing()
    
    def log_system_message(self, message):
        """
        Add a message to the system log.
        
        Args:
            message: The message to log
        """
        import time
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.system_log.insert(tk.END, log_entry)
        self.system_log.see(tk.END)


    def dispense_all(self):
        """Trigger start_dispense on all connected pumps that are not currently dispensing."""
        for pump in self.pump_windows.values():
            if pump.is_connected and not pump.is_dispensing:
                pump.start_dispense()

    def stop_all(self):
        """Trigger cancel_dispense on all currently dispensing pumps."""
        for pump in self.pump_windows.values():
            if pump.is_connected and pump.is_dispensing:
                pump.cancel_dispense()
    
        
    
    def on_closing(self):
        """Handle main window closing"""
        # Close all pump windows
        for pump_id in list(self.pump_windows.keys()):
            pump_window = self.pump_windows[pump_id]
            if pump_window.is_connected:
                pump_window.disconnect_from_arduino()
            pump_window.window.destroy()
        
        # Close main window
        self.root.destroy() 