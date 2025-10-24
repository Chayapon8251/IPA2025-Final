import os
import time
from dotenv import load_dotenv
from webexteamssdk import WebexTeamsAPI

# Import ทุกไฟล์ที่เราจะใช้
import restconf_final 
import netconf_final
import netmiko_final
import ansible_final

# --- 1. ตั้งค่า Global ---
load_dotenv()
WEBEX_TOKEN = os.getenv("WEBEX_TEAMS_ACCESS_TOKEN")
ROOM_ID = "Y2lzY29zcGFyazovL3VybjpURUFNOnVzLXdlc3QtMl9yL1JPT00vYmQwODczMTAtNmMyNi0xMWYwLWE1MWMtNzkzZDM2ZjZjM2Zm" # ห้อง IPA2025
MY_STUDENT_ID = "66070039"
VALID_IPS = ["10.0.15.61", "10.0.15.62", "10.0.15.63", "10.0.15.64", "10.0.15.65"]

current_method = None # สถานะเริ่มต้น

if not WEBEX_TOKEN:
    print("Error: WEBEX_TEAMS_ACCESS_TOKEN not found.")
    exit()

# --- 2. (แก้ไข!) สร้าง API พร้อม Timeout 10 วินาที ---
try:
    api = WebexTeamsAPI(access_token=WEBEX_TOKEN) 
    # ลองทดสอบเชื่อมต่อ (เพื่อเช็ค Token และ Network)
    print("Connecting to Webex...")
    api.people.me() 
    print("Webex connection successful.")
except Exception as e:
    print(f"FATAL ERROR: Could not connect to Webex API. Check Token/Network.")
    print(e)
    exit()

# --- 3. (แก้ไข!) ฟังก์ชัน Helper (เราจะใช้ฟังก์ชันจากไฟล์อื่นโดยตรง) ---
# (เราลบ handle_part1_command และ handle_part2_command ทิ้งไป)
# (เราจะย้าย Logic ไปไว้ใน Loop หลักแทน เพื่อให้จัดการง่ายขึ้น)

# --- 4. (ใหม่!) "Priming" - อ่านข้อความล่าสุดก่อนเริ่ม Loop ---
try:
    print("Initializing... Fetching last message ID to avoid spam.")
    messages = api.messages.list(roomId=ROOM_ID, max=1)
    last_message = next(iter(messages), None)
    if last_message:
        last_processed_message_id = last_message.id
        print(f"Initialization complete. Ignoring messages before: {last_message.text[:20]}...")
    else:
        last_processed_message_id = None
        print("Initialization complete. Room is empty.")
except Exception as e:
    print(f"Warning: Could not prime last message ID: {e}")
    last_processed_message_id = None # ถ้าล้มเหลว ก็เริ่มจากศูนย์

# --- 5. Main Loop (อัปเกรดให้ดักจับ Network Error) ---
print(f"Bot is running... ONLY listening for ID {MY_STUDENT_ID}. Press Ctrl+C to stop.")

try:
    while True:
        print(".", end="", flush=True) # พิมพ์จุดเพื่อเช็คว่า Loop ยัง "หายใจ"

        try:
            # --- ดึงข้อความ (ที่อาจจะค้าง) ---
            messages = api.messages.list(roomId=ROOM_ID, max=5) 
        
        except Exception as e: # ดักจับ Timeout, Network Error
            print(f"\n[NETWORK ERROR] Failed to fetch messages: {e}")
            print("...Will retry in 5 seconds...")
            time.sleep(5) # Sleep นานขึ้นถ้าเน็ตล่ม
            continue # ข้ามไปเริ่ม Loop ใหม่

        # --- (Logic เดิมในการหาข้อความใหม่) ---
        new_messages = []
        for msg in messages:
            if msg.id == last_processed_message_id:
                break
            new_messages.append(msg)

        if new_messages:
            for msg in reversed(new_messages):
                print(f"\nNew message detected: {msg.text}")
                
                cleaned_text = msg.text.strip()
                # --- (Logic เดิมในการ Parse และ Filter) ---
                if not cleaned_text.startswith("/"):
                    print("Message is not a command.")
                    continue

                parts = cleaned_text.split()
                command_student_id = parts[0][1:]

                if command_student_id != MY_STUDENT_ID:
                    print(f"Ignoring command for other student: {command_student_id}")
                    continue
                    
                print(f"Processing command for {MY_STUDENT_ID}...")
                
                msg_type = 'error'
                content = 'Error: Invalid command structure.'

                try:
                    # --- (Logic การ Parse จากโค้ดเดิมของคุณ) ---
                    if len(parts) == 2:
                        cmd_or_ip = parts[1].lower()
                        if cmd_or_ip == 'restconf':
                            current_method = 'restconf'
                            msg_type, content = ('text', 'Ok: Restconf')
                        elif cmd_or_ip == 'netconf':
                            current_method = 'netconf'
                            msg_type, content = ('text', 'Ok: Netconf')
                        elif cmd_or_ip in VALID_IPS:
                            msg_type, content = ('error', 'Error: No command found.')
                        else: 
                            if current_method is None:
                                msg_type, content = ('error', 'Error: No method specified')
                            else:
                                msg_type, content = ('error', 'Error: No IP specified')

                    elif len(parts) == 3:
                        ip_address = parts[1]
                        command = parts[2].lower()
                        
                        if ip_address not in VALID_IPS:
                            msg_type, content = ('error', f"Error: Invalid IP: {ip_address}")
                        elif command in ['create', 'delete', 'enable', 'disable', 'status']:
                            if current_method is None:
                                msg_type, content = ('error', 'Error: No method specified')
                            else:
                                # (เรียกฟังก์ชันจากไฟล์อื่นโดยตรง)
                                if current_method == "restconf":
                                    if command == "create": content = restconf_final.create_interface(ip_address, MY_STUDENT_ID)
                                    elif command == "delete": content = restconf_final.delete_interface(ip_address, MY_STUDENT_ID)
                                    elif command == "enable": content = restconf_final.set_interface_state(ip_address, MY_STUDENT_ID, enabled=True)
                                    elif command == "disable": content = restconf_final.set_interface_state(ip_address, MY_STUDENT_ID, enabled=False)
                                    elif command == "status":
                                        status = restconf_final.get_interface_status(ip_address, f"Loopback{MY_STUDENT_ID}")
                                        if status == "exists_enabled": content = f"Interface loopback {MY_STUDENT_ID} is enabled (checked by Restconf)"
                                        elif status == "exists_disabled": content = f"Interface loopback {MY_STUDENT_ID} is disabled (checked by Restconf)"
                                        elif status == "not_exists": content = f"No Interface loopback {MY_STUDENT_ID} (checked by Restconf)"
                                        else: content = "Error checking status (Restconf)."
                                else: # (current_method == "netconf")
                                    if command == "create": content = netconf_final.create_interface(ip_address, MY_STUDENT_ID)
                                    elif command == "delete": content = netconf_final.delete_interface(ip_address, MY_STUDENT_ID)
                                    elif command == "enable": content = netconf_final.set_interface_state(ip_address, MY_STUDENT_ID, enabled=True)
                                    elif command == "disable": content = netconf_final.set_interface_state(ip_address, MY_STUDENT_ID, enabled=False)
                                    elif command == "status":
                                        status = netconf_final.get_interface_status(ip_address, f"Loopback{MY_STUDENT_ID}")
                                        if status == "exists_enabled": content = f"Interface loopback {MY_STUDENT_ID} is enabled (checked by Netconf)"
                                        elif status == "exists_disabled": content = f"Interface loopback {MY_STUDENT_ID} is disabled (checked by Netconf)"
                                        elif status == "not_exists": content = f"No Interface loopback {MY_STUDENT_ID} (checked by Netconf)"
                                        else: content = "Error checking status (Netconf)."
                                msg_type = 'text'

                        elif command == 'motd':
                            result = netmiko_final.read_motd(ip_address)
                            if result is None: content = f"Error: No MOTD Configured on {ip_address}"
                            elif result.startswith("Error:"): content = result
                            else: content = result
                            msg_type = 'text'
                        
                        else:
                            msg_type, content = ('error', f"Error: Unknown command '{command}'")

                    elif len(parts) > 3:
                        ip_address = parts[1]
                        command = parts[2].lower()
                        
                        if ip_address not in VALID_IPS:
                            msg_type, content = ('error', f"Error: Invalid IP: {ip_address}")
                        elif command == 'motd':
                            message = " ".join(parts[3:])
                            result = ansible_final.write_motd(MY_STUDENT_ID, ip_address, message)
                            if result.startswith("Error:"):
                                msg_type, content = ('error', result)
                            else:
                                msg_type, content = ('text', result) # "Ok: success"
                        else:
                            msg_type, content = ('error', 'Error: Invalid command structure.')
                    
                except Exception as e:
                    print(f"!!! UNHANDLED ERROR: {e} !!!")
                    msg_type, content = ('error', f'Internal Bot Error: {e}')

                # --- ส่งคำตอบกลับ ---
                if msg_type == 'file':
                    print(f"Sending file: {content}")
                    api.messages.create(roomId=ROOM_ID, files=[content], text=f"Here is the config for {MY_STUDENT_ID}")
                else:
                    print(f"Sending text: {content}")
                    api.messages.create(roomId=ROOM_ID, text=content)
            
            # --- จบ Loop 'for msg' ---
            last_processed_message_id = new_messages[0].id 

        time.sleep(1) # นอน 1 วินาที

except KeyboardInterrupt:
    print("\nBot stopped by user.")