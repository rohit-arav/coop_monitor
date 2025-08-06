from dotenv import load_dotenv
load_dotenv()  # load variables from .env into os.environ

import cv2
import base64
import time
import schedule
import os
import openai
import requests
from onvif import ONVIFCamera
from astral import LocationInfo
from astral.sun import sun
from datetime import datetime, date, timedelta

# 1. Load config from environment
openai.api_key          = os.getenv("OPENAI_API_KEY")
TEXTBELT_KEY            = os.getenv("TEXTBELT_KEY")
PHONE_NUMBER            = os.getenv("PHONE_NUMBER")
CAM_IP                  = os.getenv("CAM_IP")
CAM_USER                = os.getenv("CAM_USER")
CAM_PASS                = os.getenv("CAM_PASS")
ONVIF_PORT              = int(os.getenv("ONVIF_PORT", "8000"))
ROOST_PRESET_TOKEN      = os.getenv("ROOST_PRESET_TOKEN")
DOOR_PRESET_TOKEN       = os.getenv("DOOR_PRESET_TOKEN")

# 2. Textbelt SMS
def send_sms_textbelt(body: str):
    resp = requests.post("https://textbelt.com/text", {
        "phone": PHONE_NUMBER,
        "message": body,
        "key": TEXTBELT_KEY,
    })
    print("Textbelt response:", resp.json())

# 3. Initialize ONVIF camera
cam = ONVIFCamera(CAM_IP, ONVIF_PORT, CAM_USER, CAM_PASS)
media = cam.create_media_service()
profiles = media.GetProfiles()
profile_token = profiles[0].token
ptz = cam.create_ptz_service()

# 4. RTSP URL
RTSP_URL = f"rtsp://{CAM_USER}:{CAM_PASS}@{CAM_IP}:554/Preview_01_main"

def fetch_frame():
    cap = cv2.VideoCapture(RTSP_URL)
    if not cap.isOpened():
        raise RuntimeError("Cannot open RTSP stream")
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("Failed to grab frame")
    # if upside-down mount:
    # frame = cv2.rotate(frame, cv2.ROTATE_180)
    return frame

def goto_preset(token: str):
    req = ptz.create_type('GotoPreset')
    req.ProfileToken = profile_token
    req.PresetToken  = token
    ptz.GotoPreset(req)
    time.sleep(3)

def analyze_full_frame(frame, context: str):
    _, buf = cv2.imencode('.jpg', frame)
    b64 = base64.b64encode(buf).decode()
    data_url = f"data:image/jpeg;base64,{b64}"

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
                    "(PROBLEM - Only _ chickens found)."
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

    resp = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )
    return resp.choices[0].message.content.strip()

def job():
    try:
        print(time.asctime(), "Moving to Roost preset…")
        goto_preset(ROOST_PRESET_TOKEN)
        frame_roost = fetch_frame()
        cv2.imwrite("full_roost.jpg", frame_roost)
        result_roost = analyze_full_frame(frame_roost, "roost")

        print(time.asctime(), "Moving to Door preset…")
        goto_preset(DOOR_PRESET_TOKEN)
        frame_door = fetch_frame()
        cv2.imwrite("full_door.jpg", frame_door)
        result_door = analyze_full_frame(frame_door, "door")

        summary = f"Chickens: {result_roost}\nDoor: {result_door}"
        print(time.asctime(), summary)

        # SMS sending is commented out for this test
        # send_sms_textbelt(summary)

    except Exception as e:
        print(time.asctime(), "Error in job():", e)

# 5. Astral scheduling (disabled for this test)
# CITY = LocationInfo(
#     name="San Francisco", region="USA",
#     timezone="America/Los_Angeles",
#     latitude=37.7749, longitude=-122.4194
# )
# scheduled_job = None
# def schedule_job_at_sunset():
#     global scheduled_job
#     if scheduled_job:
#         schedule.cancel_job(scheduled_job)
#     s = sun(CITY.observer, date=date.today(), tzinfo=CITY.timezone)
#     run_time = (s["sunset"] + timedelta(minutes=10)).strftime("%H:%M")
#     scheduled_job = schedule.every().day.at(run_time).do(job)
#     print(f"{datetime.now()}: scheduled job at {run_time}")
# schedule_job_at_sunset()
# schedule.every().day.at("00:05").do(schedule_job_at_sunset)

if __name__ == "__main__":
    # One-off test run
    job()
    # exit()  # uncomment to prevent any further looping
