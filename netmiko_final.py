from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException  # <--- 1. Import Error นี้เข้ามา
from pprint import pprint
import re

username = "admin"
password = "cisco"


def read_motd(router_ip):
    """อ่าน MOTD Banner (Netmiko)"""
    device_params = {
        "device_type": "cisco_xe", 
        "ip": router_ip,
        "username": username,
        "password": password,
        "conn_timeout": 20
    }
    
    try:
        with ConnectHandler(**device_params) as ssh:
            # 1. ดึง config ส่วน banner motd
            # เราใช้ 'show run | section' จะได้ผลลัพธ์ที่สะอาดกว่า
            result = ssh.send_command("show running-config | section banner motd")
            
            # 2. ค้นหาข้อความระหว่างตัวคั่น (เช่น ^C ... ^C)
            # 's' flag (re.DOTALL) ทำให้ '.' จับคู่ newline (เผื่อ MOTD หลายบรรทัด)
            match = re.search(r'banner motd \^(.*?)\^', result, re.DOTALL)
            
            if match:
                # 3. ถ้าเจอ ให้คืนค่าข้อความที่อยู่ข้างใน (กลุ่มที่ 1)
                message = match.group(1).strip() # .strip() เพื่อลบช่องว่าง/newline หน้า-หลัง
                return message
            else:
                # 4. ถ้าไม่เจอ (ไม่มี MOTD)
                return None
       
    except NetmikoTimeoutException:  # <--- 3. ดักจับ Error ถ้า Timeout
        print(f"ERROR: Connection timed out to {router_ip}")
        # คืนค่าเป็น String Error (Bot หลักจะเอาไปส่งใน Webex)
        return f"Error: Connection timed out to {router_ip}"
    except Exception as e:  # <--- 4. ดักจับ Error อื่นๆ (เผื่อไว้)
        print(f"ERROR: An unknown error occurred: {e}")
        return f"Error: An unknown error occurred: {e}"

# def gigabit_status(router_ip):
    
#     device_params = {
#         "device_type": "cisco_xe", 
#         "ip": router_ip,
#         "username": username,
#         "password": password,
#         "conn_timeout": 15
#     }
    
#     try:  # <--- 2. เริ่ม try คลุมทั้งหมด
#         ans = ""
#         with ConnectHandler(**device_params) as ssh:
#             up = 0
#             down = 0
#             admin_down = 0
            
#             result = ssh.send_command("show interfaces", use_textfsm=True)
            
#             for status in result:
#                 if 'GigabitEthernet' in status['interface']:
#                     interface_name = status['interface']
#                     link_status = status['link_status']
#                     protocol_status = status['protocol_status']
                    
#                     status_str = ""
                    
#                     if link_status == "up" and protocol_status == "up":
#                         status_str = "up"
#                         up += 1
#                     elif link_status == "administratively down":
#                         status_str = "administratively down"
#                         admin_down += 1
#                     else: 
#                         status_str = "down"
#                         down += 1
                    
#                     ans += f"{interface_name} {status_str}, "

#             ans = ans.strip(', ')
#             ans += f" -> {up} up, {down} down, {admin_down} administratively down"
            
#             pprint(ans)
#             return ans