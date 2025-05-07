import json
import argparse
import os
import glob
import re
import time
import tkinter as tk
from tkinter import filedialog, messagebox
import xml.etree.ElementTree as ET
import logging
from datetime import datetime, timedelta
from dateutil import parser as date_parser
import platform
import sys

# --- Logging setup ---
def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)  # When frozen (.exe)
    return os.path.dirname(os.path.abspath(__file__))  # When run as script

BASE_DIR = get_base_path()
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)

def cleanup_logs(retention_days=14):
    now = datetime.now()
    for fname in os.listdir(LOG_DIR):
        fpath = os.path.join(LOG_DIR, fname)
        try:
            # Expect logs named YYYY-MM-DD.log
            date_str, ext = os.path.splitext(fname)
            file_date = datetime.strptime(date_str, '%Y-%m-%d')
            if now - file_date > timedelta(days=retention_days):
                os.remove(fpath)
        except Exception:
            continue

# Initialize log cleanup
cleanup_logs()

def start_log_cleanup_loop(interval_hours=24, retention_days=14):
    import threading
    def loop():
        while True:
            cleanup_logs(retention_days)
            time.sleep(interval_hours * 3600)
    threading.Thread(target=loop, daemon=True).start()

# Start periodic log cleanup
start_log_cleanup_loop()


# Configure daily log file
today = datetime.now().strftime('%Y-%m-%d')
log_file = os.path.join(LOG_DIR, f"{today}.log")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[logging.FileHandler(log_file, encoding='utf-8')]
)

# Optional imports
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    yaml = None
    _HAS_YAML = False

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _HAS_WATCHDOG = True
except ImportError:
    _HAS_WATCHDOG = False
    

def get_resource_path(filename):
    """Always look for resources in the folder where the .exe is running."""
    base_path = os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__)
    return os.path.join(base_path, filename)

def is_directory_available(path):
    try:
        return os.path.isdir(path) and os.access(path, os.R_OK | os.W_OK)
    except Exception:
        return False




# ----------------------- Core Functions ----------------------------

def load_json_with_retry(path, retries=5, delay=0.5):
    for attempt in range(1, retries + 1):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (PermissionError, json.JSONDecodeError):
            if attempt < retries:
                time.sleep(delay)
            else:
                raise

def load_mapping_config(path):
    ext = os.path.splitext(path)[1].lower()
    with open(path, 'r', encoding='utf-8') as f:
        if ext in ('.yml', '.yaml'):
            if not _HAS_YAML:
                raise RuntimeError(
                    "PyYAML is required for YAML configs. "
                    "Install with 'pip install pyyaml' or use JSON."
                )
            return yaml.safe_load(f)
        else:
            return json.load(f)

def load_template(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

import re

def parse_format_ops(fmt):
    ops = []
    i = 0
    while i < len(fmt):
        # Grouped operations
        if fmt[i] == '(':
            depth = 1
            j = i + 1
            while j < len(fmt) and depth > 0:
                if fmt[j] == '(':
                    depth += 1
                elif fmt[j] == ')':
                    depth -= 1
                j += 1
            group = fmt[i + 1:j - 1]
            ops.append(parse_format_ops(group))  # Recursive group
            i = j

        # Regex replace: replace'from','to'
        elif fmt.startswith("replace'", i):
            m = re.match(r"replace'([^']*)','([^']*)'", fmt[i:])
            if m:
                full = m.group(0)
                ops.append(full)
                i += len(full)
            else:
                i += 1

        # Strip characters: strip'chars'[, ...]
        elif fmt.startswith("strip'", i):
            m = re.match(r"strip'(.*?)'(?:,'(.*?)')*", fmt[i:])
            if m:
                all_matches = re.findall(r"'(.*?)'", fmt[i:])
                if all_matches:
                    op = "strip" + ",".join([f"'{s}'" for s in all_matches])
                    ops.append(op)
                    i += len(m.group(0))
                else:
                    i += 1
            else:
                i += 1

        # Date formatting: date'format'
        elif fmt.startswith("date'", i):
            m = re.match(r"date'([^']*)'", fmt[i:])
            if m:
                full = m.group(0)
                ops.append(full)
                i += len(full)
            else:
                i += 1

        
        elif fmt.startswith("join(", i):
            j = i
            while j < len(fmt) and fmt[j] != ')':
                j += 1
            j += 1  # include closing )
            op = fmt[i:j]
            ops.append(op)
            i = j


        # Default fallback: default('value')
        elif fmt.startswith("default(", i):
            j = i
            while j < len(fmt) and fmt[j] != ')':
                j += 1
            j += 1  # include closing )
            op = fmt[i:j]
            ops.append(op)
            i = j
            

        # Substring slicing: substr:start,end
        elif fmt.startswith("substr:", i):
            m = re.match(r"substr:(-?\d*),(-?\d*)", fmt[i:])
            if m:
                start, end = m.group(1), m.group(2)
                ops.append(f"substr:{start},{end}")
                i += len(m.group(0))
            else:
                i += 1

        # Simple ops: lower, upper, trim alias, etc.
        else:
            m = re.match(r"[a-zA-Z_]+", fmt[i:])
            if m:
                op = m.group(0).strip()
                if op:
                    # support alias
                    if op == 'trim':
                        ops.append('strip')
                    else:
                        ops.append(op)
                i += len(op)
            else:
                i += 1

        # Skip comma separators
        if i < len(fmt) and fmt[i] == ',':
            i += 1

    return ops




def apply_ops(val, ops, tag=None):
    for op in ops:
        if isinstance(op, list):
            val = apply_ops(val, op)

        elif op.startswith("strip'") and op.endswith("'"):
            # Support multiple values: strip'.mxf','_HD','_v1'
            args = re.findall(r"'(.*?)'", op)
            for s in args:
                before = val
                val = val.replace(s, '')
                logging.debug(f" Stripping '{s}' from '{before}' => '{val}'")

        elif op.startswith("replace'") and op.endswith("'"):
            try:
                match = re.match(r"replace'([^']*)','([^']*)'", op)
                if match:
                    from_str, to_str = match.groups()
                    before = val
                    val = val.replace(from_str, to_str)
                    logging.debug(f" Replacing '{from_str}' with '{to_str}' in '{before}' => '{val}'")
                else:
                    logging.debug(f" Malformed replace: {op}")
            except Exception as e:
                logging.debug(f" Replace error: {e}")

        elif op == "lower":
            before = val
            val = val.lower()
            logging.debug(f" Lower: '{before}' => '{val}'")

        elif op == "upper":
            before = val
            val = val.upper()
            logging.debug(f" Upper: '{before}' => '{val}'")

        elif op.startswith("date'") and op.endswith("'"):
            try:
                dt = date_parser.parse(val)
                val = dt.strftime(convert_to_strftime(op[5:-1]))
            except Exception as e:
                logging.debug(f" Date parse error: {e}")

        elif op.startswith("default(") and op.endswith(")"):
            default_val = op[8:-1]
            if not val.strip():
                logging.debug(f" Default applied: '{default_val}' used instead of empty '{val}'")
                val = default_val

        elif op.startswith("substr:"):
            # syntax: substr:start,end
            params = op.split(":", 1)[1]
            start_str, end_str = params.split(",", 1)
            try:
                start = int(start_str) if start_str != "" else None
                end   = int(end_str)   if end_str   != "" else None
                before = val
                val = val[start:end]
                logging.debug(f" Substr '{start_str},{end_str}' on '{before}' => '{val}'")
            except ValueError:
                logging.debug(f" Invalid substr parameters: {op}")

                # if parsing fails, leave val unchanged or raise your own error
                pass

    logging.debug(f" Final value: {val}")
    return val



def get_value(data, path_with_format):
    if '::' in path_with_format:
        path, fmt = path_with_format.split('::', 1)
        fmt_ops = parse_format_ops(fmt)
    else:
        path, fmt_ops = path_with_format, []

    # Drill down into the JSON
    keys = path.split('.')
    val = data
    for k in keys:
        if isinstance(val, dict) and k in val:
            val = val[k]
        else:
            return ''

    # Flatten lists and dicts
    if isinstance(val, list):
        # Check for join op in fmt_ops
        join_op = next((op for op in fmt_ops if isinstance(op, str) and op.startswith("join(") and op.endswith(")")), None)
        if join_op:
            sep = join_op[5:-1]  # extract separator
            fmt_ops = [op for op in fmt_ops if op != join_op]  # remove it from list
        else:
            sep = ', '
        val = sep.join(str(v) for v in val if v)

    val = str(val)

    # — Extract only the string-based substr ops —
    substr_ops = [
        op for op in fmt_ops
        if isinstance(op, str) and op.startswith("substr:")
    ]
    # Remove them from fmt_ops so apply_ops won’t see them
    fmt_ops = [
        op for op in fmt_ops
        if not (isinstance(op, str) and op.startswith("substr:"))
    ]

    # Apply each substr:start,end immediately
    for op in substr_ops:
        params = op.split(":", 1)[1]
        start_str, end_str = params.split(",", 1)
        try:
            start = int(start_str) if start_str != "" else None
            end   = int(end_str)   if end_str   != "" else None
            val_before = val
            val = val[start:end]
            logging.debug(f" Substr '{start_str},{end_str}' on '{val_before}' => '{val}'")
        except ValueError:
            logging.warning(f"Invalid substr parameters: {op}")

    # Now hand off the rest of the ops (strip, replace, lower, upper, date, etc.)
    return apply_ops(val, fmt_ops)




def convert_to_strftime(fmt):
    replacements = {
        'YYYY': '%Y',
        'YY': '%y',
        'MMMM': '%B',
        'MMM': '%b',
        'MM': '%m',   # Month
        'M': '%#m' if platform.system() == 'Windows' else '%-m',  # Single-digit day fix
        'DD': '%d',
        'D': '%#d' if platform.system() == 'Windows' else '%-d',  # Single-digit day fix
        'HH': '%H',
        'mm': '%M',   # Minute
        'SS': '%S',
    }
    for k, v in replacements.items():
        fmt = fmt.replace(k, v)
    return fmt

def build_elements(mapping, data):
    elements = []
    for tag, spec in mapping.items():
        if isinstance(spec, str):
            value = get_value(data, spec)
            logging.debug(f" Tag: {tag}, Raw Spec: {spec}, Result: {value}")
            elem = ET.Element(tag)
            if value:
                elem.text = value
            elements.append(elem)
        elif isinstance(spec, dict):
            parent = ET.Element(tag)
            for child in build_elements(spec, data):
                parent.append(child)
            elements.append(parent)
        elif isinstance(spec, list):
            loop_path = spec[0].get('_for', '')
            items = get_value(data, loop_path)
            try:
                items = json.loads(items) if isinstance(items, str) else items
            except (ValueError, TypeError):
                items = []
            for item in items or []:
                nested_map = {k: v for k, v in spec[0].items() if k != '_for'}
                parent = ET.Element(tag)
                for child in build_elements(nested_map, item):
                    parent.append(child)
                elements.append(parent)
        else:
            raise ValueError(f"Unsupported mapping type for tag '{tag}': {type(spec)}")
    return elements

def process_mapping_file(config, data, outpath, root_tag=None):
    mapping = load_mapping_config(config)
    if root_tag:
        root = ET.Element(root_tag)
        for e in build_elements(mapping, data):
            root.append(e)
    else:
        if len(mapping) == 1:
            key = next(iter(mapping))
            root = ET.Element(key)
            for e in build_elements(mapping[key], data):
                root.append(e)
        else:
            root = ET.Element('root')
            for e in build_elements(mapping, data):
                root.append(e)
    tree = ET.ElementTree(root)
    tree.write(outpath, encoding='utf-8', xml_declaration=True)

def process_template_file(template_text, data, outpath):
    def repl(match):
        path = match.group(1)
        return get_value(data, path)
    result = re.sub(r"%([^%]+)%", repl, template_text)
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(result)

def process_file(infile, args, template_text=None):
    data = load_json_with_retry(infile)
    basename = os.path.splitext(os.path.basename(infile))[0] + '.xml'
    outpath = os.path.join(args.output_dir, basename)
    if template_text is not None:
        process_template_file(template_text, data, outpath)
    else:
        process_mapping_file(args.config, data, outpath, args.root)
    logging.info(f"Wrote {outpath}")

    # Delete input file if setting is enabled
    if getattr(args, 'delete_input', False):
        try:
            os.remove(infile)
            logging.info(f"Deleted input file: {infile}")
        except Exception as e:
            logging.warning(f"Failed to delete input file {infile}: {e}")



# ----------------------- Watchdog Handler ----------------------------

class JSONEventHandler(FileSystemEventHandler):
    def __init__(self, args, template_text, update_callback=None):
        super().__init__()
        self.args = args
        self.template_text = template_text
        self.last_mtime = {}
        self.update_callback = update_callback

    def _should_process(self, path):
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return False
        last = self.last_mtime.get(path)
        # Allow reprocessing if difference is at least 1 second
        if last is None or abs(mtime - last) >= 1:
            self.last_mtime[path] = mtime
            return True
        return False


    def _handle_event(self, src_path):
        time.sleep(0.5)
        if self._should_process(src_path):
            process_file(src_path, self.args, self.template_text)
            if self.update_callback:
                self.update_callback(src_path)

    def on_created(self, event):
        if not event.is_directory and event.src_path.lower().endswith('.json'):
            self._handle_event(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and event.src_path.lower().endswith('.json'):
            self._handle_event(event.src_path)


# ----------------------- GUI Mode ----------------------------

def run_gui():
    import threading
    import sv_ttk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText

    root = tk.Tk()
    root.title("JSON to XML Watcher")
    sv_ttk.set_theme("light")
    root.geometry("800x500")

    # Defaults
    default_settings_path = get_resource_path('settings.json')
    default_template_path = get_resource_path('template.xml')

    config_var = tk.StringVar(value=default_template_path if os.path.exists(default_template_path) else '')
    settings_var = tk.StringVar(value=default_settings_path if os.path.exists(default_settings_path) else '')
    last_file_var = tk.StringVar(value="No files processed yet")
    start_on_startup_flag = False

    observer = None
    is_watching = tk.BooleanVar(value=False)

    # Callback to update last processed file label
    def on_file(path):
        basename = os.path.basename(path)
        root.after(0, lambda: last_file_var.set(f"Last processed: {basename}"))

    # Top frame for controls
    top_frame = ttk.Frame(root)
    top_frame.pack(side=tk.TOP, fill=tk.X, pady=10)

    ttk.Label(top_frame, textvariable=last_file_var, wraplength=600).pack(anchor='center', pady=(0, 8))

    watch_btn = ttk.Button(top_frame, text="Start Watching", style="Accent.TButton")
    watch_btn.pack(anchor='center')

    # Bottom frame for log
    bottom_frame = ttk.Frame(root)
    bottom_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(10, 10))

    ttk.Label(bottom_frame, text="Log Output:").pack(anchor='w')

    log_text = ScrolledText(bottom_frame, height=15, width=100, state='disabled', wrap='word')
    log_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    first_log_load = True


    def update_log_display():
        nonlocal first_log_load
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            log_path = os.path.join(LOG_DIR, f"{today}.log")
            if os.path.exists(log_path):
                current_scroll_pos = log_text.yview()

                with open(log_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                log_text.config(state='normal')
                log_text.delete('1.0', tk.END)
                log_text.insert(tk.END, content)

                # On first load: force scroll to bottom
                if first_log_load:
                    log_text.see(tk.END)
                    first_log_load = False
                else:
                    # Preserve scroll position unless user was already at bottom
                    log_text.yview_moveto(current_scroll_pos[0])
                    if current_scroll_pos[1] >= 0.99:
                        log_text.see(tk.END)

                log_text.config(state='disabled')
        except Exception as e:
            log_text.config(state='normal')
            log_text.delete('1.0', tk.END)
            log_text.insert(tk.END, f"Error loading log: {e}")
            log_text.config(state='disabled')

        root.after(3000, update_log_display)  # refresh every 3 seconds


    def toggle_watch(auto_start=False):
        nonlocal observer

        if is_watching.get():
            # Stop watching
            if observer:
                observer.stop()
                observer.join()
                observer = None
            is_watching.set(False)
            watch_btn.config(text="Start Watching")
        else:
            # Start watching
            args = argparse.Namespace()
            args.config = config_var.get()
            args.root = None
            args.watch = True
            args.input_dir = ""
            args.output_dir = ""

            settings_file = settings_var.get()
            if os.path.exists(settings_file):
                try:
                    with open(settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                        args.input_dir = settings.get('input_dir', '')
                        args.output_dir = settings.get('output_dir', '')
                        args.delete_input = settings.get('delete_input', False)
                        nonlocal start_on_startup_flag
                        start_on_startup_flag = settings.get('start_on_startup', False)
                except Exception as e:
                    if not auto_start:
                        messagebox.showerror("Error", f"Failed to load settings file:\n{e}")
                    return
            else:
                args.input_dir = filedialog.askdirectory(title="Select Input Directory")
                args.output_dir = filedialog.askdirectory(title="Select Output Directory")

            if not args.input_dir or not args.output_dir:
                if not auto_start:
                    messagebox.showwarning("Missing paths", "Input and Output directories are required.")
                return

            is_template = args.config.lower().endswith('.xml')
            template_text = load_template(args.config) if is_template else None

            def observer_loop():
                nonlocal observer
                handler = JSONEventHandler(args, template_text, update_callback=on_file)

                while is_watching.get():
                    if is_directory_available(args.input_dir) and is_directory_available(args.output_dir):
                        if observer is None or not observer.is_alive():
                            observer = Observer()
                            observer.schedule(handler, args.input_dir, recursive=False)
                            observer.start()
                            logging.info("Observer started.")
                    else:
                        if observer:
                            observer.stop()
                            observer.join()
                            observer = None
                            logging.warning("Directory unavailable. Observer stopped.")
                    time.sleep(5)

            threading.Thread(target=observer_loop, daemon=True).start()
            is_watching.set(True)
            watch_btn.config(text="Stop Watching")


    watch_btn.config(command=toggle_watch)

    # Auto-start if configured
    if os.path.exists(default_settings_path):
        try:
            with open(default_settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                if settings.get("start_on_startup", False):
                    root.after(100, lambda: toggle_watch(auto_start=True))
        except Exception:
            pass

    def on_close():
        if observer:
            observer.stop()
            observer.join()
        root.destroy()

    update_log_display()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.iconbitmap('./icon.ico')
    root.mainloop()

# ----------------------- Main Entry ----------------------------

    
def main():
    import sys

    # Redirect stdout/stderr to log file
    if not sys.stdout or not sys.stdout.isatty():
        log_path = os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), 'cli_output.log')
        sys.stdout = open(log_path, 'w', encoding='utf-8')
        sys.stderr = sys.stdout
        print(f"[INFO] Output redirected to {log_path}")

    if len(sys.argv) == 1:
        # No arguments → launch GUI
        run_gui()
        return

    # Proceed with CLI mode
    parser = argparse.ArgumentParser(
        description='Convert JSON to XML via mapping/template, with optional watch.'
    )
    parser.add_argument('config', nargs='?', help='Mapping (JSON/YAML) or template (XML)')
    parser.add_argument('--settings', help='Optional JSON file with input/output directory settings')
    parser.add_argument('--input-dir', help='Directory with JSON files')
    parser.add_argument('--output-dir', help='Directory for XML output')
    parser.add_argument('--root', help='Optional root tag for mapping mode', default=None)
    parser.add_argument('--watch', action='store_true', help='Watch input directory for changes')
    parser.add_argument('--delete-input', action='store_true', help='Delete input files after successful processing')
    parser.add_argument('--help-only', action='store_true', help='Show this help and exit')

    args = parser.parse_args()

    if args.help_only or not args.config:
        parser.print_help()
        return

    is_template = args.config.lower().endswith('.xml')
    template_text = load_template(args.config) if is_template else None

    if args.settings:
        try:
            with open(args.settings, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                args.input_dir = settings.get('input_dir', args.input_dir)
                args.output_dir = settings.get('output_dir', args.output_dir)
                args.delete_input = settings.get('delete_input', getattr(args, 'delete_input', False))
        except Exception as e:
            print(f"Failed to load settings file: {e}")
            return

    if args.watch:
        if not _HAS_WATCHDOG:
            print("Error: watchdog not installed. Use 'pip install watchdog'")
            return

        print(f"Watching {args.input_dir} for JSON changes (with auto-recovery)...")
        handler = JSONEventHandler(args, template_text)
        observer = None

        try:
            while True:
                if is_directory_available(args.input_dir) and is_directory_available(args.output_dir):
                    if observer is None or not observer.is_alive():
                        observer = Observer()
                        observer.schedule(handler, args.input_dir, recursive=False)
                        observer.start()
                        logging.info("Observer started in CLI mode.")
                else:
                    if observer:
                        observer.stop()
                        observer.join()
                        observer = None
                        logging.warning("Directory unavailable. Observer stopped in CLI mode.")

                time.sleep(5)

        except KeyboardInterrupt:
            if observer:
                observer.stop()
                observer.join()
    else:
        if not args.input_dir or not args.output_dir:
            print("Input and output directories are required.")
            return
        json_files = glob.glob(os.path.join(args.input_dir, '*.json'))
        if not json_files:
            print(f"No JSON files found in {args.input_dir}")
            return
        os.makedirs(args.output_dir, exist_ok=True)
        for infile in json_files:
            process_file(infile, args, template_text)

    print("[DONE] Processing finished.")


if __name__ == '__main__':
    main()
