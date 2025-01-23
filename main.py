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
def nebula_idle_effect():
    nebula_step = 0
    nebula_speed = 0.02

    while True:
        for i in range(NUM_LEDS):
            color_index = int((nebula_step + i) % len(NEBULA_COLORS))
            r, g, b = NEBULA_COLORS[color_index]

            # Apply a sine wave brightness effect for smooth blending
            brightness_factor = 0.5 + 0.5 * math.sin(nebula_step + (i * 0.5))
            r = int(r * brightness_factor)
            g = int(g * brightness_factor)
            b = int(b * brightness_factor)

            bl.set_rgb(i, r, g, b)  # Set LED color
        
        nebula_step += nebula_speed
        utime.sleep(0.05)  # Smooth update interval

# 🖥️ Initialize Presto in FULL resolution mode (480x480)
presto = Presto(ambient_light=False, full_res=True, layers=1)
display = presto.display
WIDTH, HEIGHT = display.get_bounds()
jpeg = jpegdec.JPEG(display)
vector = PicoVector(display)

# 📂 SD Card Directory for Images
SD_DIR = "/sd/gallery"

# 🎨 Colors
WHITE = display.create_pen(255, 255, 255)
BLACK = display.create_pen(0, 0, 0)
DARKGREY = display.create_pen(70, 70, 70)
DARKERGREY = display.create_pen(30, 30, 30)

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

# 🔄 **Ensure SD card setup**
def setup_sd():
    try:
        sd_spi = machine.SPI(0, sck=machine.Pin(34), mosi=machine.Pin(35), miso=machine.Pin(36))
        sd = sdcard.SDCard(sd_spi, machine.Pin(39))
        uos.mount(sd, "/sd")

        if "gallery" not in uos.listdir("/sd"):
            uos.mkdir(SD_DIR)

        print("✅ SD Card Mounted Successfully!")
    except Exception as e:
        print(f"🚨 SD Mount Error: {e}")

# 📡 **Connect to Wi-Fi**
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("🌐 Connecting to Wi-Fi...")
        wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            utime.sleep(1)
            timeout -= 1
    if wlan.isconnected():
        print(f"✅ Connected to Wi-Fi: {wlan.ifconfig()[0]}")
    else:
        print("🚨 Failed to connect to Wi-Fi")

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


# 🖼️ Clean filename for SD card storage
def clean_filename(name, extension):
    if not isinstance(name, str) or not isinstance(extension, str):
        return "default_image.jpg"  # ✅ Fallback filename

    name = re.sub(r"[^a-z0-9_]", "_", name.lower())  # ✅ Safe characters only
    filename = f"{name[:50]}.{extension}"  # ✅ Limit length

    print(f"🔍 DEBUG: Clean Filename -> {filename}")
    return filename



def download_image(url, name):
    try:
        # ✅ Convert to string explicitly to prevent tuple errors
        url = str(url).strip()

        # ✅ Ensure URL is valid
        if not url.startswith("http"):
            print(f"🚨 No valid image URL provided! URL received: {url}")
            return None

        # ✅ Normalize extension (.jpeg → .jpg)
        url = url.lower()
        if url.endswith(".png"):
            extension = "png"
        elif url.endswith((".jpg", ".jpeg")):
            extension = "jpg"
        else:
            print(f"🚨 Unsupported image format: {url}")
            return None

        # ✅ Ensure filename is a string
        filename = clean_filename(name, extension)
        filepath = f"{SD_DIR}/{filename}"

        # 🔍 Debug Filename & Path
        print(f"🔍 DEBUG: Filename -> {filename}, Type -> {type(filename)}")
        print(f"🔍 DEBUG: Filepath -> {filepath}, Type -> {type(filepath)}")

        # ✅ Download image
        response = urequests.get(url)
        if response.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(response.content)
            response.close()
            gc.collect()
            print(f"✅ Image saved: {filepath}")
            return filepath  # ✅ Ensure function returns a string
        else:
            print(f"🚨 Image Download Error: {response.status_code}")
            response.close()
            return None
    except Exception as e:
        print(f"🚨 Error Downloading Image: {e}")
        return None




# 📡 **Fetch latest launch data**
def fetch_launch_data():
    base_url = "https://ll.thespacedevs.com/2.3.0/launches/"
    now = utime.time()
    future = now + (180 * 24 * 60 * 60)
    now_iso = unix_to_iso8601(now)
    future_iso = unix_to_iso8601(future)

    url = f"{base_url}?net__gte={now_iso}&net__lte={future_iso}&include_suborbital=false&mode=detailed&limit=1&ordering=net"
    print(f"🌍 Fetching: {url}")

    try:
        response = urequests.get(url)
        if response.status_code == 200:
            data = response.json()
            response.close()
            print(f"✅ Launch data fetched successfully!")
            gc.collect()
            return data
        else:
            print(f"❌ API Error: {response.status_code} - {response.text}")
            response.close()
            return None
    except Exception as e:
        print(f"🚨 Error Fetching Data: {e}")
        return None



# 📸 Display Background Image (Supports PNG & JPEG)
def display_background(image_path):
    try:
        display.set_pen(0)  # Set black background
        display.clear()

        # ✅ Handle PNG images (Use scale=2 and center properly)
        if image_path.endswith(".png"):
            png = pngdec.PNG(display)
            png.open_file(image_path)

            # ✅ Get actual PNG dimensions
            try:
                image_width, image_height = png.get_width(), png.get_height()
            except AttributeError:
                image_width, image_height = 480, 480  # Default if method isn't available

            # ✅ Calculate the true centered position
            center_x = (WIDTH - (image_width * 2)) // 2  
            center_y = (HEIGHT - (image_height * 2)) // 2  

            png.decode(center_x, center_y, scale=2)  # ✅ Scale PNG properly & center it

        # ✅ Handle JPEG images (Ensure correct scaling & centering)
        elif image_path.endswith((".jpg", ".jpeg")):  # ✅ Support .jpeg files
            jpeg.open_file(image_path)

            # ✅ JPEGs are automatically scaled with SCALE_HALF, assume full-screen
            image_width, image_height = 480, 480  
            
            # ✅ Calculate the true centered position
            center_x = (WIDTH - image_width) // 2
            center_y = (HEIGHT - image_height) // 2

            jpeg.decode(center_x, center_y, jpegdec.JPEG_SCALE_HALF)  # ✅ Center JPEG

        else:
            print(f"🚨 Unsupported Image Format: {image_path}")
            return

        print(f"✅ Image loaded and centered: {image_path} at ({center_x}, {center_y})")

    except Exception as e:
        print(f"🚨 Error Displaying Image: {e}")

# 📡 **Countdown Timer + LED Effects**
def display_countdown(launch_time):
    vector.set_font("Roboto-Medium.af", 35)

    # Measure text widths
    t_dash_width = int(vector.measure_text("T-")[2])
    num_widths = [int(vector.measure_text(f"00")[2]) for _ in range(4)]
    colon_width = int(vector.measure_text(":")[2])

    total_countdown_width = t_dash_width + sum(num_widths) + (colon_width * 3) + (15 * 4)
    countdown_x_start = int((WIDTH - total_countdown_width) // 2 - 20)
    text_y = int(HEIGHT // 2 - 30)
    label_y = int(text_y + 30)
    label_font_size = 18

    pulse_step = 0
    pulse_speed = 0.10
    nebula_step = 0
    nebula_speed = 0.002
    transition_time = 200
    color_progress = 0

    led_colors = [NEBULA_COLORS[i % len(NEBULA_COLORS)] for i in range(NUM_LEDS)]
    next_colors = [(i + 1) % len(NEBULA_COLORS) for i in range(NUM_LEDS)]

    while utime.time() < launch_time:
        now = utime.time()
        remaining_seconds = int(launch_time - now)

        if remaining_seconds <= 0:
            print("🎉 Countdown complete! Fetching new launch data...")
            return  # Exit countdown to fetch new data

        # Calculate days, hours, minutes, seconds
        days = remaining_seconds // 86400
        hours = (remaining_seconds % 86400) // 3600
        minutes = (remaining_seconds % 3600) // 60
        seconds = remaining_seconds % 60

        countdown_numbers = [f"{days:02}", f"{hours:02}", f"{minutes:02}", f"{seconds:02}"]
        labels = ["DAYS", "HOURS", "MINS", "SECS"]

        # 🚨 **Countdown Warning Mode (< 30 minutes left)**
        if remaining_seconds < 1800:
            pulse_intensity = int(200 + 55 * math.sin(pulse_step))
            text_color = display.create_pen(pulse_intensity, pulse_intensity, pulse_intensity)

            # 🔴 **Pulse Backlight LEDs Red**
            red_intensity = int(100 + 100 * math.sin(pulse_step))
            for i in range(NUM_LEDS):
                bl.set_rgb(i, red_intensity, 0, 0)

            pulse_step += pulse_speed

        else:  # 🌌 **Idle Mode (Nebula Effect)**
            text_color = WHITE

            color_progress += 1 / transition_time
            if color_progress >= 1.0:
                color_progress = 0
                for i in range(NUM_LEDS):
                    led_colors[i] = NEBULA_COLORS[next_colors[i]]
                    next_colors[i] = (next_colors[i] + 1) % len(NEBULA_COLORS)

            for i in range(NUM_LEDS):
                r, g, b = lerp_color(led_colors[i], NEBULA_COLORS[next_colors[i]], color_progress)
                bl.set_rgb(i, r, g, b)

        display.set_pen(DARKERGREY)
        display.rectangle(countdown_x_start - 10, text_y - 35, total_countdown_width + 70, 80)

        # ✅ Draw countdown
        vector.set_font("Roboto-Medium.af", 35)
        display.set_pen(text_color)
        current_x = countdown_x_start
        vector.text("T-", current_x, text_y)
        current_x += t_dash_width + 15

        for i in range(4):
            vector.text(countdown_numbers[i], current_x, text_y)
            current_x += num_widths[i] + 15
            if i < 3:
                vector.text(":", current_x, text_y)
                current_x += colon_width + 15

        # ✅ Draw labels
        vector.set_font("Roboto-Medium.af", label_font_size)
        display.set_pen(DARKGREY)
        current_x = countdown_x_start + t_dash_width + 15

        for i in range(4):
            num_width = num_widths[i]
            label_width = int(vector.measure_text(labels[i])[2])
            label_x = current_x + (num_width // 2) - (label_width // 2)
            vector.text(labels[i], label_x, label_y)
            current_x += num_width + 15
            if i < 3:
                current_x += colon_width + 15

        presto.update()
        utime.sleep(0.05)

    return True  # Countdown complete


# 📡 Display Launch Data + Countdown
def display_launch(launch_data):
    display.set_pen(0)  
    display.clear()

    if launch_data and "results" in launch_data:
        launch = launch_data["results"][0]  # First launch only
        name = launch["name"]
        net = launch["net"]  # Launch timestamp in ISO 8601 (UTC)
        provider = launch["launch_service_provider"]["name"]
        location = launch["pad"]["location"]["name"]

        # ✅ Extract and format date as DD-MM-YYYY
        date_iso = net.split("T")[0]  # Extract YYYY-MM-DD
        time_iso = net.split("T")[1][:5]  # Extract HH:MM only (UTC/GMT)
        date_parts = date_iso.split("-")
        formatted_date = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}"  # Convert to DD-MM-YYYY

        # ✅ Convert launch time to Unix timestamp
        try:
            date_time = net[:19]
            year, month, day = map(int, date_time.split("T")[0].split("-"))
            hour, minute, second = map(int, date_time.split("T")[1].split(":"))
            launch_time_unix = utime.mktime((year, month, day, hour, minute, second, 0, 0))
        except Exception as e:
            print(f"🚨 Error converting launch time: {e}")
            return

        # ✅ Use `thumbnail_url` instead of full `image_url`        
        # ✅ Extract Image URL Safely
        image_data = launch.get("image", {})

        if isinstance(image_data, dict):
            image_url = image_data.get("thumbnail_url", None)  # ✅ Use thumbnail_url if available
        else:
            image_url = None  # 🚨 Prevent tuple-related errors

        # ✅ Ensure image_url is a valid string before downloading
        if isinstance(image_url, str) and image_url.startswith("http"):
            print(f"🔍 DEBUG: Final Image URL -> {image_url}")
            img_path = download_image(image_url, name)
        else:
            print(f"🚨 Warning: Invalid image URL format -> {image_data}")
            img_path = None

        # ✅ Display the image if download was successful
        if isinstance(img_path, str):
            display_background(img_path)
        else:
            print("🚨 Error: No valid image path found.")


        # ✅ Prepare launch info text (centered)
        text_lines = [
            {"text": f"🚀 {name}", "size": 30},
            {"text": f"📅 {formatted_date}", "size": 30},
            {"text": f"🕒 {time_iso} GMT", "size": 30},
            {"text": f"🏢 {provider}", "size": 20},  # 🔥 Smaller font
            {"text": f"📍 {location}", "size": 20},  # 🔥 Smaller font
        ]

        # ✅ Dynamically center each text line
        text_y = int(HEIGHT - 120)  # Ensure integer
        spacing = int(27)  # Ensure integer

        for line in text_lines:
            text_offset = -8
            vector.set_font("Roboto-Medium.af", line["size"])  # ✅ Set font size
            text_width = int(vector.measure_text(line["text"])[2])  # ✅ Ensure integer
            text_x = int((WIDTH - text_width) / 2) + text_offset # ✅ Convert to integer

            # 🔥 Draw Shadow (Black, offset by +2 pixels)
            display.set_pen(BLACK)
            vector.text(line["text"], text_x + 2, text_y + 2)

            # 🔥 Draw Main Text (White, on top)
            display.set_pen(WHITE)
            vector.text(line["text"], text_x, text_y)

            text_y += spacing  # Move down for next line

        presto.update()

        # ✅ Start Countdown Without Clearing the Screen
        display_countdown(launch_time_unix)


# 🔄 **Main Loop**
setup_sd()
connect_wifi()
clear_images()
gc.collect()

while True:
    launch_data = fetch_launch_data()
    if launch_data:
        display_launch(launch_data)
        countdown_finished = display_countdown(launch_time_unix)  # 🔄 Wait for countdown
        if countdown_finished:
            print("🔄 Fetching new launch data...")
            continue  # Restart loop

    utime.sleep(3600)
