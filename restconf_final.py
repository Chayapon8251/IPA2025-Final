import requests
import json
from requests.auth import HTTPBasicAuth

# ปิดการแจ้งเตือนเรื่อง InsecureRequestWarning เพราะเราจะใช้ verify=False
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

ROUTER_USER = "admin"
ROUTER_PASS = "cisco"

def get_interface_status(router_ip, interface_name):
    """
    ตรวจสอบสถานะของ interface
    Returns:
        - "exists_enabled" ถ้ามีและ up
        - "exists_disabled" ถ้ามีและ down
        - "not_exists" ถ้าไม่มี
        - "error" ถ้าเกิดข้อผิดพลาด
    """
    url = f"https://{router_ip}/restconf/data/ietf-interfaces:interfaces/interface={interface_name}"
    headers = {'Accept': 'application/yang-data+json'}
    auth = HTTPBasicAuth(ROUTER_USER, ROUTER_PASS)

    try:
        response = requests.get(url, headers=headers, auth=auth, verify=False)
        if response.status_code == 200:
            data = response.json()

            is_enabled = data.get("ietf-interfaces:interface", {}).get("enabled", False)

            if is_enabled:
                return "exists_enabled"
            else:
                return "exists_disabled"
        elif response.status_code == 404:
            return "not_exists"
        else:
            return "error"
    except requests.exceptions.RequestException as e:
        print(f"Error checking interface: {e}")
        return "error"

def create_interface(router_ip, student_id):
    """สร้าง Loopback interface"""
    interface_name = f"Loopback{student_id}"
    
    # 1. ตรวจสอบก่อนว่ามี interface นี้หรือยัง
    status = get_interface_status(router_ip, interface_name)
    if status != "not_exists":
        return f"Cannot create: Interface {interface_name}"

    # 2. คำนวณ IP Address
    last_3_digits = student_id[-3:] # "123"
    x = int(last_3_digits[0]) # 1
    y = int(last_3_digits[1:]) # 23
    ip_address = f"172.{x}.{y}.1"
    
    # 3. สร้าง Payload และส่ง Request
    url = f"https://{router_ip}/restconf/data/ietf-interfaces:interfaces"
    headers = {'Content-Type': 'application/yang-data+json'}
    auth = HTTPBasicAuth(ROUTER_USER, ROUTER_PASS)

    payload = {
        "ietf-interfaces:interface": {
            "name": interface_name,
            "description": f"Created by student {student_id}",
            "type": "iana-if-type:softwareLoopback",
            "enabled": True,
            "ietf-ip:ipv4": {
                "address": [
                    {
                        "ip": ip_address,
                        "netmask": "255.255.255.0"
                    }
                ]
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, auth=auth, data=json.dumps(payload), verify=False)
        if response.status_code == 201: # 201 Created
            return f"Interface {interface_name} is created successfully"
        else:
            return f"Failed to create. Status: {response.status_code}, Body: {response.text}"
    except requests.exceptions.RequestException as e:
        return f"Error creating interface: {e}"

def delete_interface(router_ip, student_id):
    """ลบ Loopback interface"""
    interface_name = f"Loopback{student_id}"
    
    # 1. ตรวจสอบก่อนว่ามี interface หรือไม่
    status = get_interface_status(router_ip, interface_name)
    if status == "not_exists":
        return f"Cannot delete: Interface {interface_name}"

    # 2. ถ้ามี ให้ลบ
    url = f"https://{router_ip}/restconf/data/ietf-interfaces:interfaces/interface={interface_name}"
    headers = {'Accept': 'application/yang-data+json'}
    auth = HTTPBasicAuth(ROUTER_USER, ROUTER_PASS)

    try:
        response = requests.delete(url, headers=headers, auth=auth, verify=False)
        
        if response.status_code == 204: # 204 No Content (คือสำเร็จ)
            return f"Interface {interface_name} is deleted successfully"
        else:
            return f"Delete failed: {response.status_code} {response.text}"
    except requests.exceptions.RequestException as e:
        return f"Error deleting interface: {e}"


def set_interface_state(router_ip, student_id, enabled: bool):
    """Enable (no shutdown) หรือ Disable (shutdown) interface"""
    interface_name = f"Loopback{student_id}"
    
    # 1. ตรวจสอบก่อนว่ามี interface หรือไม่
    status = get_interface_status(router_ip, interface_name)
    if status == "not_exists":
        if enabled:
            return f"Cannot enable: Interface {interface_name}"
        else:
            return f"Cannot shutdown: Interface {interface_name}"

    # 2. ถ้ามี ให้ส่งคำสั่ง
    url = f"https://{router_ip}/restconf/data/ietf-interfaces:interfaces/interface={interface_name}/enabled"
    headers = {'Content-Type': 'application/yang-data+json', 'Accept': 'application/yang-data+json'}
    auth = HTTPBasicAuth(ROUTER_USER, ROUTER_PASS)
    
    # Payload ตาม YANG Model (ietf-interfaces)
    payload = {"ietf-interfaces:enabled": enabled}

    try:
        response = requests.put(url, headers=headers, auth=auth, data=json.dumps(payload), verify=False)
        
        if response.status_code == 204: # 204 No Content (คือสำเร็จ)
            if enabled:
                return f"Interface {interface_name} is enabled successfully"
            else:
                return f"Interface {interface_name} is shutdowned successfully"
        else:
            return f"Set state failed: {response.status_code} {response.text}"
    except requests.exceptions.RequestException as e:
        return f"Error setting interface state: {e}"