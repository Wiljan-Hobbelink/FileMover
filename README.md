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

**config.json**: Customize paths, file extensions, themes, FTP details, etc.

### Example config.json

Here is an example configuration file (`config.json`) for setting up **FileMover**.

```json
{
  "source_folders": {
    "SD Card": ["J:/", "K:/", "C:/FileMover/in", "C:/FileMover/in2"],
    "SXS Reader": "X:/",
    "SSD Drive": "S:/",
    "XQD Reader": "I:/",
    "Other Drive (D:/)": "D:/"
  },
  "default_destinations": {
    "SD Card": "ProjectB",
    "SXS Reader": "ProjectC"
  },
  "destination_folders_mapping": {
    "ProjectA": {
      ".mp4": [
        {
          "path": "C:/FileMover/out/ProjectA/MP4",
          "media_info_tracks": {
            "Video": {
              "format": "AVC",
              "width": "1920",
              "height": "1080",
              "frame_rate": "25.000"
            },
            "Audio": {
              "format": "AAC",
              "channels": "2",
              "sample_rate": "48000"
            }
          }
        }
      ],
      ".mxf": [
        {
          "path": "C:/FileMover/out/ProjectA/FS6",
          "media_info_tracks": {
            "General": {"codecs_video": "AVC", "commercial_name": "MXF"},
            "Video": {
              "format": "MPEG Video",
              "width": "1920",
              "height": "1080",
              "frame_rate": "29.970"
            },
            "Audio": {
              "format": "PCM",
              "channels": "2",
              "sample_rate": "48000"
            }
          }
        }
      ]
    },
    "ProjectB": {
      ".mp4": [
        {
          "path": "C:/FileMover/out/ProjectB/MP4",
          "media_info_tracks": {
            "Video": {
              "format": "HEVC",
              "width": "3840",
              "height": "2160",
              "frame_rate": "30.000"
            },
            "Audio": {
              "format": "AAC",
              "channels": "2",
              "sample_rate": "48000"
            }
          }
        }
      ],
      ".avi": [
        {
          "path": "C:/FileMover/out/ProjectB/avi",
          "media_info_tracks": {
            "Video": {
              "format": "MPEG-4 Visual",
              "width": "720",
              "height": "576",
              "frame_rate": "25.000"
            },
            "Audio": {
              "format": "MP3",
              "channels": "2",
              "sample_rate": "44100"
            }
          }
        }
      ]
    },
    "ProjectC": {
      ".mp4": [
        {
          "path": "C:/FileMover/out/ProjectC/MP4",
          "media_info_tracks": {
            "Video": {
              "format": "AVC",
              "width": "1280",
              "height": "720",
              "frame_rate": "29.970"
            },
            "Audio": {
              "format": "AAC",
              "channels": "2",
              "sample_rate": "48000"
            }
          }
        }
      ],
      ".mxf": [
        {
          "path": "C:/FileMover/out/ProjectC/FS6",
          "media_info_tracks": {
            "General": {"codecs_video": "AVC", "commercial_name": "MXF"},
            "Video": {
              "format": "AVC",
              "width": "1920",
              "height": "1080",
              "frame_rate": "29.970"
            },
            "Audio": {
              "format": "PCM",
              "channels": "2",
              "sample_rate": "48000"
            }
          }
        }
      ]
    }
  },
  "update_file_listbox": [".mp4", ".avi", ".mkv", ".mov", ".mxf", ".mts"],
  "theme": "light",
  "enable_custom_export": true,
  "enable_ftp_export": true,
  "perform_hash_check": false
}
```
### Explanation:
**source_folders:**  Defines paths for source folders, where files can be selected for copying.
**destination_folders_mapping:** Specifies paths for different file types (e.g., .mp4, .mov, etc.) for each destination, with optional media info requirements.
**default_destinations:** Sets default destination folders based on the selected source folder.
**theme:** Sets the theme of the application ("light" or "dark").
**enable_custom_export:** Enables or disables the option to copy files to a custom location.
**enable_ftp_export:** Enables or disables the FTP upload functionality.
**update_file_listbox:** Defines file extensions to display in the file list.
**perform_hash_check:** Enables or disables hash checking to verify file integrity after copying.

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
