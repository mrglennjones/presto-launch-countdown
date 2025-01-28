import gc
import sdcard
import machine
import plasma  # LED control
import math    # Smooth effects
import uos
import urequests
import jpegdec
import pngdec  # PNG decoder for PicoGraphics
from presto import Presto
import network
import secrets
import utime
import re
from picovector import PicoVector, Transform, ANTIALIAS_FAST


#DEBUG_MODE = True  # Start with debug mode enabled
# 🔥 Global variables to keep animation smooth
nebula_step = 0  # Keep track of nebula animation state


# 📟 Terminal-Style Boot Log
BOOT_LOG = []  # Store boot log messages
MAX_LOG_LINES = 8  # Maximum lines to keep on screen
LOG_WRAP_WIDTH = 420  # Adjust for actual screen width
LOG_LINE_HEIGHT = 20  # Spacing between lines

def insert_soft_breaks(text, max_width):
    """Inserts soft breaks in long words (filenames, URLs) if they exceed max width."""
    if int(vector.measure_text(text)[2]) < max_width:
        return [text]  # ✅ Already fits, return as a single line

    broken_text = []
    for i in range(0, len(text), 50):  # ✅ Insert break every 10 characters
        broken_text.append(text[i:i+50])

    return broken_text  # ✅ Return list of broken parts

def wrap_text(text, max_width):
    """Wraps text into multiple lines while handling long words (URLs, filenames)."""
    words = text.split(" ")  # Split into words
    wrapped_lines = []
    current_line = ""

    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        text_width = int(vector.measure_text(test_line)[2])  # Measure pixel width

        if text_width < max_width:
            current_line = test_line  # ✅ Add word to current line
        else:
            if current_line:
                wrapped_lines.append(current_line)  # ✅ Store full line
            wrapped_lines.extend(insert_soft_breaks(word, max_width))  # ✅ Add broken word parts
            current_line = ""

    if current_line:
        wrapped_lines.append(current_line)  # ✅ Store last line

    return wrapped_lines  # ✅ Returns a full list of wrapped lines

TERMINAL_MODE = True

# A global flag to indicate whether we still want on-screen terminal logs.
TERMINAL_MODE = True

def boot_log(category, message):
    """Logs and (optionally) displays a message on the Presto screen."""
    global BOOT_LOG, TERMINAL_MODE

    log_message = f"[{category}] {message}"
    print(log_message)  # Always print to console

    # If we've switched to final UI mode, skip redrawing the log text
    if not TERMINAL_MODE:
        return

    # Otherwise, do the usual wrap/clear/draw routine
    wrapped_lines = wrap_text(log_message, LOG_WRAP_WIDTH)
    for line in wrapped_lines:
        BOOT_LOG.append(line)

    while len(BOOT_LOG) > MAX_LOG_LINES:
        BOOT_LOG.pop(0)

    display.set_pen(BLACK)
    display.clear()
    y_offset = 15
    vector.set_font("Roboto-Medium.af", 18)

    for log_line in BOOT_LOG:
        display.set_pen(GREEN)
        vector.text(log_line, 10, y_offset)
        y_offset += LOG_LINE_HEIGHT

    presto.update()
    utime.sleep(0.1)





# 🛠️ Initialize backlight LEDs
NUM_LEDS = 7  # Presto has 7 LEDs
bl = plasma.WS2812(NUM_LEDS, 0, 0, 33)
bl.start()

# 🌌 Define nebula colors for smooth blending
NEBULA_COLORS = [
    (148, 0, 211),  # Dark Violet
    (75, 0, 130),   # Indigo
    (0, 0, 255),    # Deep Blue
    (0, 255, 255),  # Cyan
    (255, 20, 147), # Deep Pink
    (255, 69, 0),   # Orange-Red
    (128, 0, 128)   # Purple
]

# **🔥 Smoothly transition between two colors using Linear Interpolation (LERP)**
def lerp_color(color1, color2, t):
    r1, g1, b1 = color1
    r2, g2, b2 = color2
    return (
        int(r1 + (r2 - r1) * t),
        int(g1 + (g2 - g1) * t),
        int(b1 + (b2 - b1) * t),
    )

# 🌌 **Idle Nebula Effect**
def update_nebula_color():
    global nebula_step
    
    nebula_speed = 0.02

    for i in range(NUM_LEDS):
        # 1) Compute a *float* index, e.g. 3.25 means 25% of the way from color[3] to color[4]
        idx_float = (nebula_step + i) % len(NEBULA_COLORS)
        
        # 2) Separate into integer + fractional
        idx_int = int(idx_float)  # e.g. 3
        alpha   = idx_float - idx_int  # e.g. 0.25
        
        # 3) Identify the “next” color index
        next_idx = (idx_int + 1) % len(NEBULA_COLORS)
        
        # 4) LERP between NEBULA_COLORS[idx_int] and NEBULA_COLORS[next_idx]
        c1 = NEBULA_COLORS[idx_int]
        c2 = NEBULA_COLORS[next_idx]
        
        r1, g1, b1 = c1
        r2, g2, b2 = c2
        
        # Linear interpolation
        r = int(r1 + (r2 - r1) * alpha)
        g = int(g1 + (g2 - g1) * alpha)
        b = int(b1 + (b2 - b1) * alpha)
        
        # 5) Optionally apply the sine-wave brightness factor like before
        brightness = 0.5 + 0.5 * math.sin(nebula_step + (i * 0.5))
        r = int(r * brightness)
        g = int(g * brightness)
        b = int(b * brightness)
        
        # 6) Set the LED color
        bl.set_rgb(i, r, g, b)

    # 7) Increment step for next frame
    nebula_step += nebula_speed



# 🖥️ Initialize Presto in FULL resolution mode (480x480)
#presto = Presto(ambient_light=False, full_res=True)
presto = Presto(ambient_light=False, full_res=True, layers=2)
display = presto.display

display.set_layer(0)
# Clear layer 0, decode, etc.

display.set_layer(1)
# decode again, etc.

WIDTH, HEIGHT = display.get_bounds()
jpeg = jpegdec.JPEG(display)
vector = PicoVector(display)

def setup_sd():
    boot_log("DISK", "💾 Initializing SD Card...")
    try:
        sd_spi = machine.SPI(0, sck=machine.Pin(34), mosi=machine.Pin(35), miso=machine.Pin(36))
        sd = sdcard.SDCard(sd_spi, machine.Pin(39))
        uos.mount(sd, "/sd")

        if "gallery" not in uos.listdir("/sd"):
            uos.mkdir(SD_DIR)

        boot_log("DISK", "✅ SD Card Mounted Successfully!")
        return True
    except Exception as e:
        boot_log("DISK", f"🚨 SD Mount Error: {e}")
        return False


# 📂 SD Card Directory for Images
SD_DIR = "/sd/gallery"

# 🎨 Colors
WHITE = display.create_pen(255, 255, 255)
BLACK = display.create_pen(0, 0, 0)
DARKGREY = display.create_pen(70, 70, 70)
DARKERGREY = display.create_pen(30, 30, 30)
GREEN = display.create_pen(0, 200, 0)

# 🎨 Set up Vector Font
vector.set_antialiasing(ANTIALIAS_FAST)
vector.set_font("Roboto-Medium.af", 22)
transform = Transform()
vector.set_transform(transform)

# 🔄 **Convert Unix timestamp to ISO 8601 format**
def unix_to_iso8601(timestamp):
    """Converts Unix timestamp to ISO 8601 (UTC) format."""
    time_tuple = utime.localtime(timestamp)
    return f"{time_tuple[0]:04d}-{time_tuple[1]:02d}-{time_tuple[2]:02d}T{time_tuple[3]:02d}:{time_tuple[4]:02d}:{time_tuple[5]:02d}Z"


# 📡 **Connect to Wi-Fi**
def connect_wifi():
    boot_log("WEB", "🌐 Connecting to Wi-Fi...")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
    timeout = 20  # Increase timeout for reliability

    while not wlan.isconnected() and timeout > 0:
        utime.sleep(1)
        timeout -= 1

    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        boot_log("WEB", f"✅ Connected to Wi-Fi: {ip}")
    else:
        boot_log("WEB", "🚨 Failed to connect to Wi-Fi! Retrying...")
        utime.sleep(5)
        return connect_wifi()  # Retry connection


# 🗑️ **Delete all previous images from SD card**
def clear_images():
    try:
        for file in uos.listdir(SD_DIR):
            filepath = f"{SD_DIR}/{file}"
            uos.remove(filepath)
            print(f"🗑️ Deleted: {filepath}")
        print("✅ Old Images Cleared!")
    except OSError as e:
        print(f"🚨 Error Clearing Images: {e}")
    gc.collect()


def clean_filename(name, extension):
    """Ensures a valid filename while preserving its exact extension."""
    if not isinstance(name, str) or not isinstance(extension, str):
        boot_log("ERROR", f"❌ Invalid filename input types: {type(name)}, {type(extension)}")
        return "default_image.jpg"  # ✅ Fallback filename

    # ✅ Ensure only valid characters in the filename
    name = re.sub(r"[^a-zA-Z0-9_.-]", "_", name)

    # ✅ Keep the extension exactly as it is (no forced conversion)
    filename = f"{name[:150]}.{extension}"  # ✅ Preserve original extension

    boot_log("DISK", f"🔍 DEBUG: Clean Filename -> {filename}, Type: {type(filename)}")
    return filename  # ✅ Always return a clean string



def download_image(url):
    """Downloads an image from the provided URL while preserving its original extension."""
    try:
        # ✅ Ensure URL is valid
        if not isinstance(url, str) or not url.startswith("http"):
            boot_log("ERROR", f"❌ Invalid image URL: {url}")
            return None

        # ✅ Extract the filename and extension properly
        filename = url.split("/")[-1]  # Last part of URL
        if "." in filename:
            extension = filename.split(".")[-1]  # ✅ Preserve exact extension
        else:
            boot_log("ERROR", f"❌ No valid extension found in: {url}")
            return None

        # ✅ Clean filename while keeping the exact extension
        filename = clean_filename(filename.split(".")[0], extension)  
        filepath = f"{SD_DIR}/{filename}"

        boot_log("WEB", f"📷 Downloading Image: {url} -> {filepath}")

        # ✅ Download the image
        response = urequests.get(url)
        if response.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(response.content)
            response.close()
            gc.collect()
            boot_log("DISK", f"✅ Image saved: {filepath}")
            return filepath  # ✅ Return path of the downloaded image
        else:
            boot_log("ERROR", f"❌ Image Download Error: {response.status_code}")
            response.close()
            return None
    except Exception as e:
        boot_log("ERROR", f"❌ Image Download Exception: {e}")
        return None


def fetch_and_process_launch(launch_data):
    """Fetches, processes, and prepares launch data for display."""

    display.set_pen(BLACK)
    display.clear()
    boot_log("UI", "🖥 Preparing Launch Display...")

    if not launch_data or "results" not in launch_data:
        boot_log("WEB", "🚨 No valid launch data received!")
        return

    launch = launch_data["results"][0]
    name = launch["name"]
    net = launch["net"]
    provider = launch["launch_service_provider"]["name"]
    location = launch["pad"]["location"]["name"]

    boot_log("DATA", f"🚀 Launch: {name}")
    boot_log("DATA", f"📅 Date: {net}")

    # **Extract and format date & time**
    try:
        date_iso = net.split("T")[0]
        time_iso = net.split("T")[1][:5]
        date_parts = date_iso.split("-")
        formatted_date = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"

        boot_log("DATA", f"⏳ Formatted Date: {formatted_date}")
    except Exception as e:
        boot_log("ERROR", f"❌ Date Parsing Error: {e}")
        return

    # **Convert launch time to Unix timestamp**
    try:
        date_time = net[:19]
        year, month, day = map(int, date_time.split("T")[0].split("-"))
        hour, minute, second = map(int, date_time.split("T")[1].split(":"))
        launch_time_unix = utime.mktime((year, month, day, hour, minute, second, 0, 0))

        boot_log("DATA", f"⏳ Launch Time (Unix): {launch_time_unix}")
    except Exception as e:
        boot_log("ERROR", f"❌ Launch Time Conversion Error: {e}")
        return

    # **Download Image**
    image_data = launch.get("image", {})
    image_url = image_data.get("thumbnail_url", None) if isinstance(image_data, dict) else None

    if image_url:
        boot_log("WEB", f"📷 Downloading Image: {image_url}")
        img_path = download_image(image_url)
    else:
        boot_log("WEB", "🚨 No Image URL Found!")
        img_path = None

    if isinstance(img_path, str):
        boot_log("UI", f"✅ Image Path Verified: {img_path}")
        #display_background(img_path)
        boot_log("UI", "✅ Image Downloaded Successfully")
    else:
        boot_log("ERROR", "❌ Image Load Failed!")

    # ✅ **Ensure Terminal is Fully Removed Here**
    global TERMINAL_MODE
    TERMINAL_MODE = False
    display_final_ui(name, formatted_date, time_iso, provider, location, img_path, launch_time_unix)



# 📡 **Fetch latest launch data**
def fetch_launch_data():
    boot_log("WEB", "🌍 Fetching Launch Data...")
    base_url = "https://ll.thespacedevs.com/2.3.0/launches/"
    now = utime.time()
    future = now + (180 * 24 * 60 * 60)  # 6 months ahead
    now_iso = unix_to_iso8601(now)
    future_iso = unix_to_iso8601(future)

    url = f"{base_url}?net__gte={now_iso}&net__lte={future_iso}&include_suborbital=true&mode=detailed&limit=1&ordering=net"

    try:
        response = urequests.get(url)
        if response.status_code == 200:
            boot_log("WEB", "✅ Launch data fetched successfully!")
            return response.json()
        else:
            boot_log("WEB", f"❌ API Error: {response.status_code}")
            return None
    except Exception as e:
        boot_log("WEB", f"🚨 Error Fetching Data: {e}")
        return None


import gc
import jpegdec
import pngdec

def display_background(image_path):
    """
    Displays a background image (JPEG or PNG) from the SD card.
    - Never stringifies any exceptions from jpegdec,
      so it cannot trigger "can't convert 'tuple' object to str".
    - Uses broad except blocks to gracefully handle unknown errors.
    """

    # (1) Basic validations for the path
    if not isinstance(image_path, str):
        boot_log("ERROR", "❌ Invalid image path (not a string).")
        return

    file_name = image_path.strip().split("/")[-1]
    if file_name not in uos.listdir(SD_DIR):
        boot_log("ERROR", "❌ Image file not found on SD.")
        return

    # (2) Clear the screen and free memory before decode
    display.set_pen(0)
    display.clear()
    gc.collect()

    # (Optional) Log we’re starting
    boot_log("UI", f"✅ Attempting to display: {file_name}")

    try:
        # ---------- Handle PNG ----------
        if image_path.lower().endswith(".png"):
            local_png = pngdec.PNG(display)
            local_png.open_file(image_path)

            # Original width & height
            w = local_png.get_width()
            h = local_png.get_height()

            # We're scaling up by 2, so the final displayed size will be w*2 x h*2.
            scaled_w = w * 2
            scaled_h = h * 2

            # Center based on scaled dimensions
            center_x = (WIDTH - scaled_w) // 2
            center_y = (HEIGHT - scaled_h) // 2

            # Decode at 2× scale, so it fills more of the screen
            local_png.decode(center_x, center_y, scale=2)

        # ---------- Handle JPEG/JPG ----------
        elif image_path.lower().endswith((".jpg", ".jpeg")):
            local_jpeg = jpegdec.JPEG(display)
            local_jpeg.open_file(image_path)

            w, h = local_jpeg.get_width(), local_jpeg.get_height()
            center_x = (WIDTH - w) // 2
            center_y = (HEIGHT - h) // 2

            # If memory is tight, consider half-scale:
            # local_jpeg.decode(center_x, center_y, jpegdec.JPEG_SCALE_HALF, dither=False)
            local_jpeg.decode(center_x, center_y, jpegdec.JPEG_SCALE_FULL, dither=True)

        else:
            boot_log("ERROR", "❌ Unsupported image format.")
            return

        # (3) Final display update
        presto.update()
        boot_log("UI", "✅ Image displayed successfully.")

    # ------------ Exceptions Without Stringifying 'e' ------------
    except OSError:
        # Matches Pimoroni's example approach
        boot_log("ERROR", "❌ OSError while opening or decoding the image.")
    except MemoryError:
        # Common on large images in 480×480 mode
        boot_log("ERROR", "❌ MemoryError! Try smaller images or half-scale decode.")
    except:
        # Catch-all for anything else (including if jpegdec returned a tuple)
        boot_log("ERROR", "❌ Unknown error while decoding the image.")




# 📡 **Countdown Timer + LED Effects**
#nebula_step = 0  # ✅ Keep this outside so it persists

def display_countdown(launch_time):
    """Displays countdown timer with formatted labels and animation effects."""
    global nebula_step  # ✅ Keep nebula animation continuous

    # ✅ **Clear Terminal Before Starting Countdown**
    global BOOT_LOG
    BOOT_LOG.clear()  # ✅ Remove all previous log messages
    presto.update()   # ✅ Ensure screen clears

    # **Font Sizes**
    vector.set_font("Roboto-Medium.af", 35)  # ✅ Large countdown font
    label_font_size = 18  # ✅ Smaller font for labels

    # **Measure Text Widths**
    t_dash_width = int(vector.measure_text("T-")[2])
    num_widths = [int(vector.measure_text("00")[2]) for _ in range(4)]
    colon_width = int(vector.measure_text(":")[2])

    # **Calculate Total Countdown Width**
    x_offset = -22
    total_countdown_width = t_dash_width + sum(num_widths) + (colon_width * 3) + (15 * 4)
    countdown_x_start = int((WIDTH - total_countdown_width) // 2) + x_offset
    text_y = int(HEIGHT // 2 - 30)
    label_y = text_y + 30

    pulse_step = 0  # ✅ Keep pulse effect local (resets each countdown)
    # ❌ REMOVE: `nebula_step = 0` (this is the cause of reset!)

    while utime.time() < launch_time:
        now = utime.time()
        remaining_seconds = int(launch_time - now)

        if remaining_seconds <= 0:
            boot_log("TIMER", "🎉 Countdown Reached Zero! Fetching New Data...")
            return True  # Restart process

        # ✅ Do NOT clear the entire screen, only update the countdown section
        display.set_pen(DARKERGREY)
        display.rectangle(countdown_x_start - 10, text_y - 35, total_countdown_width + 70, 80)

        # **Draw "T-" Prefix**
        vector.set_font("Roboto-Medium.af", 35)
        display.set_pen(WHITE)
        current_x = countdown_x_start
        vector.text("T-", current_x, text_y)
        current_x += t_dash_width + 15

        # **Calculate Time Left**
        days = remaining_seconds // 86400
        hours = (remaining_seconds % 86400) // 3600
        minutes = (remaining_seconds % 3600) // 60
        seconds = remaining_seconds % 60
        countdown_numbers = [f"{days:02}", f"{hours:02}", f"{minutes:02}", f"{seconds:02}"]
        labels = ["DAYS", "HOURS", "MINS", "SECS"]

        # **Draw Numbers & Colons**
        for i in range(4):
            vector.text(countdown_numbers[i], current_x, text_y)
            current_x += num_widths[i] + 15
            if i < 3:
                vector.text(":", current_x, text_y)
                current_x += colon_width + 15

        # **Draw Labels Under Numbers**
        vector.set_font("Roboto-Medium.af", label_font_size)
        display.set_pen(DARKGREY)
        current_x = countdown_x_start + t_dash_width + 15
        for i in range(4):
            num_width = num_widths[i]
            label_width = int(vector.measure_text(labels[i])[2])
            label_x = int(current_x + (num_width // 2) - (label_width // 2))
            vector.text(labels[i], label_x, label_y)
            current_x += num_width + 15
            if i < 3:
                current_x += colon_width + 15

        # 🚨 **Red Pulse if < 30 mins**
        if remaining_seconds < 1800:
            pulse_intensity = int(200 + 55 * math.sin(pulse_step))
            red_intensity = int(100 + 100 * math.sin(pulse_step))
            for i in range(NUM_LEDS):
                bl.set_rgb(i, red_intensity, 0, 0)
            pulse_step += 0.1
        else:
            # 🌌 **Nebula LED Effect (Continuous Blend)**
            for i in range(NUM_LEDS):
                color_index = int((nebula_step + i) % len(NEBULA_COLORS))
                bl.set_rgb(i, *NEBULA_COLORS[color_index])
            
            nebula_step += 0.02  # ✅ Smoothly increment without resetting

        # 🔄 **Update Display**
        presto.update()
        utime.sleep(1)

    return True  # Countdown complete



def display_launch_info(name, date, time, provider, location):
    """Displays the launch details on the screen."""
    text_lines = [
        {"text": f"🚀 {name}", "size": 30},
        {"text": f"📅 {date}", "size": 30},
        {"text": f"🕒 {time} GMT", "size": 30},
        {"text": f"🏢 {provider}", "size": 20},
        {"text": f"📍 {location}", "size": 20},
    ]

    text_y = HEIGHT - 120
    spacing = 27

    for line in text_lines:
        vector.set_font("Roboto-Medium.af", line["size"])
        text_width = int(vector.measure_text(line["text"])[2])
        text_x = int((WIDTH - text_width) / 2) - 8  

        display.set_pen(BLACK)
        vector.text(line["text"], text_x + 2, text_y + 2)
        display.set_pen(WHITE)
        vector.text(line["text"], text_x, text_y)

        text_y += spacing
    presto.update()


def display_launch(launch_data):
    global DEBUG_MODE
    display.set_pen(BLACK)
    display.clear()
    presto.update()

    if not launch_data or "results" not in launch_data:
        boot_log("WEB", "🚨 No valid launch data received!")
        return

    launch = launch_data["results"][0]
    name = launch["name"]
    net = launch["net"]
    provider = launch["launch_service_provider"]["name"]
    location = launch["pad"]["location"]["name"]

    # ✅ Extract & Format Date
    date_iso = net.split("T")[0]
    time_iso = net.split("T")[1][:5]
    date_parts = date_iso.split("-")
    formatted_date = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"

    # ✅ Convert Launch Time to Unix Timestamp
    global launch_time_unix
    year, month, day = map(int, date_iso.split("-"))
    hour, minute = map(int, time_iso.split(":"))
    launch_time_unix = utime.mktime((year, month, day, hour, minute, 0, 0, 0))

    # ✅ Download Image
    image_data = launch.get("image", {})
    image_url = image_data.get("thumbnail_url", None) if isinstance(image_data, dict) else None
    img_path = download_image(image_url) if image_url else None

    # ✅ FINAL UI: Disable Debug Mode and Show All Elements
    DEBUG_MODE = False  
    display_final_ui(name, formatted_date, time_iso, provider, location, img_path, launch_time_unix)



def display_final_ui(name, date, time, provider, location, image_path, launch_time):
    """Displays the final UI with launch details, image, and countdown."""

    # ✅ 1. CLEAR TERMINAL BEFORE SWITCHING TO FINAL UI
    global BOOT_LOG
    BOOT_LOG.clear()  # ✅ This ensures the terminal never reappears

    # ✅ 2. Render the Final UI
    if isinstance(image_path, str):
        display_background(image_path)

    display_launch_info(name, date, time, provider, location)  

    # ✅ 3. Start Countdown WITHOUT Erasing Other UI Elements
    display_countdown(launch_time)  # 🚀 Runs without printing "Countdown Started..."

    # ✅ 4. FINAL UPDATE (After Everything is Rendered)
    presto.update()




# 🛠️ Setup/Initialization
setup_sd()
connect_wifi()
clear_images()
gc.collect()

# Main loop
while True:
    # 1) Fetch new launch data
    boot_log("SYSTEM", "🔄 Fetching new launch data...")
    launch_data = fetch_launch_data()
    
    if launch_data:
        # 2) Process/Display the launch info
        fetch_and_process_launch(launch_data)
    else:
        boot_log("ERROR", "❌ Failed to fetch launch data!")
    
    # 3) **Rate-limit** by sleeping a total of 500 seconds 
    #    but in smaller chunks (e.g. 5 seconds * 100 = 500)
    for _ in range(100):
        update_nebula_color()  # keeps the LED animation flowing
        utime.sleep(5)

