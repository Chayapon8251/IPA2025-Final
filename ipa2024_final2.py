import os
import time
from dotenv import load_dotenv
from webexteamssdk import WebexTeamsAPI
import restconf_final 
import netmiko_final
import ansible_final

# โหลด environment variables จากไฟล์ .env
load_dotenv()

WEBEX_TOKEN = os.getenv("WEBEX_TEAMS_ACCESS_TOKEN")
#devnet
#ROOM_ID = "Y2lzY29zcGFyazovL3VybjpURUFNOnVzLXdlc3QtMl9yL1JPT00vZTZkNTkzMzAtNmY4Ny0xMWYwLTk3YjctMGIxYzg5Y2RlMzQw"
#ipa2025
ROOM_ID = "Y2lzY29zcGFyazovL3VybjpURUFNOnVzLXdlc3QtMl9yL1JPT00vYmQwODczMTAtNmMyNi0xMWYwLWE1MWMtNzkzZDM2ZjZjM2Zm"
ROUTER_IP = "10.0.15.61" # <-- ใส่ IP ของคุณ (หรือ 61-65)

# --- 1. เพิ่ม ID ของคุณเป็นตัวแปร ---
MY_STUDENT_ID = "66070039" 

if not WEBEX_TOKEN:
    print("Error: WEBEX_TEAMS_ACCESS_TOKEN not found.")
    exit()

api = WebexTeamsAPI(access_token=WEBEX_TOKEN)

# --- (ฟังก์ชัน process_message ทั้งหมด... ไม่ต้องแก้) ---
# (ฟังก์ชันนี้คือเวอร์ชันสมบูรณ์จากรอบที่แล้ว)
def process_message(message_text, student_id):
    """
    อัปเกรด: คืนค่าเป็น Tuple (message_type, content)
    """
    parts = message_text.lower().split()
    if len(parts) != 2:
        return ('error', "Invalid command format. Use: /<studentID> <command>")

    command = parts[1]
    print(f"Received command '{command}' for studentID '{student_id}'")

    # --- ส่วนของ RESTCONF ---
    if command == "create":
        msg = restconf_final.create_interface(ROUTER_IP, student_id)
        return ('text', msg)
    elif command == "delete":
        msg = restconf_final.delete_interface(ROUTER_IP, student_id)
        return ('text', msg)
    elif command == "enable":
        msg = restconf_final.set_interface_state(ROUTER_IP, student_id, enabled=True)
        return ('text', msg)
    elif command == "disable":
        msg = restconf_final.set_interface_state(ROUTER_IP, student_id, enabled=False)
        return ('text', msg)
    elif command == "status":
        status = restconf_final.get_interface_status(ROUTER_IP, f"Loopback{student_id}")
        if status == "exists_enabled":
            return ('text', f"Interface loopback {student_id} is enabled")
        elif status == "exists_disabled":
            return ('text', f"Interface loopback {student_id} is disabled")
        elif status == "not_exists":
            return ('text', f"No Interface loopback {student_id}")
        else:
            return ('error', "Error checking status.")
    
    # --- ส่วนของ Netmiko และ Ansible ---
    elif command == "gigabit_status":
        msg = netmiko_final.gigabit_status(ROUTER_IP)
        if msg.startswith("Error:"):
             return ('error', msg)
        else:
             return ('text', msg)
        
    elif command == "showrun":
        result = ansible_final.showrun(student_id, ROUTER_IP)
        if result.startswith("Error:"):
            return ('error', result)
        else:
            return ('file', result) 
            
    else:
        return ('error', f"Unknown command: {command}")


# --- 2. อัปเกรด Main Loop (นี่คือส่วนที่แก้) ---
last_processed_message_id = None 

try:
    while True:
        messages = api.messages.list(roomId=ROOM_ID, max=1)
        last_message = next(iter(messages), None)

        if last_message and last_message.id != last_processed_message_id:
            
            print(f"\nNew message detected: {last_message.text}")
            last_processed_message_id = last_message.id

            if last_message.text.startswith("/"):
                try:
                    student_id = last_message.text.split()[0][1:]
                    if student_id.isdigit() and len(student_id) == 8:
                        
                        # --- 3. นี่คือ "ตัวกรอง" ที่เพิ่มเข้ามา ---
                        if student_id == MY_STUDENT_ID:
                            print(f"Processing command for {MY_STUDENT_ID}...")
                            
                            # --- (โค้ดประมวลผลเดิม) ---
                            msg_type, content = process_message(last_message.text, student_id)
                            
                            if msg_type == 'file':
                                print(f"Sending file: {content}")
                                api.messages.create(roomId=ROOM_ID, files=[content], text=f"Here is the config for {student_id}")
                            else:
                                print(f"Sending text: {content}")
                                api.messages.create(roomId=ROOM_ID, text=content)
                            # --- (จบโค้ดประมวลผลเดิม) ---
                            
                        else:
                            # ถ้า ID ไม่ตรง ก็แค่พิมพ์บอกแล้วไม่ทำอะไร
                            print(f"Ignoring command for other student: {student_id}")
                        # --- (จบ "ตัวกรอง") ---
                            
                    else:
                        print("Message is not a valid student command.")
                except IndexError:
                    print("Invalid command format.")
            else:
                print("Message is not a command.")

        time.sleep(5)

except KeyboardInterrupt:
    print("\nBot stopped by user.")