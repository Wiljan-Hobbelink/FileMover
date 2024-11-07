# FileMover

**FileMover** is a Python-based GUI application for transferring files between selected source and destination folders, with features like file integrity checks, customizable export settings, and FTP upload support. It uses a Tkinter-based interface, VLC for media playback, and allows convenient file management and metadata checking.

## Features
- **Copy Files**: Copy files from the source to the destination folder with optional custom destination paths.
- **FTP Upload**: Upload files to an FTP server with encrypted credentials.
- **Media Playback**: Play selected media files using VLC.
- **File Integrity Check**: Optionally verify file integrity via hash comparisons.
- **Customizable Configuration**: Use `config.json` to define source/destination folders, file extensions, and FTP settings.
- **Logging**: Maintains logs for operations and automatically deletes logs older than 14 days.

## Requirements
- **Python 3.x**
- Required libraries:
  - `tkinter`, `tkcalendar`, `vlc`, `hashlib`, `pymediainfo`, `cryptography`, `ftplib`, `fsv_ttk`
  
  Install all dependencies with:
  ```bash
  pip install tkcalendar python-vlc pymediainfo cryptography sv_ttk
-------------

## Configuration

1.  **config.json**: Customize paths, file extensions, themes, FTP details, etc.
2.  **FTP Credentials**: Stored in `ftpConfig/ftp_credentials.json` with encryption enabled.
3.  **Logs**: Saved in the `logs` folder and rotated daily.

Usage
-----

1.  **Run the application**:

    bash

    Code kopiëren

    `python Filemover.py`

2.  **Select a source folder and destination folder**, and choose files to copy or upload.

3.  Use the provided buttons to:

    -   **Play media**
    -   **Copy files** to the selected destination
    -   **Upload files** to an FTP server
4.  Use the progress bar and log messages for tracking the status of operations.

Keyboard Shortcuts
------------------

-   **F5**: Refresh the file list
-   **Ctrl+E**: Copy files to a custom location (if enabled)
-   **Ctrl+F**: Open FTP upload window (if enabled)

Logging
-------

Logs are saved in the `logs` directory and automatically cleaned up after 14 days.

![App Screenshot](https://github.com/Wiljan-Hobbelink/Filemover/blob/main/Assets/screenshot.jpg)

License
-------

This project is licensed under the **MIT License**.
