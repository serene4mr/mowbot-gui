# Use Python 3.10 slim as the base image
FROM python:3.10-slim-bullseye

# 1. Set environment variables
# Prevents Python from writing .pyc files and ensures logs are sent to terminal
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Set the default display for X11 forwarding
ENV DISPLAY=:0

# 2. Install system dependencies for PySide6 and QtWebEngine
# These are critical for the ESRI Maps (Chromium-based) to render correctly
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libevent-2.1-7 \
    libegl1 \
    libgl1-mesa-dri \
    libgl1-mesa-glx \
    libglib2.0-0 \
    mesa-vulkan-drivers \
    libminizip1 \
    libopus0 \
    libtiff5 \
    libwebpdemux2 \
    libwebpmux3 \
    libx11-xcb1 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    libdbus-1-3 \
    libfontconfig1 \
    libnss3 \
    libasound2 \
    libxtst6 \
    libxcomposite1 \
    libxdamage1 \
    libxkbfile1 \
    libxrandr2 \
    libxml2 \
    libxslt1.1 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. Set the working directory
WORKDIR /app

# 4. Install Python dependencies (Optimized for Caching)
# We copy only the requirements file first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the application source code
COPY . .

# 6. Execute the application
# Make sure your main entry point is at src/main.py
CMD ["python", "src/main.py"]