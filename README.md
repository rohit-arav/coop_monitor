# Coop Monitor

A fully automated chicken-coop monitoring system using a Reolink E1 Pro PTZ camera, GPT-4o vision analysis, and Telegram notifications.

## Project Overview

This script will:
1. Move the camera to two PTZ presets:
   - Roost (to count chickens)
   - Door (to verify the door is closed)
2. Capture a full‐frame snapshot via RTSP.
3. Analyze each image with GPT-4o:
   - Count chickens, verify exactly five
   - Confirm door closed or open
4. Send a summary via Telegram with a status update.

## Prerequisites

- Reolink E1 Pro configured with:
  - Static LAN IP
  - ONVIF enabled
  - Two PTZ presets created (“Roost” and “Door”)
  - RTSP Main Stream (`Preview_01_main`) working in VLC
- Python 3.8+ 
- OpenAI account with GPT-4o access
- Telegram Bot Token and Chat ID

## Installation and Setup

1. **Clone the repository and set up a virtual environment**  
   ```bash
   git clone https://github.com/your-username/coop_monitor.git
   cd coop_monitor
   python3 -m venv venv
   source venv/bin/activate

2. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3. Create a .env file in the project root with:
    ```
    # Required
    OPENAI_API_KEY=your_openai_api_key
    TELEGRAM_BOT_TOKEN=your_telegram_bot_token
    TELEGRAM_CHAT_ID=your_telegram_chat_id
    CAM_IP=192.168.6.120
    CAM_USER=admin
    CAM_PASS=your_camera_password
    
    # Optional (with defaults)
    ONVIF_PORT=8000
    ROOST_PRESET_TOKEN=001
    DOOR_PRESET_TOKEN=002
    ```