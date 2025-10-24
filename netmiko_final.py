from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException  # <--- 1. Import Error นี้เข้ามา
from pprint import pprint

username = "admin"
password = "cisco"

def gigabit_status(router_ip):
    
    device_params = {
        "device_type": "cisco_xe", 
        "ip": router_ip,
        "username": username,
        "password": password,
        "conn_timeout": 15
    }
    
    try:  # <--- 2. เริ่ม try คลุมทั้งหมด
        ans = ""
        with ConnectHandler(**device_params) as ssh:
            up = 0
            down = 0
            admin_down = 0
            
            result = ssh.send_command("show interfaces", use_textfsm=True)
            
            for status in result:
                if 'GigabitEthernet' in status['interface']:
                    interface_name = status['interface']
                    link_status = status['link_status']
                    protocol_status = status['protocol_status']
                    
                    status_str = ""
                    
                    if link_status == "up" and protocol_status == "up":
                        status_str = "up"
                        up += 1
                    elif link_status == "administratively down":
                        status_str = "administratively down"
                        admin_down += 1
                    else: 
                        status_str = "down"
                        down += 1
                    
                    ans += f"{interface_name} {status_str}, "

            ans = ans.strip(', ')
            ans += f" -> {up} up, {down} down, {admin_down} administratively down"
            
            pprint(ans)
            return ans
            
    except NetmikoTimeoutException:  # <--- 3. ดักจับ Error ถ้า Timeout
        print(f"ERROR: Connection timed out to {router_ip}")
        # คืนค่าเป็น String Error (Bot หลักจะเอาไปส่งใน Webex)
        return f"Error: Connection timed out to {router_ip}"
    except Exception as e:  # <--- 4. ดักจับ Error อื่นๆ (เผื่อไว้)
        print(f"ERROR: An unknown error occurred: {e}")
        return f"Error: An unknown error occurred: {e}"