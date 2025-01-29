import os
import shutil
import tkinter as tk
from tkinter import Listbox, StringVar, ttk, messagebox, filedialog, PhotoImage
import vlc
import hashlib
import datetime
from tkcalendar import DateEntry
import json
import logging
from logging.handlers import TimedRotatingFileHandler
from pymediainfo import MediaInfo
import time
import threading
import unicodedata
import re
import sv_ttk
import ftplib
from cryptography.fernet import Fernet

class FileCopyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FileMover")  

        self.manual_position_update = False

        # Initialize flag to check if copying is in progress
        self.is_copying = False  
        
        # Bind the window close event to a custom handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)        

        # Set up the directory for FTP configurations
        self.ftp_config_folder = os.path.join(os.getcwd(), 'ftpConfig')
        if not os.path.exists(self.ftp_config_folder):
            os.makedirs(self.ftp_config_folder)

        # Use paths with the new subfolder
        self.ftp_credentials_path = os.path.join(self.ftp_config_folder, 'ftp_credentials.json')
        self.secret_key_path = os.path.join(self.ftp_config_folder, 'secret.key') 

        self.load_configuration()  # Assuming this method or similar ones will use the updated paths               

        # Configure logging
        log_folder = "logs"  # Change this to the desired folder for log files

        if not os.path.exists(log_folder):
            os.makedirs(log_folder)

        log_file = os.path.join(log_folder, "file_copy_app.log")
        
        # Use a different file name pattern for rotation, including date placeholders
        handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=0, encoding='utf-8', atTime=datetime.time(0, 0, 0))
        handler.suffix = "%Y-%m-%d.log"
        
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

        # Cleanup logs older than 14 days
        self.cleanup_old_logs(log_folder, days=14)

        logging.info("GUI opened.") 

        # Load configuration from the file
        self.load_configuration()

        sv_ttk.set_theme(self.theme)

        # Custom location if enabled
        if self.enable_custom_export:
            self.root.bind('<Control-e>', self.copy_to_custom_location)

        # FTP upload if enabled
        if self.enable_ftp_export:
            self.root.bind('<Control-f>', self.open_ftp_upload_window)   

        # Bind the F5 key to refresh the listbox
        self.root.bind('<F5>', self.update_file_listbox)    

        # Set the minimum size as a percentage of the screen size
        self.set_min_size_by_percentage(50, 50)  # For example, 50% width and 30% height of the screen            

        # Schedule the initial date picker update after a short delay
        self.root.after(100, self.initialize_date_picker)

        # Load icons
        if self.theme == "dark":
            self.save_icon_path = './Icons/save_icon_dark.png'
            self.delete_icon_path = './Icons/delete_icon_dark.png'
            self.upload_icon_path = './Icons/upload_icon_dark.png'
        else:
            self.save_icon_path = './Icons/save_icon.png'
            self.delete_icon_path = './Icons/delete_icon.png'
            self.upload_icon_path = './Icons/upload_icon.png'

        # Load icons
        self.save_icon = PhotoImage(file=self.save_icon_path)
        self.delete_icon = PhotoImage(file=self.delete_icon_path)
        self.upload_icon = PhotoImage(file=self.upload_icon_path)
  
        # Subfolder entry
        self.subfolder_label = ttk.Label(root, text="Naam:", font=("-size", 10, "-weight", "bold"),)
        self.subfolder_label.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self.subfolder_entry_var = StringVar()
        self.subfolder_entry = ttk.Entry(root, textvariable=self.subfolder_entry_var)
        self.subfolder_entry.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        # Date picker for subfolder date
        self.date_label = ttk.Label(root, text="Uitzenddatum:", font=("-size", 10, "-weight", "bold"),)
        self.date_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.date_picker_var = StringVar()
        self.date_picker = DateEntry(root, textvariable=self.date_picker_var, width=12, background='grey',
                                     foreground='white', borderwidth=2, style='CustomDateEntryStyle.DateEntry')
        self.date_picker.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
             
        # Source folder dropdown
        self.source_label = ttk.Label(root, text="Bron:", font=("-size", 10, "-weight", "bold"),)
        self.source_label.grid(row=2, column=0, padx=10, pady=10, sticky="nw")

        self.selected_source_folder = StringVar(value=next(iter(self.source_folders), ''))
        self.source_dropdown = ttk.Combobox(root, textvariable=self.selected_source_folder,
                                            values=list(self.source_folders.keys()), state="readonly", style='TCombobox')
        self.source_dropdown.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        self.source_dropdown.bind("<FocusIn>", lambda event: event.widget.selection_clear())
        
        # Destination folder dropdown
        self.destination_label = ttk.Label(root, text="Bestemming:", font=("-size", 10, "-weight", "bold"),)
        self.destination_label.grid(row=3, column=0, padx=10, pady=10, sticky="nw")

        self.destination_dropdown = ttk.Combobox(root, textvariable=self.selected_destination_folder,
                                                values=list(self.destination_folders_mapping.keys()), state="readonly", style='TCombobox')
        self.destination_dropdown.grid(row=3, column=1, padx=10, pady=10, sticky="nw")


        self.destination_dropdown.bind("<FocusIn>", lambda event: event.widget.selection_clear())

        # Listbox to display files
        self.file_listbox = Listbox(root, selectmode="extended", exportselection=False, font=("Helvetica", 11))
        self.file_listbox.grid(row=3, column=0, rowspan=6, columnspan=2, padx=7, pady=55, sticky="nsew")

        # Play button
        self.play_button = ttk.Button(root, text="                 Play                 ", command=self.play_media, style="Accent.TButton")
        self.play_button.grid(row=10, column=1, padx=10, pady=10, sticky="e")

        # Copy button
        self.copy_button = ttk.Button(root, text="         Kopiëren         ", command=self.copy_files, style="Accent.TButton")
        self.copy_button.grid(row=11, column=2, padx=10, pady=10, sticky="e")

        # Frame to hold the Refresh and Select All buttons
        self.buttons_frame = tk.Frame(root)
        self.buttons_frame.grid(row=10, column=0, padx=10, pady=10, sticky="ew")

        # Refresh button
        self.refresh_button = ttk.Button(self.buttons_frame, text="    Refresh (F5)    ", command=self.update_file_listbox, style="Accent.TButton")
        self.refresh_button.pack(side="left", padx=(0, 5))

        # Select All button
        self.select_all_button = ttk.Button(self.buttons_frame, text="    Select All    ", command=self.select_all_files, style="Accent.TButton")
        self.select_all_button.pack(side="left")

        # Calculate desired canvas size as a percentage of screen size
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        canvas_width = int(screen_width * 0.7)  # For example, 75% of the screen width
        canvas_height = int(screen_height * 0.7)  # For example, 50% of the screen height

        # Media player canvas
        self.media_player_canvas = tk.Canvas(root, width=canvas_width, height=canvas_height)
        self.media_player_canvas.grid(row=1, column=2, rowspan=6, padx=10, pady=10, sticky="nsew")

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(root, variable=self.progress_var, mode="determinate")
        self.progress_bar.grid(row=0, column=2, columnspan=2, padx=10, pady=10, sticky="we")

        # Duration display label
        self.duration_label = ttk.Label(root, text=r"\ 00:00:00:00")
        self.duration_label.grid(row=11, column=2, padx=85, pady=5, sticky="w")

        # Current time display label
        self.current_time_label = ttk.Label(root, text="00:00:00:00")
        self.current_time_label.grid(row=11, column=2, padx=10, pady=5, sticky="w")

        # Create VLC media player instance with native interface
        self.instance = vlc.Instance("--no-xlib")
        self.player = self.instance.media_player_new()
        
        # Bind the listbox selection event to load_media
        self.file_listbox.bind("<<ListboxSelect>>", lambda event: self.load_media())

        # Update the file listbox when the source folder is selected
        self.source_dropdown.bind("<<ComboboxSelected>>", lambda event: self.update_file_listbox())

        self.source_dropdown.bind("<<ComboboxSelected>>", self.on_source_selection)
  
        # Scrub bar
        self.scrub_bar = ttk.Scale(root, from_=0, to=100, orient="horizontal", length=400, command=self.update_player_position)
        self.scrub_bar.set(0)
        self.scrub_bar.grid(row=10, column=2, padx=10, pady=10, sticky="ew")

        # Bind events to detect when the user starts and ends interacting with the scrub bar
        self.scrub_bar.bind("<ButtonPress-1>", self.on_scrub_start)
        self.scrub_bar.bind("<ButtonRelease-1>", self.on_scrub_end)


        self.copied_files_label_var = StringVar(value=" ")
        self.copied_files_label = ttk.Label(root, textvariable=self.copied_files_label_var)
        self.copied_files_label.grid(row=11, column=2, padx=200, pady=10, sticky="e")

        # Flag to indicate manual position update
        self.manual_position_update = False

        # Make the GUI resizable
        root.grid_rowconfigure(3, weight=1)
        root.grid_columnconfigure(0, weight=0, uniform="group1")
        root.grid_columnconfigure(2, weight=6, uniform="group1")

        # Update duration and current time labels periodically
        self.update_time_labels()

        self.key = self.load_key()

        # Splash screen handling with logging
        try:
            import pyi_splash
            pyi_splash.update_text('UI Loaded ...')
            pyi_splash.close()
            logging.info("Splash screen closed successfully.")
        except ModuleNotFoundError:
            logging.info("pyi_splash module not found; skipping splash screen handling.")
        except Exception as e:
            logging.error(f"Error closing splash screen: {e}")


    def cleanup_old_logs(self, log_folder, days=14):
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
        for filename in os.listdir(log_folder):
            file_path = os.path.join(log_folder, filename)
            if os.path.isfile(file_path):
                file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_time < cutoff_date:
                    try:
                        os.remove(file_path)
                        logging.info(f"Deleted old log file: {filename}")
                    except Exception as e:
                        logging.error(f"Error deleting file {filename}: {e}")

    def generate_key(self):
        # Generate a new encryption key and save it to a file.
        key = Fernet.generate_key()
        with open(self.secret_key_path, "wb") as key_file:
            key_file.write(key)
        return key

    def load_key(self):
        # Load the encryption key from a file, generating a new one if it doesn't exist.
        try:
            return open(self.secret_key_path, "rb").read()
        except FileNotFoundError:
            # Generate the key if it does not exist
            return self.generate_key()

    def encrypt_password(self, password):
        # Encrypt a password using the loaded key.
        f = Fernet(self.key)
        encrypted_password = f.encrypt(password.encode())
        return encrypted_password.decode()

    def decrypt_password(self, encrypted_password):
        # Decrypt an encrypted password using the loaded key.
        f = Fernet(self.key)
        decrypted_password = f.decrypt(encrypted_password.encode())
        return decrypted_password.decode()    

    def save_ftp_credentials(self):
        new_credential = {
            'server': self.ftp_server_var.get(),
            'username': self.ftp_username_var.get(),
            'password': self.encrypt_password(self.ftp_password_var.get())
        }
        try:
            with open(self.ftp_credentials_path, 'r') as f:
                credentials_list = json.load(f)  # Load existing data
        except (FileNotFoundError, json.JSONDecodeError):
            credentials_list = []  # Initialize if not found or empty

        credentials_list.append(new_credential)  # Append new credentials

        with open(self.ftp_credentials_path, 'w') as f:
            json.dump(credentials_list, f)  # Save the list back to file

        messagebox.showinfo("Opslaan succesvol", "FTP-inloggegevens zijn succesvol opgeslagen.")
        self.load_ftp_credentials()  # Refresh credentials list in the combobox

    def open_ftp_upload_window(self, event=None):
        # Check if the subfolder entry is empty
        subfolder_name = self.subfolder_entry_var.get().strip()
        if not subfolder_name:
            messagebox.showwarning("Lege Subfolder Naam", "Voer een naam in voordat u uploadt.")
            return  # Cancel the upload process        
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Fout", "Selecteer ten minste één bestand om te uploaden.")
            return        
        self.ftp_window = tk.Toplevel(self.root)
        self.ftp_window.title("FTP Upload")
        self.ftp_window.transient(self.root)  # Set to be a transient window of the main app window
        self.ftp_window.grab_set()  # Grab all events directed to the application to this window        

        self.ftp_window.iconbitmap('./Icons/arrow.ico')

        # Get screen width and height
        screen_width = self.ftp_window.winfo_screenwidth()
        screen_height = self.ftp_window.winfo_screenheight()

        # Calculate window size as a percentage of screen size
        window_width = max(400, int(screen_width * 0.2))  # 50% of the screen width
        window_height = max(300, int(screen_height * 0.25))  # 50% of the screen height

        # Set the position (center the window)
        x_position = int((screen_width - window_width) / 2)
        y_position = int((screen_height - window_height) / 2)

        # Apply the calculated geometry
        self.ftp_window.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")

        # Configure grid behavior to make elements expand
        self.ftp_window.grid_rowconfigure(0, weight=1)
        self.ftp_window.grid_rowconfigure(1, weight=1)
        self.ftp_window.grid_rowconfigure(2, weight=1)
        self.ftp_window.grid_rowconfigure(3, weight=1)
        self.ftp_window.grid_rowconfigure(4, weight=1)
        self.ftp_window.grid_rowconfigure(5, weight=1)
        self.ftp_window.grid_columnconfigure(0, weight=1)
        self.ftp_window.grid_columnconfigure(1, weight=1)        

        # Create a Combobox for saved FTP credentials
        ttk.Label(self.ftp_window, text="Opgeslagen inloggegevens:").grid(row=0, column=0, padx=5, sticky="w")
        self.ftp_creds_combobox = ttk.Combobox(self.ftp_window, state="readonly", postcommand=self.load_ftp_credentials, style='TCombobox')
        self.ftp_creds_combobox.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.load_ftp_credentials()  # Load credentials to populate the combobox initially

        self.ftp_creds_combobox.bind("<FocusIn>", lambda event: event.widget.selection_clear())

        # Detailed FTP configuration fields
        ttk.Label(self.ftp_window, text="FTP Server:").grid(row=1, column=0, padx=5, sticky="w")
        self.ftp_server_var = tk.StringVar()
        ttk.Entry(self.ftp_window, textvariable=self.ftp_server_var).grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        ttk.Label(self.ftp_window, text="Gebruikersnaam:").grid(row=2, column=0, padx=5, sticky="w")
        self.ftp_username_var = tk.StringVar()
        ttk.Entry(self.ftp_window, textvariable=self.ftp_username_var).grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        ttk.Label(self.ftp_window, text="Wachtwoord:").grid(row=3, column=0, padx=5, sticky="w")
        self.ftp_password_var = tk.StringVar()
        ttk.Entry(self.ftp_window, textvariable=self.ftp_password_var, show="*").grid(row=3, column=1, padx=10, pady=10, sticky="ew")

        ttk.Button(self.ftp_window, text="Uploaden  ", image=self.upload_icon, compound='right', command=self.upload_file_to_ftp, style="Accent.TButton").grid(row=4, column=1, padx=10, sticky="e")

        # Bind the Enter key to the upload_file_to_ftp function
        self.ftp_window.bind('<Return>', self.handle_ftp_upload_shortcut)      

        # Frame for buttons
        buttons_frame = ttk.Frame(self.ftp_window)
        buttons_frame.grid(row=4, column=0, columnspan=2, sticky="w")

        # Save and Delete Buttons within the frame
        ttk.Button(buttons_frame, image=self.save_icon, command=self.save_ftp_credentials, style="Accent.TButton").grid(row=0, column=0, padx=5, pady=10, sticky="w")
        ttk.Button(buttons_frame, image=self.delete_icon, command=self.delete_selected_credential, style="Accent.TButton").grid(row=0, column=1, sticky="e")

        # Make the grid cells in the frame expand and fill space
        buttons_frame.columnconfigure(0, weight=1)
        buttons_frame.columnconfigure(1, weight=1)

        self.ftp_creds_combobox.bind("<<ComboboxSelected>>", self.on_ftp_creds_selected)

        self.ftp_window.resizable(False, False)

    def handle_ftp_upload_shortcut(self, event=None):
        # Ensure all necessary fields have values before triggering the upload
        if self.ftp_server_var.get() and self.ftp_username_var.get() and self.ftp_password_var.get():
            self.upload_file_to_ftp()
        else:
            messagebox.showwarning("Incompleet formulier", "Vul alle velden in voordat u uploadt.")

    def load_ftp_credentials(self):
        try:
            with open(self.ftp_credentials_path, 'r') as f:
                credentials_list = json.load(f)
            self.ftp_creds_combobox['values'] = [f"{cred['username']}@{cred['server']}" for cred in credentials_list]
            if not credentials_list:  # Clear entries if no credentials are left
                self.ftp_server_var.set("")
                self.ftp_username_var.set("")
                self.ftp_password_var.set("")
        except FileNotFoundError:
            self.ftp_creds_combobox['values'] = []  # Ensure the dropdown is cleared if file not found

    def on_ftp_creds_selected(self, event=None):
        selected_index = self.ftp_creds_combobox.current()
        if selected_index == -1:
            return
        try:
            with open(self.ftp_credentials_path, 'r') as f:
                credentials_list = json.load(f)
            credential = credentials_list[selected_index]  # Access list by index, not a string
            self.ftp_server_var.set(credential['server'])
            self.ftp_username_var.set(credential['username'])
            self.ftp_password_var.set(self.decrypt_password(credential['password']))
        except (FileNotFoundError, IndexError):
            messagebox.showerror("Fout", "Kan de geselecteerde inloggegevens niet laden.")

    def delete_selected_credential(self):
        selected_index = self.ftp_creds_combobox.current()
        if selected_index == -1:
            messagebox.showinfo("Inloggegevens verwijderen", "Er is geen inloggegevens geselecteerd om te verwijderen.")
            return

        try:
            with open(self.ftp_credentials_path, 'r') as f:
                credentials_list = json.load(f)

            # Remove selected credential
            credentials_list.pop(selected_index)

            # Save the updated list back to the file
            with open(self.ftp_credentials_path, 'w') as f:
                json.dump(credentials_list, f)

            messagebox.showinfo("Inloggegevens verwijderen", "Geselecteerde inloggegevens zijn succesvol verwijderd.")
            self.load_ftp_credentials()  # Refresh the credentials list in the combobox
        except (FileNotFoundError, IndexError, json.JSONDecodeError) as e:
            messagebox.showerror("Fout", "Kan de geselecteerde inloggegevens niet verwijderen: " + str(e))

    def upload_file_to_ftp(self):
        # Check if the subfolder entry is empty
        subfolder_name = self.subfolder_entry_var.get().strip()
        if not subfolder_name:
            messagebox.showwarning("Lege Subfolder Naam", "Voer een naam in voordat u uploadt.")
            return  # Cancel the upload process        
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            messagebox.showerror("Fout", "Selecteer ten minste één bestand om te uploaden.")
            return

        # Collect all files to be uploaded
        files_to_upload = [self.source_folder_paths_and_names[i][0] for i in selected_indices]

        # Start the upload process in a single thread
        threading.Thread(target=self.perform_ftp_upload, args=(files_to_upload,), daemon=True).start()

    def perform_ftp_upload(self, files_to_upload):
        """Perform the FTP upload with support for nested subfolders."""
        # Fetch the subfolder name from the user input
        subfolder_name = self.subfolder_entry_var.get().strip()

        # Get date from date_picker_var, assuming it's formatted as 'dd-mm-yyyy'
        selected_date_str = self.date_picker_var.get()
        try:
            selected_date = datetime.datetime.strptime(selected_date_str, "%d-%m-%Y")
        except ValueError:
            messagebox.showwarning("Ongeldige datum", "De datum moet de notatie dd-mm-jjjj hebben. Corrigeer de datum en probeer het opnieuw.")
            self.copy_button.config(state="normal")
            return  # Cancel the copy process
        date_prefix = selected_date.strftime("%y%m%d")

        # Combine the date prefix with the subfolder name
        full_subfolder_name = f"{date_prefix}_{subfolder_name}"

        # Split the server address to handle subfolders
        server_address = self.ftp_server_var.get()
        server, *subfolder = server_address.split('/', 1)
        ftp_subfolder = subfolder[0] if subfolder else ''

        def ensure_directory_exists(session, directory_path):
            # Ensure that a directory exists on the FTP server, create if not
            directories = directory_path.split('/')
            for directory in directories:
                try:
                    session.cwd(directory)
                except ftplib.error_perm:
                    session.mkd(directory)
                    session.cwd(directory)

        try:
            # Attempt to connect to FTP or FTPS
            session = ftplib.FTP_TLS(server, self.ftp_username_var.get(), self.ftp_password_var.get())
            session.set_pasv(True)  # Set passive mode
            logging.info("Connected via FTPS.")
        except Exception as e:
            logging.info(f"FTPS connection failed: {e}. Trying regular FTP...")
            try:
                session = ftplib.FTP(server, self.ftp_username_var.get(), self.ftp_password_var.get())
                session.set_pasv(True)  # Set passive mode
            except Exception as e:
                messagebox.showerror("FTP-upload mislukt", f"Kan geen verbinding maken via FTPS of FTP: {str(e)}")
                return

        # Navigate to the specified subfolder if present
        if ftp_subfolder:
            ensure_directory_exists(session, ftp_subfolder)

        # Ensure the full subfolder exists
        ensure_directory_exists(session, full_subfolder_name)

        # Dictionary to keep track of file names and their counts
        file_name_counts = {}

        total_files = len(files_to_upload)
        uploaded_files = 0

        for file_to_upload in files_to_upload:
            file_name = os.path.basename(file_to_upload)
            creation_time = os.path.getctime(file_to_upload)

            if file_name in file_name_counts:
                file_name_counts[file_name] += 1
                base_name, ext = os.path.splitext(file_name)
                new_file_name = f"{base_name}_{file_name_counts[file_name]}{ext}"
            else:
                file_name_counts[file_name] = 1
                new_file_name = file_name

            try:
                with open(file_to_upload, 'rb') as file:
                    session.storbinary(f"STOR {new_file_name}", file)
                uploaded_files += 1
                logging.info(f"Uploaded {new_file_name} successfully.")
                # Update progress on the GUI thread after each file upload
                progress = (uploaded_files / total_files) * 100
                self.root.after(0, self.progress_var.set, progress)
            except Exception as e:
                logging.warning(f"Failed to upload {new_file_name}: {e}")

        # Reset directory to home or another specified baseline if necessary
        session.cwd('/')
        session.quit()

        # Set the date picker to today's date
        current_date = datetime.datetime.now().strftime("%d-%m-%Y")
        self.date_picker_var.set(current_date)

        # Reset progress bar after all uploads are done
        self.root.after(0, self.reset_progress)
        messagebox.showinfo("Upload voltooid", "Alle geselecteerde bestanden zijn geüpload.")


    def update_progress(self, uploaded, total_size):
        progress = (uploaded / total_size) * 100
        self.progress_var.set(progress)

    def reset_progress(self):
        self.progress_var.set(0) 

    def set_min_size_by_percentage(self, width_percent, height_percent):
        #Set the minimum size of the window based on a percentage of the screen size
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        min_width = int(screen_width * width_percent / 100)
        min_height = int(screen_height * height_percent / 100)
        self.root.minsize(min_width, min_height)                 

    def copy_to_custom_location(self, event=None):
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Geen bestanden geselecteerd", "Selecteer minstens één bestand om te kopiëren.")
            return

        destination_directory = filedialog.askdirectory()
        if not destination_directory:
            # User cancelled the dialog
            return

        # Collect full paths of selected files
        selected_files = [self.source_folder_paths_and_names[i][0] for i in selected_indices]

        # Start the copying in a separate thread
        threading.Thread(target=self.copy_files_to_custom_location, args=(selected_files, destination_directory), daemon=True).start()
    
    def copy_files_to_custom_location(self, selected_files, destination_directory):
        total_files = len(selected_files)
        successful_copies = 0  # Initialize a counter for successful copies
        
        # Dictionary to keep track of file names and their counts
        file_name_counts = {}
        
        for index, source_path in enumerate(selected_files, start=1):
            file_name = os.path.basename(source_path)
            creation_time = os.path.getctime(source_path)
            
            if file_name in file_name_counts:
                file_name_counts[file_name] += 1
                base_name, ext = os.path.splitext(file_name)
                new_file_name = f"{base_name}_{file_name_counts[file_name]}{ext}"
            else:
                file_name_counts[file_name] = 1
                new_file_name = file_name

            destination_path = os.path.join(destination_directory, new_file_name)
            
            try:
                shutil.copy2(source_path, destination_path)
                successful_copies += 1  # Increment on successful copy
                logging.info(f"File {source_path} copied to custom location {destination_path}")
                progress = (index / total_files) * 100
                # Update progress bar in a thread-safe manner
                self.root.after(0, self.progress_var.set, progress)
            except Exception as e:
                logging.error(f"Error copying file: {source_path} to {destination_directory}: {e}")

        # Ensure GUI updates are done in the main thread
        self.root.after(0, self.progress_var.set, 0)
        logging.info(f"Kopiëren voltooid. {successful_copies} van de {total_files} geselecteerde bestanden succesvol gekopieerd naar {destination_directory}.")
        copy_message = f"Kopiëren voltooid. {successful_copies} van de {total_files} geselecteerde bestanden succesvol gekopieerd naar {destination_directory}."
        self.root.after(0, messagebox.showinfo, "Kopiëren voltooid", copy_message)

    def select_all_files(self):
        self.file_listbox.select_set(0, "end")  # Selects all items in the listbox
        self.file_listbox.event_generate("<<ListboxSelect>>")  # Triggers the listbox select event

    def on_source_selection(self, event):
        selected_source = self.selected_source_folder.get()
        default_destination = self.default_destinations.get(selected_source)
        if default_destination:
            self.selected_destination_folder.set(default_destination)
        self.update_file_listbox()

    def update_time_labels(self):
        # Update duration and current time labels periodically.
        duration = self.player.get_length()
        if duration != -1:
            duration_str = self.format_time(duration)
            self.duration_label.config(text=fr"\ {duration_str}")

        current_time = self.player.get_time()
        if current_time != -1:
            current_time_str = self.format_time(current_time)
            self.current_time_label.config(text=f"{current_time_str}")

        self.root.after(100, self.update_time_labels)

    def format_time(self, milliseconds):
        # Format time from milliseconds to HH:MM:SS:FF.
        total_seconds = milliseconds // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        frames = (milliseconds // 33) % 25  # Assuming 25 frames per second
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"

    def update_player_position(self, value):
        # Only update the video position if the user is manually moving the scrub bar
        if self.manual_position_update:
            position = float(value) / 100
            self.player.set_position(position)

    def on_scrub_start(self, event):
        # The user has started interacting with the scrub bar
        self.manual_position_update = True

    def on_scrub_end(self, event):
        # The user has finished interacting with the scrub bar
        self.manual_position_update = False
        self.update_player_position(self.scrub_bar.get())
            

    def load_configuration(self):
        try:
            with open("config.json", "r") as config_file:
                self.config = json.load(config_file)
    
            # Load source folders
            self.source_folders = self.config.get("source_folders", {})
            for key, value in self.source_folders.items():
                if not isinstance(value, list):
                    self.source_folders[key] = [value]

            # Load the theme configuration
            self.theme = self.config.get("theme", "light")            

            # Load custom export configuration
            self.enable_custom_export = self.config.get("enable_custom_export", True)  

            # Load custom export configuration
            self.enable_ftp_export = self.config.get("enable_ftp_export", True)                   
    
            # Load destination folder mappings
            self.destination_folders_mapping = self.config.get("destination_folders_mapping", {})

            self.default_destinations = self.config.get("default_destinations", {})
    
            # Load file listbox update extensions
            self.update_file_listbox_extensions = self.config.get("update_file_listbox", [])
    
            # Initialize StringVars for selected source and destination, defaulting to the first key if available
            self.selected_source_folder = StringVar(value=next(iter(self.source_folders), ''))
            self.selected_destination_folder = StringVar(value=next(iter(self.destination_folders_mapping), ''))
    
        except FileNotFoundError:
            messagebox.showerror("Configuratiefout", "Configuratiebestand niet gevonden.")
            self.root.destroy()
        except json.JSONDecodeError as e:
            messagebox.showerror("Configuratiefout", f"Fout bij lezen configuratiebestand: {e}")
            self.root.destroy()

    def check_file_integrity(self, source, destination):
        #Compare file hashes
        source_hash = self.calculate_file_hash(source)
        destination_hash = self.calculate_file_hash(destination)
        return source_hash == destination_hash
  
    def calculate_file_hash(self, file_path, hash_algorithm="sha256", block_size=65536):
        # Calculate the hash of a file.
        hash_obj = hashlib.new(hash_algorithm)
        with open(file_path, "rb") as file:
            for block in iter(lambda: file.read(block_size), b""):
                hash_obj.update(block)
        return hash_obj.hexdigest()

    def show_error_message(self, file_name):
        # Show an error message.
        error_message = f"Fout: kopiëren van bestand '{file_name}' mislukt. Hashes komen niet overeen."
        messagebox.showerror("Kopieerfout", error_message)

    def update_file_listbox(self, event=None):
        selected_source_folders = self.source_folders[self.selected_source_folder.get()]

        source_folder_paths_and_names = []

        allowed_extensions = self.config.get("update_file_listbox", [])

        for selected_source_folder in selected_source_folders:
            for root, dirs, files in os.walk(selected_source_folder):
                for file_name in files:
                    _, file_extension = os.path.splitext(file_name.lower())
                    if file_extension in allowed_extensions:
                        full_path = os.path.join(root, file_name)
                        creation_time = os.path.getctime(full_path)
                        source_folder_paths_and_names.append((full_path, file_name, creation_time))

        # Custom sorting function to prioritize GX-prefixed files by chapter number
        def custom_sort_key(item):
            file_name = item[1]
            creation_time = item[2]

            # Check if the filename has a two-letter prefix followed by two digits and then a clip identifier
            match = re.match(r'([A-Z]{2})(\d{2})(\d+)', file_name)
            if match:
                # Extract the prefix (e.g., 'GX', 'AX'), chapter prefix (e.g., '01', '02'), and clip identifier (e.g., '1234')
                prefix = match.group(1)             # e.g., 'GX' or 'AX'
                chapter_prefix = int(match.group(2)) # e.g., '01' or '02'
                clip_identifier = int(match.group(3)) # The remaining identifier like '1234', '1240', etc.

                # Sort prefixed files by prefix alphabetically, then by clip identifier and chapter
                return (prefix, clip_identifier, chapter_prefix)
            else:
                # For non-prefixed files, sort alphabetically by filename
                return (file_name.lower(),)

        # Apply the updated sorting function in the update_file_listbox method
        source_folder_paths_and_names.sort(key=custom_sort_key)

        # Handle duplicate filenames
        file_name_counts = {}
        for i, (path, file_name, creation_time) in enumerate(source_folder_paths_and_names):
            if file_name in file_name_counts:
                file_name_counts[file_name] += 1
                base_name, ext = os.path.splitext(file_name)
                new_file_name = f"{base_name}_{file_name_counts[file_name]}{ext}"
                source_folder_paths_and_names[i] = (path, new_file_name, creation_time)
            else:
                file_name_counts[file_name] = 1

        self.file_listbox.delete(0, "end")
        for path, file_name, creation_time in source_folder_paths_and_names:
            self.file_listbox.insert("end", file_name)

        self.source_folder_paths_and_names = [(path, file_name) for path, file_name, creation_time in source_folder_paths_and_names]
 
    def load_media(self):
        selected_indices = self.file_listbox.curselection()

        self.play_button.config(text="                 Play                 ")

        if len(selected_indices) != 1:
            return

        selected_path, selected_file = self.source_folder_paths_and_names[selected_indices[0]]
        absolute_path = os.path.abspath(selected_path)
        media = self.instance.media_new(absolute_path)
        self.player.set_media(media)
        self.player.set_hwnd(self.media_player_canvas.winfo_id())  # Assign the media player to the Canvas widget

        # Start playback to initiate loading
        self.player.play()
        self.player.audio_set_mute(True)  # Mute the audio immediately after starting playback

        # Wait until the media is actually playing, then pause it
        def wait_for_media_ready():
            while True:
                state = self.player.get_state()
                if state in (vlc.State.Playing, vlc.State.Paused):
                    break
                time.sleep(0.1)

            # Seek to the first frame and pause the player
            if self.player.is_seekable():
                self.player.set_time(0)  # Seek to 40 milliseconds
                self.player.pause()  # Ensure the player is paused after seeking

        # Run the wait operation in a separate thread to avoid blocking the main GUI thread
        threading.Thread(target=wait_for_media_ready, daemon=True).start()

        # Reset the scrub bar to the start if applicable
        self.scrub_bar.set(0)

        logging.info(f"Media '{selected_file}' loaded and set to pause.")
 
    def play_media(self):
        if self.player.get_media():
            if self.player.is_playing():
                # If the video is playing, pause it and change button text to "Play"
                self.player.pause()
                self.play_button.config(text="                 Play                 ")
                logging.info("Video paused.")
            else:
                # If the video is paused, play it and change button text to "Pause"
                self.player.audio_set_mute(False)  # Ensure the audio is not muted
                self.player.play()
                self.play_button.config(text="               Pause                ")
                logging.info("Video playing.")
                self.update_scrub_bar()  # Start updating the scrub bar during playback
        else:
            logging.warning("No media loaded to play.")
            messagebox.showinfo("Afspeelfout", "Er is geen medium geladen. Selecteer een bestand uit de lijst.")

    def update_scrub_bar(self):
        if not self.manual_position_update:
            # Get the total length of the video
            length = self.player.get_length()
            
            # Get the current playback time
            current_time = self.player.get_time()

            if length > 0:
                # Calculate the position as a percentage
                position = (current_time / length) * 100
                self.scrub_bar.set(position)
        
        # Schedule the next update after 100 milliseconds
        self.root.after(100, self.update_scrub_bar)

    def copy_files(self):
        # Start the file copying in a background thread
        threading.Thread(target=self.copy_files_thread, daemon=True).start()

    def copy_files_thread(self):
        self.is_copying = True
        # Disable input controls to prevent user interaction during the copy process
        self.subfolder_entry.config(state="disabled")
        self.date_picker.config(state="disabled")
        self.source_dropdown.config(state="disabled")
        self.destination_dropdown.config(state="disabled")
        self.copy_button.config(state="disabled")

        # Record the start time for measuring the duration of the copy process
        start_time = time.time()

        try:
            # Check if hash check is enabled in the configuration
            perform_hash_check = self.config.get("perform_hash_check", True)

            # Validate the selected date from the date picker
            try:
                selected_date = self.date_picker_var.get()
                datetime.datetime.strptime(selected_date, "%d-%m-%Y")
            except ValueError:
                messagebox.showwarning(
                    "Ongeldige datum",
                    "De datum moet de notatie dd-mm-jjjj hebben. "
                    "Corrigeer de datum en probeer het opnieuw."
                )
                self.subfolder_entry.config(state="normal")
                self.date_picker.config(state="normal")
                self.source_dropdown.config(state="normal")
                self.destination_dropdown.config(state="normal")
                self.copy_button.config(state="normal")
                self.is_copying = False
                return

            # Retrieve and validate the subfolder name from user input
            subfolder_name = self.subfolder_entry_var.get().strip()

            # 1) Normalize the input to a standard Unicode form (e.g., NFC).
            subfolder_name = unicodedata.normalize('NFC', subfolder_name)

<<<<<<< HEAD
            # 2) Define a pattern that forbids Windows-reserved ASCII chars and control characters
            pattern = r'[\u0000-\u001F\u007F-\u009F\\/:*?"<>|]'
=======
            # 2) Define a pattern that forbids:
            #    - Windows-reserved ASCII characters  (\/:*?"<>|)
            #    - ASCII control characters           [\u0000-\u001F\u007F]
            #    - Unicode C1 control characters      [\u0080-\u009F]
            pattern = r'[\u0000-\u001F\u007F-\u009F\\/:*?"<>|]'

>>>>>>> 4ef7c679184ab47df35b991f062579cd2e417278
            if re.search(pattern, subfolder_name):
                logging.warning("Copy button pressed, but folder name contains invalid or control characters.")
                messagebox.showwarning(
                    'Ongeldige naam',
                    'De naam van de submap bevat ongeldige of speciale tekens. '
                    'Corrigeer de naam en probeer het opnieuw.'
                )
                self.subfolder_entry.config(state="normal")
                self.date_picker.config(state="normal")
                self.source_dropdown.config(state="normal")
                self.destination_dropdown.config(state="normal")
                self.copy_button.config(state="normal")
                self.is_copying = False
                return

            if not subfolder_name:
                messagebox.showwarning("Lege naamveld", "Voer een naam in.")
                self.subfolder_entry.config(state="normal")
                self.date_picker.config(state="normal")
                self.source_dropdown.config(state="normal")
                self.destination_dropdown.config(state="normal")
                self.copy_button.config(state="normal")
                self.is_copying = False
                return

            # Get selected source and destination folders from the dropdowns
            selected_source_folder = self.source_folders[self.selected_source_folder.get()]
            selected_destination_folder = self.destination_folders_mapping[self.selected_destination_folder.get()]

            # Get the list of selected files from the listbox
            selected_files = [self.file_listbox.get(i) for i in self.file_listbox.curselection()]

            if not selected_files:
                logging.warning("Copy button pressed, but no files selected.")
                messagebox.showwarning("Geen bestanden geselecteerd", "Selecteer de bestanden die u wilt kopiëren.")
                self.subfolder_entry.config(state="normal")
                self.date_picker.config(state="normal")
                self.source_dropdown.config(state="normal")
                self.destination_dropdown.config(state="normal")
                self.copy_button.config(state="normal")
                self.is_copying = False
                return

            logging.info(f"Copy button pressed. Copying {len(selected_files)} file(s).")

            total_files = len(selected_files)
            completed_files = 0

            # Format the subfolder name with the selected date
            selected_datetime = datetime.datetime.strptime(selected_date, "%d-%m-%Y")
            subfolder_name_with_date = selected_datetime.strftime("%y%m%d") + "_" + subfolder_name

            # Loop through selected files and copy them to the destination
            for index in self.file_listbox.curselection():
                source_path, file_name = self.source_folder_paths_and_names[index]
                _, file_extension = os.path.splitext(file_name.lower())

                # Only proceed if there's a matching extension mapping in the destination folder config
                if file_extension in selected_destination_folder:
                    destination_info_list = selected_destination_folder[file_extension]

                    # Try each path in this extension's list
                    for destination_info in destination_info_list:
                        destination_path_base = destination_info.get("path")
                        extension_media_info_tracks = destination_info.get("media_info_tracks", {})

                        # --- Media Info Check ---
                        # Always define media_info
                        media_info = MediaInfo.parse(source_path)

                        # We'll track whether the file’s media info fails the checks
                        mismatch_occurred = False  
                        # Also define a default for actual_value
                        actual_value = None  

                        # Parse media_info tracks, check them against the config if present
                        for track in media_info.tracks:
                            track_type = track.track_type
                            if track_type in extension_media_info_tracks:
                                # For each required attribute + expected value
                                for attr, expected_value in extension_media_info_tracks[track_type].items():
                                    actual_value = getattr(track, attr, "N/A")
                                    if actual_value != expected_value:
                                        mismatch_occurred = True

                        # If we found any mismatch, skip copying this file
                        if mismatch_occurred:
                            logging.warning(
                                f"Skipping copying of file '{file_name}' due to media info mismatch. "
                                f"Last actual_value read: {actual_value}"
                            )
                            continue
                        # --- End Media Info Check ---

                        # Build the actual path with date-based subfolder
                        destination_path = os.path.join(destination_path_base, subfolder_name_with_date)
                        if not os.path.exists(destination_path):
                            os.makedirs(destination_path)

                        destination_path = os.path.join(destination_path, os.path.basename(file_name))

                        # If the file already exists, handle overwrite logic
                        if os.path.exists(destination_path):
                            overwrite = messagebox.askyesnocancel(
                                "Bestand bestaat",
                                f"Het bestand '{file_name}' bestaat al. "
                                "Wil je het overschrijven?",
                                default=messagebox.YES
                            )
                            if overwrite is None:
                                # User chose "Cancel" => cancel entire copy operation
                                self.progress_var.set(0)
                                self.subfolder_entry.config(state="normal")
                                self.date_picker.config(state="normal")
                                self.source_dropdown.config(state="normal")
                                self.destination_dropdown.config(state="normal")
                                self.copy_button.config(state="normal")
                                self.is_copying = False
                                return
                            elif overwrite:
                                logging.info(f"User chose to overwrite '{file_name}'.")
                            else:
                                # User chose 'No' => skip this file
                                logging.info(f"User chose NOT to overwrite '{file_name}'.")
                                continue

                        # Update counters, progress
                        completed_files += 1
                        self.root.after(0, self.copied_files_label_var.set,
                                    f"Kopiëren: {completed_files}/{total_files}")
                        progress_value = (completed_files / total_files) * 100
                        self.progress_var.set(progress_value)
                        self.root.update_idletasks()

                        # Copy the file
                        shutil.copy2(source_path, destination_path)
                        logging.info(f"File '{file_name}' copied to '{destination_path}'.")

<<<<<<< HEAD
                        # If "adjust_time" is True, set the file timestamps to now
                        if destination_info.get("adjust_time", False):
                            current_time = time.time()
                            os.utime(destination_path, (current_time, current_time))

                        # --- Optional File Verification Logic ---
=======
                        # --- File Verification Logic ---
>>>>>>> 4ef7c679184ab47df35b991f062579cd2e417278
                        if perform_hash_check:
                            # Perform hash check
                            source_hash = self.calculate_file_hash(source_path)
                            destination_hash = self.calculate_file_hash(destination_path)
                            if source_hash == destination_hash:
                                logging.info(f"Hashes match for file '{file_name}'. Copy successful.")
                            else:
                                logging.info(
                                    f"Hashes do not match for file '{file_name}'. "
                                    f"Copy may not be successful."
                                )
                                self.show_error_message(file_name)
                        else:
                            source_size = os.path.getsize(source_path)
                            destination_size = os.path.getsize(destination_path)
                            if source_size == destination_size:
                                logging.info(f"File sizes match for '{file_name}'. Copy successful.")
                            else:
                                logging.info(
                                    f"File sizes do not match for '{file_name}'. "
                                    f"Copy may not be successful."
                                )
                                self.show_error_message(file_name)
                        else:
                            # Compare file sizes
                            source_size = os.path.getsize(source_path)
                            destination_size = os.path.getsize(destination_path)
                            if source_size == destination_size:
                                logging.info(f"File sizes match for '{file_name}'. Copy successful.")
                            else:
                                logging.info(f"File sizes do not match for '{file_name}'. Copy may not be successful.")
                                self.show_error_message(file_name)
                        # --- End of File Verification Logic ---

                        # If we successfully copied to this `destination_info`,
                        # we can break out of the `for destination_info in destination_info_list` loop
                        break

            # Measure the total duration of the copy process
            duration = time.time() - start_time

            # Reset GUI controls and show completion message
            self.progress_var.set(0)
            self.subfolder_entry.config(state="normal")
            self.date_picker.config(state="normal")
            self.source_dropdown.config(state="normal")
            self.destination_dropdown.config(state="normal")
            self.copy_button.config(state="normal")

            logging.info(
                f"Copying {completed_files} file(s) to '{subfolder_name_with_date}' "
                f"completed in {duration:.2f} seconds."
            )

            current_date = datetime.datetime.now().strftime("%d-%m-%Y")
            self.date_picker_var.set(current_date)

<<<<<<< HEAD
            self.root.after(0, self.copied_files_label_var.set, "Kopiëren: Voltooid")
            messagebox.showinfo(
                "Kopiëren voltooid",
                f"Kopiëren voltooid. {completed_files} bestanden gekopieerd naar '{subfolder_name_with_date}'."
            )

            self.is_copying = False
=======
            self.is_copying = False            
>>>>>>> 4ef7c679184ab47df35b991f062579cd2e417278

        except Exception as e:
            # Handle any exceptions that occur during the copy process
            logging.error(f"An error occurred during file copying: {str(e)}")
            messagebox.showerror(
                "Fout",
                f"Er is een fout opgetreden tijdens het kopiëren van de bestanden: {str(e)}"
            )
            self.progress_var.set(0)
            self.subfolder_entry.config(state="normal")
            self.date_picker.config(state="normal")
            self.source_dropdown.config(state="normal")
            self.destination_dropdown.config(state="normal")
            self.copy_button.config(state="normal")

            self.is_copying = False


<<<<<<< HEAD

=======
>>>>>>> 4ef7c679184ab47df35b991f062579cd2e417278
    def initialize_date_picker(self):
        # Get the current time and date
        now = datetime.datetime.now()
        current_time = now.time()

        # Calculate the next occurrence of 00:01
        if current_time >= datetime.time(0, 1):
            # If current time is 00:01 or later, next 00:01 is on the next day
            next_datetime = datetime.datetime(now.year, now.month, now.day) + datetime.timedelta(days=1, minutes=1)
        else:
            # If current time is before 00:01, next 00:01 is today
            next_datetime = datetime.datetime(now.year, now.month, now.day, 0, 1)

        # Calculate how many seconds until next 00:01
        delta_seconds = (next_datetime - now).total_seconds()

        # Set the initial date format in the date picker
        current_date = now.date()
        initial_date = current_date.strftime("%d-%m-%Y")  # Format it as string "dd-mm-yyyy"
        
        # Set locale and date pattern
        self.date_picker.configure(locale='nl_NL')
        self.date_picker.config(date_pattern='dd-MM-yyyy')
        
        # Set the newly formatted date string as the current date in the date picker
        self.date_picker_var.set(initial_date)

        # Schedule to run again at next 00:01
        self.root.after(int(delta_seconds * 1000), self.initialize_date_picker)

    def on_close(self):
        # Check if a copy action is in progress
        if self.is_copying:
            # Ask the user if they really want to close the app
            if not messagebox.askyesno("Bevestiging", "Een kopieeractie is nog bezig. Weet u zeker dat u wilt afsluiten?"):
                return  # If 'No' is selected, do nothing
    
        # Log application closure
        logging.info("Application closed by the user.")

        # If no copy in progress or 'Yes' is selected, close the application
        self.root.destroy()

    def __del__(self):
        logging.info("GUI closed.")

if __name__ == "__main__":
    root = tk.Tk()
    app = FileCopyApp(root)
    root.state('zoomed')
    root.iconbitmap('./Icons/arrow.ico')
    root.mainloop()