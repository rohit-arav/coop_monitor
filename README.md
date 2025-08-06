# Coop Monitor

A fully automated chicken‐coop monitoring system using a Reolink E1 Pro PTZ camera, GPT-4o vision analysis, and SMS alerts via Textbelt—scheduled to run ten minutes after local sunset in the Bay Area.

## Project Overview

Every evening, this script will:
1. Move the camera to two PTZ presets:
   - Roost (to count chickens)
   - Door (to verify the door is closed)
2. Capture a full‐frame snapshot via RTSP.
3. Analyze each image with GPT-4o:
   - Count chickens, verify exactly five
   - Confirm door closed or open
4. Send a summary via Textbelt SMS (one free SMS per day).
5. Schedule itself for sunset plus ten minutes, recalculated daily.

## Prerequisites

- Reolink E1 Pro configured with:
  - Static LAN IP (e.g. `192.168.6.120`)
  - ONVIF enabled
  - Two PTZ presets created (“Roost” and “Door”)
  - RTSP Main Stream (`Preview_01_main`) working in VLC
- Python 3.8+ on an always‐on host
- OpenAI account with GPT-4o access
- Textbelt free SMS key (`textbelt`)
- Git and a GitHub account (to host code)

## Installation and Setup

1. **Clone the repository and set up a virtual environment**  
   ```bash
   git clone https://github.com/your-username/coop_monitor.git
   cd coop_monitor
   python3 -m venv venv
   source venv/bin/activate

2. Install dependencies
    pip install opencv-python numpy astral requests schedule onvif-zeep openai python-dotenv

3. Create a .env file in the project root with:
    OPENAI_API_KEY=sk-…
    TEXTBELT_KEY=textbelt
    PHONE_NUMBER=+1YOURNUMBER
    CAM_IP=192.168.6.120
    CAM_USER=admin
    CAM_PASS=your_camera_password
    ONVIF_PORT=8000
    ROOST_PRESET_TOKEN=001
    DOOR_PRESET_TOKEN=000

The script will:

    Compute today’s sunset (SF timezone) + 10 min

    Schedule the job at that time each evening

    Recalculate at 00:05 daily

Use screen, tmux or a systemd service to keep it running.