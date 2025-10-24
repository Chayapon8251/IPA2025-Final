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
ROOM_ID = "Y2lzY29zcGFyazovL3VybjpURUFNOnVzLXdlc3QtMl9yL1JPT00vZTZkNTkzMzAtNmY4Ny0xMWYwLTk3YjctMGIxYzg5Y2RlMzQw"
#ipa2025
# ROOM_ID = "Y2lzY29zcGFyazovL3VybjpURUFNOnVzLXdlc3QtMl9yL1JPT00vYmQwODczMTAtNmMyNi0xMWYwLWE1MWMtNzkzZDM2ZjZjM2Zm"
VALID_IPS = ["10.0.15.61", "10.0.15.62", "10.0.15.63", "10.0.15.64", "10.0.15.65"]


MY_STUDENT_ID = "66070039" 

current_method = None
last_processed_message_id = None

if not WEBEX_TOKEN:
    print("Error: WEBEX_TEAMS_ACCESS_TOKEN not found.")
    exit()

api = WebexTeamsAPI(access_token=WEBEX_TOKEN)

# --- (ฟังก์ชัน process_message ทั้งหมด... ไม่ต้องแก้) ---
# (ฟังก์ชันนี้คือเวอร์ชันสมบูรณ์จากรอบที่แล้ว)
def handle_part1_command(command, ip_address, student_id):
    """เรียกใช้ฟังก์ชัน Restconf/Netconf ตาม 'current_method'"""
    
    if current_method == "restconf":
        if command == "create":
            return ('text', restconf_final.create_interface(ip_address, student_id))
        elif command == "delete":
            return ('text', restconf_final.delete_interface(ip_address, student_id))
        elif command == "enable":
            return ('text', restconf_final.set_interface_state(ip_address, student_id, enabled=True))
        elif command == "disable":
            return ('text', restconf_final.set_interface_state(ip_address, student_id, enabled=False))
        elif command == "status":
            status = restconf_final.get_interface_status(ip_address, f"Loopback{student_id}")
            if status == "exists_enabled":
                return ('text', f"Interface loopback {student_id} is enabled (checked by Restconf)")
            elif status == "exists_disabled":
                return ('text', f"Interface loopback {student_id} is disabled (checked by Restconf)")
            elif status == "not_exists":
                return ('text', f"No Interface loopback {student_id} (checked by Restconf)")
            else:
                return ('error', "Error checking status (Restconf).")
                
    elif current_method == "netconf":
        if command == "create":
            return ('text', netconf_final.create_interface(ip_address, student_id))
        elif command == "delete":
            return ('text', netconf_final.delete_interface(ip_address, student_id))
        elif command == "enable":
            return ('text', netconf_final.set_interface_state(ip_address, student_id, enabled=True))
        elif command == "disable":
            return ('text', netconf_final.set_interface_state(ip_address, student_id, enabled=False))
        elif command == "status":
            status = netconf_final.get_interface_status(ip_address, f"Loopback{student_id}")
            if status == "exists_enabled":
                return ('text', f"Interface loopback {student_id} is enabled (checked by Netconf)")
            elif status == "exists_disabled":
                return ('text', f"Interface loopback {student_id} is disabled (checked by Netconf)")
            elif status == "not_exists":
                return ('text', f"No Interface loopback {student_id} (checked by Netconf)")
            else:
                return ('error', "Error checking status (Netconf).")
    
    return ('error', 'Internal error: Method not recognized.')


def handle_part2_command(command, ip_address, student_id, message):
    """เรียกใช้ฟังก์ชัน Ansible/Netmiko (ส่วนที่ 2)"""
    
    if command == "motd":
        if message: # ถ้ามีข้อความต่อท้าย = เขียน MOTD (Ansible)
            result = ansible_final.write_motd(student_id, ip_address, message)
            if result.startswith("Error:"):
                return ('error', result)
            else:
                return ('text', result) # คืนค่า "Ok: success"
        else: # ถ้าไม่มีข้อความ = อ่าน MOTD (Netmiko)
            result = netmiko_final.read_motd(ip_address)
            if result is None:
                return ('error', f"Error: No MOTD Configured on {ip_address}")
            elif result.startswith("Error:"):
                return ('error', result)
            else:
                return ('text', result) # คืนค่า MOTD ที่อ่านได้
                
    return ('error', f"Unknown Part 2 command: {command}")


# --- 4. Main Loop (ยกเครื่องใหม่ทั้งหมด) ---
try:
    while True:
        # 1. ดึงข้อความมา 5 อันล่าสุด
        print(".", end="", flush=True)
        messages = api.messages.list(roomId=ROOM_ID, max=5) 
        
        new_messages = []
        for msg in messages:
            # 2. หาว่าเราทำข้อความนี้ไปหรือยัง?
            if msg.id == last_processed_message_id:
                break # ถ้าเจออันที่ทำแล้ว ก็หยุด (แสดงว่าที่เหลือเก่ากว่า)
            new_messages.append(msg) # เก็บข้อความใหม่ไว้

        # 3. ถ้ามีข้อความใหม่ (ที่ยังไม่เคยทำ)
        if new_messages:
            
            # 4. "กลับด้าน" list เพื่อประมวลผล "จากเก่าไปใหม่"
            for msg in reversed(new_messages):
                print(f"\nNew message detected: {msg.text}")

                # --- 5. เริ่ม Logic การแยกคำสั่ง (ใช้ 'msg' แทน 'last_message') ---
                if not msg.text.startswith("/"):
                    print("Message is not a command.")
                    continue # <-- ใช้ continue เพื่อไปทำข้อความต่อไป

                parts = msg.text.split()
                command_student_id = parts[0][1:]

                # --- 6. ตัวกรอง ID (สำคัญที่สุด) ---
                if command_student_id != MY_STUDENT_ID:
                    print(f"Ignoring command for other student: {command_student_id}")
                    continue # <-- ใช้ continue เพื่อไปทำข้อความต่อไป
                    
                print(f"Processing command for {MY_STUDENT_ID}...")
                
                msg_type = 'error' # ค่าเริ่มต้น
                content = 'Error: Invalid command structure.' # ค่าเริ่มต้น

                try:
                    # --- 7. Logic การ Parse (เหมือนเดิมทุกอย่าง) ---
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
                                msg_type, content = handle_part1_command(command, ip_address, MY_STUDENT_ID)
                        elif command == 'motd':
                            msg_type, content = handle_part2_command(command, ip_address, MY_STUDENT_ID, None)
                        else:
                            msg_type, content = ('error', f"Error: Unknown command '{command}'")

                    elif len(parts) > 3:
                        ip_address = parts[1]
                        command = parts[2].lower()
                        
                        if ip_address not in VALID_IPS:
                            msg_type, content = ('error', f"Error: Invalid IP: {ip_address}")
                        elif command == 'motd':
                            message = " ".join(parts[3:])
                            msg_type, content = handle_part2_command(command, ip_address, MY_STUDENT_ID, message)
                        else:
                            msg_type, content = ('error', 'Error: Invalid command structure.')
                    
                except Exception as e:
                    print(f"!!! UNHANDLED ERROR: {e} !!!")
                    msg_type, content = ('error', f'Internal Bot Error: {e}')

                # --- 8. ส่งคำตอบกลับ (เหมือนเดิม) ---
                if msg_type == 'file':
                    print(f"Sending file: {content}")
                    api.messages.create(roomId=ROOM_ID, files=[content], text=f"Here is the config for {MY_STUDENT_ID}")
                else:
                    print(f"Sending text: {content}")
                    api.messages.create(roomId=ROOM_ID, text=content)
                
                # --- จบการทำงานของข้อความ 'msg' นี้ ---

            # 9. "จำ" ID ของข้อความ "ใหม่ที่สุด" ที่เราเพิ่งทำไป (หลังจากวน Loop 'for msg' จบ)
            last_processed_message_id = new_messages[0].id 

        # 10. นอนแค่ 1 วินาที (เหมือนเดิม)
        time.sleep(1) 

except KeyboardInterrupt:
    print("\nBot stopped by user.")