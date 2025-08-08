import logging
import logging.handlers
import sys
import os
import time
import base64
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

import cv2
import openai
import requests
from onvif import ONVIFCamera

# Setup logging
def setup_logging():
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_file = 'coop_monitor.log'
    
    os.makedirs('logs', exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # File handler (rotates daily, keeps 7 days)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        f'logs/{log_file}', when='midnight', backupCount=7, encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logging.getLogger(__name__)

# Initialize logger
logger = setup_logging()

# Load config from environment
try:
    openai.api_key = os.getenv("OPENAI_API_KEY")
    # Telegram Bot Configuration
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    CAM_IP = os.getenv("CAM_IP")
    CAM_USER = os.getenv("CAM_USER")
    CAM_PASS = os.getenv("CAM_PASS")
    ONVIF_PORT = int(os.getenv("ONVIF_PORT", "8000"))
    ROOST_PRESET_TOKEN = os.getenv("ROOST_PRESET_TOKEN")
    DOOR_PRESET_TOKEN = os.getenv("DOOR_PRESET_TOKEN")
    
    # Verify required environment variables
    required_vars = ["OPENAI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", 
                    "CAM_IP", "CAM_USER", "CAM_PASS", 
                    "ROOST_PRESET_TOKEN", "DOOR_PRESET_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    logger.info("Successfully loaded all environment variables")
    
except Exception as e:
    logger.error(f"Error loading configuration: {str(e)}")
    raise

# Telegram Notification
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram bot token or chat ID not configured")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:

        formatted_message = message.replace('\\n', '\n')
        full_message = formatted_message 
        
        logger.debug(f"Sending Telegram message: {full_message}")
        
        response = requests.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": full_message,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        response.raise_for_status()
        
        logger.info("Telegram notification sent successfully")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Telegram notification: {str(e)}")
        return False
    except Exception as e:
        logger.exception("Unexpected error in send_telegram_message")
        return False

# Initialize ONVIF camera
cam = ONVIFCamera(CAM_IP, ONVIF_PORT, CAM_USER, CAM_PASS)
media = cam.create_media_service()
profiles = media.GetProfiles()
profile_token = profiles[0].token
ptz = cam.create_ptz_service()

# RTSP URL
RTSP_URL = f"rtsp://{CAM_USER}:{CAM_PASS}@{CAM_IP}:554/Preview_01_main"

def fetch_frame(max_attempts=3):
    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(f"Attempt {attempt}/{max_attempts} to capture frame")
            cap = cv2.VideoCapture(RTSP_URL)
            
            if not cap.isOpened():
                logger.warning(f"Failed to open RTSP stream (attempt {attempt}/{max_attempts})")
                time.sleep(1)  # Wait before retrying
                continue
                
            ret, frame = cap.read()
            cap.release()
            
            if not ret or frame is None:
                logger.warning(f"Failed to grab frame (attempt {attempt}/{max_attempts})")
                time.sleep(1)  # Wait before retrying
                continue
                
            # if upside-down mount:
            #     frame = cv2.rotate(frame, cv2.ROTATE_180)
                
            logger.debug(f"Successfully captured frame (attempt {attempt})")
            return frame
            
        except Exception as e:
            logger.warning(f"Error capturing frame (attempt {attempt}): {str(e)}")
            if attempt < max_attempts:
                time.sleep(1)  # Wait before retrying
            
    # If we get here, all attempts failed
    error_msg = f"Failed to capture frame after {max_attempts} attempts"
    logger.error(error_msg)
    raise RuntimeError(error_msg)

def goto_preset(token):
    req = ptz.create_type('GotoPreset')
    req.ProfileToken = profile_token
    req.PresetToken = token
    ptz.GotoPreset(req)
    time.sleep(3)

def analyze_full_frame(frame, context):
    try:
        # Convert frame to base64
        _, buffer = cv2.imencode('.jpg', frame)
        data_url = f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"
        
        # Prepare messages
        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Count how many chickens are in this image. "
                        "The amount we are looking for is 5. "
                        "If you see 5, answer with "
                        "(OKAY - 5 Chickens found). "
                        "If you see less than 5, answer with "
                        "(PROBLEM - ONLY _ CHICKENS FOUND)."
                        if context == "roost"
                        else
                        "Is the coop door fully closed? "
                        "Answer with (OKAY - Door is closed) or "
                        "(PROBLEM - DOOR IS STILL OPEN)."
                    )
                },
                {
                    "type": "image_url",
                    "image_url": {"url": data_url}
                }
            ]
        }]

        # Get response from OpenAI
        resp = openai.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=100
        )
        
        return resp.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error in analyze_full_frame: {str(e)}")
        return f"ERROR - {str(e)}"

def job():
    logger.info("Starting coop monitoring job")
    
    try:
        # Check roost
        logger.info("Moving to Roost preset")
        goto_preset(ROOST_PRESET_TOKEN)
        
        logger.debug("Capturing roost frame")
        frame_roost = fetch_frame()
        
        roost_image_path = "logs/roost_last_check.jpg"
        cv2.imwrite(roost_image_path, frame_roost)
        logger.debug(f"Saved roost image to {roost_image_path}")
        
        logger.info("Analyzing roost image")
        result_roost = analyze_full_frame(frame_roost, "roost")
        logger.info(f"Roost analysis result: {result_roost}")

        # Check door
        logger.info("Moving to Door preset")
        goto_preset(DOOR_PRESET_TOKEN)
        
        logger.debug("Capturing door frame")
        frame_door = fetch_frame()
        
        door_image_path = "logs/door_last_check.jpg"
        cv2.imwrite(door_image_path, frame_door)
        logger.debug(f"Saved door image to {door_image_path}")
        
        logger.info("Analyzing door image")
        result_door = analyze_full_frame(frame_door, "door")
        logger.info(f"Door analysis result: {result_door}")

        # Prepare message with dynamic title
        is_roost_ok = "OKAY" in result_roost and "PROBLEM" not in result_roost
        is_door_ok = "OKAY" in result_door and "PROBLEM" not in result_door
        
        # Set title and emoji depending on results
        if is_roost_ok and is_door_ok:
            title = "✅ All Good!"
        else:
            title = "🚨 PROBLEM DETECTED"
        
        # Format message with title and details
        message = (
            f"*{title}*\n\n"
            f"🐔 {result_roost}\n"
            f"🚪 {result_door}\n\n"
            f"🕒 {datetime.now().strftime('%Y-%m-%d %I:%M %p %Z')}"
        )
        
        logger.info(f"Sending message: {message}")
        
        if not send_telegram_message(message):
            logger.warning("Failed to send Telegram notification")
            
        logger.info("Coop monitoring job completed successfully")
        
    except Exception as e:
        error_msg = f"Error in job(): {str(e)}"
        logger.error(error_msg, exc_info=True)
        send_telegram_message(f"❌ Coop Monitor Error\n\n{error_msg}")

def main():
    try:
        logger.info("=" * 50)
        logger.info("Starting Coop Monitor")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Current time: {datetime.now()}")
        
        logger.info("Running coop check...")
        job()
        logger.info("Coop check completed successfully")
        
    except Exception as e:
        error_msg = f"Coop Monitor Error: {str(e)}"
        logger.critical(error_msg, exc_info=True)
        send_telegram_message(f"❌ {error_msg}")
    finally:
        logger.info("Coop Monitor stopped")

if __name__ == "__main__":
    main()
