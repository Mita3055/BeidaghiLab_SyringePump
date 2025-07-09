#!/usr/bin/env python3
"""
Arduino Syringe-Pump Manager - Pump Window Module
=================================================

This module contains the PumpWindow class which provides the interface
for controlling individual Arduino syringe pumps.

Features:
- Individual pump control interface
- Real-time progress tracking
- Serial communication with Arduino
- Enhanced status monitoring

Author: Beidaghi Lab
Version: 2.0
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import serial
import serial.tools.list_ports
import threading
import time
import queue

class PumpWindow:
    """
    Individual pump control window that manages communication with
    a single Arduino syringe pump.
    """
    
    def __init__(self, pump_id, name, manager_callback):
        """
        Initialize the pump window.
        
        Args:
            pump_id: Unique identifier for this pump
            name: Display name for the pump
            manager_callback: Callback function to notify the manager
        """
        self.pump_id = pump_id
        self.name = name
        self.manager_callback = manager_callback
        
        # Connection state
        self.serial_connection = None
        self.is_connected = False
        self.is_dispensing = False
        self.port = ""
        
        # Message queue for this pump
        self.message_queue = queue.Queue()
        
        # Real-time data storage
        self.current_progress = 0.0
        self.dispensed_volume = 0.0
        self.remaining_volume = 0.0
        self.elapsed_time = 0.0
        self.estimated_remaining_time = 0.0
        self.current_speed = 0.0
        
        # Create pump window
        self.create_window()
        
        # Start message processing for this pump
        self.process_messages()
        
        # Refresh COM ports on startup
        self.refresh_ports()
    
    def create_window(self):
        """Create the pump control window"""
        self.window = tk.Toplevel()
        self.window.title(f"Pump Control - {self.name}")
        self.window.geometry("500x600")
        self.window.resizable(True, True)
        
        # Handle window closing
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Main frame
        main_frame = ttk.Frame(self.window, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Header with pump name
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 15))
        
        # Editable pump name
        name_frame = ttk.LabelFrame(header_frame, text="Pump Name", padding=10)
        name_frame.pack(fill="x")
        
        self.name_var = tk.StringVar(value=self.name)
        self.name_entry = ttk.Entry(name_frame, textvariable=self.name_var, 
                                   font=("Arial", 12, "bold"))
        self.name_entry.pack(fill="x")
        self.name_entry.bind('<Return>', self.rename_pump)
        self.name_entry.bind('<FocusOut>', self.rename_pump)
        
        # Connection Frame
        conn_frame = ttk.LabelFrame(main_frame, text="Connection", padding=10)
        conn_frame.pack(fill="x", pady=5)
        
        # COM Port selection
        port_frame = ttk.Frame(conn_frame)
        port_frame.pack(fill="x", pady=5)
        
        ttk.Label(port_frame, text="COM Port:").pack(side="left")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(port_frame, textvariable=self.port_var, 
                                      state="readonly", width=20)
        self.port_combo.pack(side="left", padx=(10, 5))
        
        self.refresh_btn = ttk.Button(port_frame, text="Refresh", command=self.refresh_ports)
        self.refresh_btn.pack(side="left", padx=5)
        
        self.connect_btn = ttk.Button(port_frame, text="Connect", command=self.toggle_connection)
        self.connect_btn.pack(side="left", padx=5)
        
        # Connection status
        self.status_var = tk.StringVar(value="Status: Disconnected")
        self.status_label = ttk.Label(conn_frame, textvariable=self.status_var, foreground="red")
        self.status_label.pack(anchor="w", pady=5)
        
        # Control Frame
        control_frame = ttk.LabelFrame(main_frame, text="Dispenser Control", padding=10)
        control_frame.pack(fill="x", pady=5)
        
        # Volume and Rate inputs
        input_frame = ttk.Frame(control_frame)
        input_frame.pack(fill="x", pady=5)
        
        ttk.Label(input_frame, text="Volume (mL):").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.volume_var = tk.StringVar(value="5.0")
        volume_entry = ttk.Entry(input_frame, textvariable=self.volume_var, width=12)
        volume_entry.grid(row=0, column=1, padx=5)
        
        ttk.Label(input_frame, text="Rate (mL/min):").grid(row=0, column=2, sticky="w", padx=(20, 5))
        self.rate_var = tk.StringVar(value="10.0")
        rate_entry = ttk.Entry(input_frame, textvariable=self.rate_var, width=12)
        rate_entry.grid(row=0, column=3, padx=5)
        
        # Control buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill="x", pady=10)
        
        self.dispense_btn = ttk.Button(button_frame, text="Start Dispense", 
                                      command=self.start_dispense, state="disabled")
        self.dispense_btn.pack(side="left", padx=(0, 10))
        
        self.cancel_btn = ttk.Button(button_frame, text="Cancel", 
                                    command=self.cancel_dispense, state="disabled")
        self.cancel_btn.pack(side="left", padx=5)
        
        self.status_btn = ttk.Button(button_frame, text="Get Status", 
                                    command=self.get_status, state="disabled")
        self.status_btn.pack(side="left", padx=5)
        
        # Progress Frame
        progress_frame = ttk.LabelFrame(main_frame, text="Real-Time Progress", padding=10)
        progress_frame.pack(fill="x", pady=5)
        
        # Progress bar and percentage
        progress_header_frame = ttk.Frame(progress_frame)
        progress_header_frame.pack(fill="x", pady=5)
        
        self.progress_var = tk.StringVar(value="Ready")
        progress_label = ttk.Label(progress_header_frame, textvariable=self.progress_var, 
                                  font=("Arial", 10, "bold"))
        progress_label.pack(anchor="w")
        
        self.progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.progress_bar.pack(fill="x", pady=5)
        
        # Detailed progress information
        details_frame = ttk.Frame(progress_frame)
        details_frame.pack(fill="x", pady=5)
        
        # Volume information
        volume_frame = ttk.LabelFrame(details_frame, text="Volume", padding=5)
        volume_frame.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.dispensed_var = tk.StringVar(value="Dispensed: 0.00 mL")
        self.remaining_var = tk.StringVar(value="Remaining: 0.00 mL")
        ttk.Label(volume_frame, textvariable=self.dispensed_var).pack(anchor="w")
        ttk.Label(volume_frame, textvariable=self.remaining_var).pack(anchor="w")
        
        # Time information
        time_frame = ttk.LabelFrame(details_frame, text="Time", padding=5)
        time_frame.pack(side="left", fill="x", expand=True, padx=5)
        
        self.elapsed_var = tk.StringVar(value="Elapsed: 0.0 min")
        self.remaining_time_var = tk.StringVar(value="ETA: 0.0 min")
        ttk.Label(time_frame, textvariable=self.elapsed_var).pack(anchor="w")
        ttk.Label(time_frame, textvariable=self.remaining_time_var).pack(anchor="w")
        
        # Speed information
        speed_frame = ttk.LabelFrame(details_frame, text="Speed", padding=5)
        speed_frame.pack(side="left", fill="x", expand=True, padx=(5, 0))
        
        self.speed_var = tk.StringVar(value="Current: 0.0 mL/min")
        ttk.Label(speed_frame, textvariable=self.speed_var).pack(anchor="w")
        
        # Log Frame
        log_frame = ttk.LabelFrame(main_frame, text="Communication Log", padding=10)
        log_frame.pack(fill="both", expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, width=60)
        self.log_text.pack(fill="both", expand=True)
        
        # Log control buttons
        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.pack(fill="x", pady=5)
        
        clear_btn = ttk.Button(log_btn_frame, text="Clear Log", command=self.clear_log)
        clear_btn.pack(side="right")
        
        # Bottom frame with close button
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill="x", pady=10)
        
        close_btn = ttk.Button(bottom_frame, text="Close Pump Window", command=self.on_closing)
        close_btn.pack(side="right")
        
        # Update window title with connection status
        self.update_window_title()
    
    def update_window_title(self):
        """Update window title with current status"""
        status = "Connected" if self.is_connected else "Disconnected"
        dispensing = " - Dispensing" if self.is_dispensing else ""
        self.window.title(f"Pump Control - {self.name} ({status}){dispensing}")
    
    def rename_pump(self, event=None):
        """Rename the pump"""
        new_name = self.name_var.get().strip()
        if new_name and new_name != self.name:
            old_name = self.name
            self.name = new_name
            self.update_window_title()
            self.log_message(f"Pump renamed from '{old_name}' to '{new_name}'")
            # Notify manager of name change
            self.manager_callback('rename', self.pump_id, {'old_name': old_name, 'new_name': new_name})
    
    def refresh_ports(self):
        """Refresh available COM ports"""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports and not self.port_var.get():
            self.port_combo.set(ports[0])
    
    def toggle_connection(self):
        """Toggle connection to Arduino"""
        if not self.is_connected:
            self.connect_to_arduino()
        else:
            self.disconnect_from_arduino()
    """
    def connect_to_arduino(self):
    # FAKE/SIMULATED connection for UI testing (no hardware required)
        self.is_connected = True
        self.port = "FAKE_PORT"
        self.connect_btn.config(text="Disconnect")
        self.status_var.set(f"Status: Connected to FAKE_PORT")
        self.status_label.config(foreground="green")
        self.dispense_btn.config(state="normal")
        self.status_btn.config(state="normal")
        self.update_window_title()
        self.log_message(f"Connected to FAKE_PORT (SIMULATED)")
        self.manager_callback('connect', self.pump_id, {'port': "FAKE_PORT"})

    """
    def connect_to_arduino(self):
        #Connect to Arduino
        port = self.port_var.get()
        if not port:
            messagebox.showerror("Error", "Please select a COM port")
            return
        
        try:
            self.serial_connection = serial.Serial(port, 115200, timeout=1)
            time.sleep(2)  # Wait for Arduino to initialize
            
            self.is_connected = True
            self.port = port
            self.connect_btn.config(text="Disconnect")
            self.status_var.set(f"Status: Connected to {port}")
            self.status_label.config(foreground="green")
            
            # Enable control buttons
            self.dispense_btn.config(state="normal")
            self.status_btn.config(state="normal")
            
            # Update window title
            self.update_window_title()
            
            # Start reading thread
            self.reading_thread = threading.Thread(target=self.read_serial, daemon=True)
            self.reading_thread.start()
            
            self.log_message(f"Connected to {port}")
            self.manager_callback('connect', self.pump_id, {'port': port})
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {str(e)}")
            self.log_message(f"Connection failed: {str(e)}")
    

    def disconnect_from_arduino(self):
        """Disconnect from Arduino"""
        if self.serial_connection:
            self.serial_connection.close()
            self.serial_connection = None
        
        self.is_connected = False
        self.is_dispensing = False
        self.connect_btn.config(text="Connect")
        self.status_var.set("Status: Disconnected")
        self.status_label.config(foreground="red")
        
        # Disable control buttons
        self.dispense_btn.config(state="disabled")
        self.cancel_btn.config(state="disabled")
        self.status_btn.config(state="disabled")
        
        # Reset progress
        self.progress_var.set("Ready")
        self.progress_bar['value'] = 0
        
        # Update window title
        self.update_window_title()
        
        self.log_message("Disconnected")
        self.manager_callback('disconnect', self.pump_id, {})
    
    """"
    def start_dispense(self):
        #Start dispensing (simulate if no hardware).
        if not self.is_connected:
            return
    # REMOVE the check for serial_connection:
    # if not self.serial_connection:
    #     return

        try:
            volume = float(self.volume_var.get())
            rate = float(self.rate_var.get())
            if volume <= 0 or rate <= 0:
                messagebox.showerror("Invalid Input", "Volume and rate must be positive numbers")
                return

            # Simulate dispensing
            self.is_dispensing = True
            self.dispense_btn.config(state="disabled")
            self.cancel_btn.config(state="normal")
            self.update_window_title()
            self.progress_var.set(f"Simulating dispense of {volume}mL at {rate}mL/min")
            self.progress_bar['value'] = 100
            self.log_message(f"Simulated: DISPENSE:{volume},{rate}")
            self.manager_callback('dispense_start', self.pump_id, {'volume': volume, 'rate': rate})
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for volume and rate")

    
    def cancel_dispense(self):
        #Cancel current dispensing (simulated if no hardware)
        if not self.is_connected:
            return

        # For simulation, just update states (don't require serial_connection)
        self.is_dispensing = False
        self.dispense_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.progress_bar['value'] = 0
        self.progress_var.set("Dispense Cancelled (simulated)")
        self.log_message("Simulated: CANCEL")
        self.manager_callback('dispense_cancel', self.pump_id, {})

    
    def get_status(self):
        #Request status from Arduino
        if not self.is_connected or not self.serial_connection:
            return
        
        try:
            self.serial_connection.write(b"STATUS\n")
            self.log_message("Sent: STATUS")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get status: {str(e)}")
    """

    def start_dispense(self):
        """Start dispensing"""
        if not self.is_connected or not self.serial_connection:
            return

        try:
            volume = float(self.volume_var.get())
            rate = float(self.rate_var.get())

            if volume <= 0 or rate <= 0:
                messagebox.showerror("Invalid Input", "Volume and rate must be positive numbers")
                return

            command = f"DISPENSE:{volume},{rate}\n"
            self.serial_connection.write(command.encode())

            self.is_dispensing = True
            self.dispense_btn.config(state="disabled")
            self.cancel_btn.config(state="normal")

            # Update window title
            self.update_window_title()

            self.log_message(f"Sent: {command.strip()}")
            self.manager_callback('dispense_start', self.pump_id, {'volume': volume, 'rate': rate})

        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numbers for volume and rate")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send command: {str(e)}")

    def cancel_dispense(self):
        """Cancel current dispensing"""
        if not self.is_connected or not self.serial_connection:
            return

        try:
            self.serial_connection.write(b"CANCEL\n")
            self.log_message("Sent: CANCEL")
            self.manager_callback('dispense_cancel', self.pump_id, {})
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send cancel: {str(e)}")

    def get_status(self):
        """Request status from Arduino"""
        if not self.is_connected or not self.serial_connection:
            return

        try:
            self.serial_connection.write(b"STATUS\n")
            self.log_message("Sent: STATUS")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get status: {str(e)}")

        

            
    def read_serial(self):
        """Read serial data in separate thread"""
        while self.is_connected and self.serial_connection:
            try:
                if self.serial_connection.in_waiting:
                    message = self.serial_connection.readline().decode().strip()
                    if message:
                        self.message_queue.put(message)
                time.sleep(0.1)
            except Exception as e:
                self.message_queue.put(f"Read error: {str(e)}")
                break
    
    def process_messages(self):
        """Process incoming serial messages"""
        try:
            while True:
                message = self.message_queue.get_nowait()
                self.handle_arduino_message(message)
        except queue.Empty:
            pass
        
        # Schedule next check
        if hasattr(self, 'window') and self.window.winfo_exists():
            self.window.after(100, self.process_messages)
    
    def handle_arduino_message(self, message):
        """Handle incoming Arduino messages"""
        self.log_message(f"Received: {message}")
        
        if message.startswith("STATUS:"):
            status = message[7:].strip()
            if "DISPENSING" in status:
                self.progress_var.set(f"Dispensing: {status}")
                if not self.is_dispensing:
                    self.is_dispensing = True
                    self.dispense_btn.config(state="disabled")
                    self.cancel_btn.config(state="normal")
                    self.update_window_title()
            else:
                self.progress_var.set(f"Status: {status}")
                if self.is_dispensing and status in ["IDLE", "CANCELLED", "ERROR"]:
                    self.is_dispensing = False
                    self.dispense_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.progress_bar['value'] = 0
                    self.reset_progress_variables()
                    self.update_window_title()
        
        elif message.startswith("PROGRESS_DETAILED:"):
            # Parse detailed progress information
            try:
                parts = message[18:].split(',')  # Remove "PROGRESS_DETAILED: " prefix
                if len(parts) >= 9:
                    self.current_progress = float(parts[0])
                    self.dispensed_volume = float(parts[1])
                    self.remaining_volume = float(parts[2])
                    self.elapsed_time = float(parts[3])
                    self.estimated_remaining_time = float(parts[4])
                    self.current_speed = float(parts[5])
                    
                    # Update GUI elements
                    self.progress_bar['value'] = self.current_progress
                    self.progress_var.set(f"Progress: {self.current_progress:.1f}%")
                    self.dispensed_var.set(f"Dispensed: {self.dispensed_volume:.2f} mL")
                    self.remaining_var.set(f"Remaining: {self.remaining_volume:.2f} mL")
                    self.elapsed_var.set(f"Elapsed: {self.elapsed_time:.1f} min")
                    self.remaining_time_var.set(f"ETA: {self.estimated_remaining_time:.1f} min")
                    self.speed_var.set(f"Current: {self.current_speed:.1f} mL/min")
            except (ValueError, IndexError) as e:
                self.log_message(f"Error parsing detailed progress: {e}")
        
        elif message.startswith("PROGRESS:"):
            # Extract progress percentage (backward compatibility)
            try:
                progress_part = message.split()[1]  # Get "XX.X%"
                progress_value = float(progress_part.replace('%', ''))
                self.progress_bar['value'] = progress_value
                self.progress_var.set(f"Progress: {message[9:]}")
            except:
                self.progress_var.set(f"Progress: {message[9:]}")
        
        elif message in ["DISPENSE_COMPLETE", "DISPENSE_CANCELLED"]:
            self.is_dispensing = False
            self.dispense_btn.config(state="normal")
            self.cancel_btn.config(state="disabled")
            self.progress_bar['value'] = 0 if "CANCELLED" in message else 100
            self.progress_var.set(message.replace("_", " ").title())
            self.reset_progress_variables()
            self.update_window_title()
            
            # Notify manager
            event_type = 'dispense_complete' if 'COMPLETE' in message else 'dispense_cancelled'
            self.manager_callback(event_type, self.pump_id, {})
    
    def reset_progress_variables(self):
        """Reset all progress variables when dispensing stops"""
        self.current_progress = 0.0
        self.dispensed_volume = 0.0
        self.remaining_volume = 0.0
        self.elapsed_time = 0.0
        self.estimated_remaining_time = 0.0
        self.current_speed = 0.0
        
        # Update GUI elements
        self.dispensed_var.set("Dispensed: 0.00 mL")
        self.remaining_var.set("Remaining: 0.00 mL")
        self.elapsed_var.set("Elapsed: 0.0 min")
        self.remaining_time_var.set("ETA: 0.0 min")
        self.speed_var.set("Current: 0.0 mL/min")
    
    def log_message(self, message):
        """Add message to log with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
    
    def clear_log(self):
        """Clear the communication log"""
        self.log_text.delete(1.0, tk.END)
    
    def on_closing(self):
        """Handle window closing"""
        if self.is_connected:
            if messagebox.askyesno("Close Window", 
                                 f"Pump '{self.name}' is still connected. Disconnect and close?"):
                self.disconnect_from_arduino()
                self.manager_callback('close', self.pump_id, {})
                self.window.destroy()
        else:
            self.manager_callback('close', self.pump_id, {})
            self.window.destroy() 