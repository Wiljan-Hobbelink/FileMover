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
  - `tkinter`, `tkcalendar`, `vlc`, `hashlib`, `pymediainfo`, `cryptography`, `ftplib`
  
  Install all dependencies with:
  ```bash
  pip install python-vlc pymediainfo cryptography tkcalendar
