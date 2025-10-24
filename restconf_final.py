import json
import requests
from requests.auth import HTTPBasicAuth
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# ปิดคำเตือนเรื่อง cert self-signed
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

ROUTER_USER = "admin"
ROUTER_PASS = "cisco"
TIMEOUT = 15  # วินาที

# เตรียม Session ใช้ซ้ำทุกคำขอ
_session = requests.Session()
_session.verify = False  # สำคัญ! กัน SSL: CERTIFICATE_VERIFY_FAILED
_session.auth = HTTPBasicAuth(ROUTER_USER, ROUTER_PASS)
_session.headers.update({
    "Accept": "application/yang-data+json"
})

def _if_res_path(router_ip: str, interface_name: str) -> str:
    """
    เส้นทาง resource อินเทอร์เฟซหนึ่งตัว (RESTCONF data resource)
    """
    return f"https://{router_ip}/restconf/data/ietf-interfaces:interfaces/interface={interface_name}"

def _interfaces_collection(router_ip: str) -> str:
    """
    เส้นทางคอลเลกชัน interfaces (เผื่อใช้ POST ถ้าต้องการ)
    """
    return f"https://{router_ip}/restconf/data/ietf-interfaces:interfaces"

def get_interface_status(router_ip, interface_name):
    """
    ตรวจสอบสถานะของ interface
    Returns:
        - "exists_enabled"
        - "exists_disabled"
        - "not_exists"
        - "error"
    """
    url = _if_res_path(router_ip, interface_name)
    try:
        r = _session.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"[RESTCONF][status] Request error: {e}")
        return "error"

    if r.status_code == 200:
        try:
            data = r.json()
        except ValueError:
            print(f"[RESTCONF][status] Invalid JSON: {r.text[:200]}")
            return "error"

        # JSON ตาม YANG ietf-interfaces
        iface = data.get("ietf-interfaces:interface") or data.get("interface")
        if not iface:
            # อุปกรณ์ตอบ 200 แต่ body แปลก ๆ
            print(f"[RESTCONF][status] Unexpected body: {data}")
            return "error"

        enabled = iface.get("enabled")
        # หมายเหตุ: บางรุ่นหากไม่ใส่ enabled จะหมายถึง true (ขึ้นกับ model/device)
        if enabled is None or enabled is True:
            return "exists_enabled"
        return "exists_disabled"

    elif r.status_code == 404:
        return "not_exists"
    else:
        print(f"[RESTCONF][status] HTTP {r.status_code}: {r.text[:300]}")
        return "error"

def _calc_ip_from_student_id(student_id: str):
    last_3 = student_id[-3:]
    x = int(last_3[0])
    y = int(last_3[1:])
    return f"172.{x}.{y}.1", "255.255.255.0"

def create_interface(router_ip, student_id):
    """
    สร้าง Loopback interface ด้วย PUT ไปที่ resource โดยตรง
    (idempotent, คาดเดาได้)
    """
    interface_name = f"Loopback{student_id}"

    # เช็กก่อน
    status = get_interface_status(router_ip, interface_name)
    if status not in ("not_exists", "error"):
        return f"Cannot create: Interface {interface_name}"

    ip_address, netmask = _calc_ip_from_student_id(student_id)

    url = _if_res_path(router_ip, interface_name)
    payload = {
        "ietf-interfaces:interface": {
            "name": interface_name,
            "description": f"Created by student {student_id}",
            "type": "iana-if-type:softwareLoopback",
            "enabled": True,
            "ietf-ip:ipv4": {
                "address": [
                    {"ip": ip_address, "netmask": netmask}
                ]
            }
        }
    }

    try:
        r = _session.put(
            url,
            headers={"Content-Type": "application/yang-data+json"},
            data=json.dumps(payload),
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        return f"Error creating interface (Restconf): {e}"

    # 201 Created (หรือบางรุ่น 204 No Content ถ้า replace ได้)
    if r.status_code in (200, 201, 204):
        return f"Interface {interface_name} is created successfully using Restconf"

    # 409 Conflict => มีอยู่แล้ว (ถือว่าสร้างสำเร็จหรือแจ้งเตือนตามตรง)
    if r.status_code == 409:
        return f"Cannot create: Interface {interface_name}"

    # อื่น ๆ แสดงข้อความจากอุปกรณ์ (ถ้ามี)
    return f"Error: Router rejected config ({r.status_code}) for {interface_name}. {r.text[:300]}"

def delete_interface(router_ip, student_id):
    interface_name = f"Loopback{student_id}"

    # เช็กก่อน
    status = get_interface_status(router_ip, interface_name)
    if status == "not_exists":
        return f"Cannot delete: Interface {interface_name}"

    url = _if_res_path(router_ip, interface_name)
    try:
        r = _session.delete(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        return f"Error deleting interface (Restconf): {e}"

    if r.status_code == 204:
        return f"Interface {interface_name} is deleted successfully using Restconf"

    if r.status_code == 404:
        return f"Cannot delete: Interface {interface_name}"

    return f"Delete failed: {r.status_code} {r.text[:300]}"

def set_interface_state(router_ip, student_id, enabled: bool):
    """
    เปิด/ปิด (enabled leaf) ด้วย PUT ไปยัง leaf-resource โดยตรง
    """
    interface_name = f"Loopback{student_id}"

    # เช็กก่อน
    status = get_interface_status(router_ip, interface_name)
    if status == "not_exists":
        if enabled:
            return f"Cannot enable: Interface {interface_name}"
        else:
            return f"Cannot shutdown: Interface {interface_name}"

    url = _if_res_path(router_ip, interface_name) + "/enabled"
    payload = {"ietf-interfaces:enabled": bool(enabled)}

    try:
        r = _session.put(
            url,
            headers={"Content-Type": "application/yang-data+json"},
            data=json.dumps(payload),
            timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        return f"Error setting interface state: {e}"

    if r.status_code in (200, 204):
        return (
            f"Interface {interface_name} is enabled successfully using Restconf"
            if enabled
            else f"Interface {interface_name} is shutdowned successfully using Restconf"
        )

    if r.status_code == 404:
        return f"Set state failed: Interface {interface_name} not found"

    return f"Set state failed: {r.status_code} {r.text[:300]}"
