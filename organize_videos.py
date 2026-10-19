import os
import shutil
import time

# Mapping of task UUID to video subject
TASK_MAP = {
    "c97c5840-35ce-4441-b3d1-e959448a6525": "Reliance_Industries",
    "bbcb2818-4836-4031-9ae7-56d2438eac58": "HDFC_Bank",
    "d2d3ceb0-6aea-4aba-b9ec-f8c8f68c21de": "TCS",
    "abaa3db7-50ce-4650-8e65-778894e9b731": "ICICI_Bank",
    "31207e09-4609-4479-a3b2-6866a87653ad": "Bajaj_Finance",
    "15cfe072-2fcb-4402-9f93-deaab2ed3af1": "Larsen_and_Toubro",
    "231e73f0-a38e-47a8-96b2-fea9186d4330": "Infosys",
    "3dc67964-3381-465d-bad7-245b934b5431": "Hindustan_Unilever",
    "53be8456-37e1-465d-85de-67409b7cf8f1": "ITC",
    "5875e5da-457d-4cc3-ba62-d606701317a6": "Bharti_Airtel"
}

BASE_DIR = "/Users/apple/Documents/Antigravity/untitled folder/storage/tasks"
OUTPUT_DIR = "/Users/apple/Documents/Antigravity/untitled folder/Final_Videos"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

print("Monitoring output directories for completed videos...")

completed = set()

while len(completed) < len(TASK_MAP):
    for task_id, title in TASK_MAP.items():
        if task_id in completed:
            continue
        
        # Checking for final-1.mp4 (this is the completed file MoneyPrinterTurbo produces)
        final_video_path = os.path.join(BASE_DIR, task_id, "final-1.mp4")
        
        if os.path.exists(final_video_path):
            # We wait a couple of seconds to ensure ffmpeg has completely released the file lock
            time.sleep(2)
            
            clean_name = f"{title}.mp4"
            dest_path = os.path.join(OUTPUT_DIR, clean_name)
            
            # Copy instead of rename to prevent breaking any internal state of MPT
            shutil.copy2(final_video_path, dest_path)
            print(f"✅ Extracted and renamed: {clean_name}")
            completed.add(task_id)
            
    if len(completed) < len(TASK_MAP):
        time.sleep(10)

print("\n🎉 All 10 videos have been successfully organized in the 'Final_Videos' folder!")
