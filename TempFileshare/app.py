import os
import random
import string
import time
import threading
from flask import Flask, request, send_file, render_template, abort, url_for
from werkzeug.utils import secure_filename
from pathlib import Path

app = Flask(__name__)

# --- Config with default values ---
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Get absolute path to uploads directory
UPLOAD_FOLDER_PATH = os.path.abspath(UPLOAD_FOLDER)

# Default values that can be changed manually
DEFAULT_MAX_FILE_SIZE = 25  # MB
DEFAULT_LINK_EXPIRY = 15    # minutes

# Initialize with defaults
MAX_FILE_SIZE_MB = DEFAULT_MAX_FILE_SIZE
LINK_EXPIRY_MINUTES = DEFAULT_LINK_EXPIRY

# Convert to appropriate units for Flask config
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_MB * 1024 * 1024
LINK_EXPIRY_SECONDS = LINK_EXPIRY_MINUTES * 60

# Store mapping: { random_id: {"path":..., "time":..., "expiry":..., "filename":...} }
file_links = {}

def generate_random_string(length=8):
    """Generate random ID for each file link"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

@app.errorhandler(413)
def file_too_large(e):
    return f"File is too large. Max limit is {MAX_FILE_SIZE_MB} MB.", 413

@app.route("/", methods=["GET", "POST"])
def upload():
    global MAX_FILE_SIZE_MB, LINK_EXPIRY_MINUTES, LINK_EXPIRY_SECONDS
    
    if request.method == "POST":
        # Check if settings are being updated
        if 'update_settings' in request.form:
            try:
                new_size = int(request.form.get('max_file_size', DEFAULT_MAX_FILE_SIZE))
                new_expiry = int(request.form.get('link_expiry', DEFAULT_LINK_EXPIRY))
                
                # Validate inputs
                if new_size < 1 or new_size > 100:  # Reasonable limits
                    return render_template("index.html", link=None, error="File size must be between 1 and 100 MB",
                                         max_file_size=MAX_FILE_SIZE_MB, 
                                         link_expiry=LINK_EXPIRY_MINUTES)
                
                if new_expiry < 1 or new_expiry > 1440:  # 24 hours max
                    return render_template("index.html", link=None, error="Expiry time must be between 1 and 1440 minutes",
                                         max_file_size=MAX_FILE_SIZE_MB, 
                                         link_expiry=LINK_EXPIRY_MINUTES)
                
                # Update settings
                MAX_FILE_SIZE_MB = new_size
                LINK_EXPIRY_MINUTES = new_expiry
                app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE_MB * 1024 * 1024
                LINK_EXPIRY_SECONDS = LINK_EXPIRY_MINUTES * 60
                
                return render_template("index.html", link=None, error=None, 
                                      max_file_size=MAX_FILE_SIZE_MB, 
                                      link_expiry=LINK_EXPIRY_MINUTES,
                                      settings_updated=True)
            
            except ValueError:
                return render_template("index.html", link=None, error="Invalid settings values",
                                     max_file_size=MAX_FILE_SIZE_MB, 
                                     link_expiry=LINK_EXPIRY_MINUTES)
        
        # Handle file upload
        if 'file' not in request.files:
            return render_template("index.html", link=None, error="No file selected", 
                                 max_file_size=MAX_FILE_SIZE_MB, 
                                 link_expiry=LINK_EXPIRY_MINUTES)

        file = request.files['file']
        if file.filename == "":
            return render_template("index.html", link=None, error="No file selected",
                                 max_file_size=MAX_FILE_SIZE_MB, 
                                 link_expiry=LINK_EXPIRY_MINUTES)

        # Get current expiry from form or use default
        current_expiry = int(request.form.get('link_expiry', LINK_EXPIRY_MINUTES))
        current_max_size = int(request.form.get('max_file_size', MAX_FILE_SIZE_MB))

        # Check file size
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)  # Reset file pointer
        
        if file_length > current_max_size * 1024 * 1024:
            return render_template("index.html", link=None, error=f"File is too large. Max limit is {current_max_size} MB.",
                                 max_file_size=MAX_FILE_SIZE_MB, 
                                 link_expiry=LINK_EXPIRY_MINUTES)

        # Save uploaded file with a secure filename
        filename = secure_filename(file.filename)
        unique_filename = f"{int(time.time())}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER_PATH, unique_filename)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Save the file
        try:
            file.save(filepath)
            print(f"File saved successfully at: {filepath}")  # Debug print
            print(f"File exists: {os.path.exists(filepath)}")  # Debug print
        except Exception as e:
            print(f"Error saving file: {e}")
            return render_template("index.html", link=None, error=f"Error saving file: {e}",
                                 max_file_size=MAX_FILE_SIZE_MB, 
                                 link_expiry=LINK_EXPIRY_MINUTES)

        # Generate random link ID
        random_id = generate_random_string()
        file_links[random_id] = {
            "path": filepath,
            "time": time.time(),
            "expiry": current_expiry * 60,  # Convert minutes to seconds
            "filename": filename  # Store original filename for download
        }

        # Use url_for to generate the correct URL
        share_link = url_for('download', random_id=random_id, _external=True)
        
        # Render the same page but with the link
        return render_template("index.html", link=share_link, error=None,
                             max_file_size=MAX_FILE_SIZE_MB, 
                             link_expiry=LINK_EXPIRY_MINUTES,
                             file_expiry=current_expiry)

    # GET request: just show the page without a link
    return render_template("index.html", link=None, error=None,
                         max_file_size=MAX_FILE_SIZE_MB, 
                         link_expiry=LINK_EXPIRY_MINUTES)

@app.route("/download/<random_id>")
def download(random_id):
    """Serve the file if link is still valid"""
    file_info = file_links.get(random_id)
    if not file_info:
        return "Invalid or expired link", 404

    # Check if link has expired using the individual file's expiry time
    if time.time() - file_info["time"] > file_info["expiry"]:
        # Clean up expired file
        try:
            if os.path.exists(file_info["path"]):
                os.remove(file_info["path"])
        except FileNotFoundError:
            pass  # File already deleted
        del file_links[random_id]
        return "Link has expired", 410  # 410 Gone

    # Check if file exists before trying to send it
    if not os.path.exists(file_info["path"]):
        print(f"File not found at: {file_info['path']}")  # Debug print
        # Remove the invalid entry
        del file_links[random_id]
        return "File not found", 404

    print(f"Serving file from: {file_info['path']}")  # Debug print
    
    # Send the file with the original filename
    try:
        return send_file(
            file_info["path"], 
            as_attachment=True, 
            download_name=file_info["filename"],
            mimetype='application/octet-stream'  # Explicit mimetype
        )
    except Exception as e:
        print(f"Error sending file: {e}")
        return f"Error downloading file: {e}", 500

# --- Background cleaner thread ---
def cleanup_expired_files():
    """Periodically remove files older than their individual expiry time"""
    while True:
        now = time.time()
        expired_keys = []
        for key, info in list(file_links.items()):
            if now - info["time"] > info["expiry"]:
                # Delete the file
                try:
                    if os.path.exists(info["path"]):
                        os.remove(info["path"])
                except FileNotFoundError:
                    pass  # File already deleted
                expired_keys.append(key)

        # Remove expired entries
        for key in expired_keys:
            try:
                del file_links[key]
            except KeyError:
                pass  # Entry already removed

        time.sleep(60)  # Check every 60 seconds

# Start background thread for cleaning expired files
threading.Thread(target=cleanup_expired_files, daemon=True).start()

if __name__ == "__main__":
    print(f"Upload folder path: {UPLOAD_FOLDER_PATH}")
    app.run(debug=True)