import os
import subprocess
import tempfile
from textwrap import dedent

# ปรับให้ตรงกับเครื่องแล็บของคุณ
ROUTER_USER = "admin"
ROUTER_PASS = "cisco"
# ถ้า device ต้อง enable secret ให้เพิ่ม ANSIBLE_BECOME / SECRET ต่อไปนี้ (ถ้าไม่ใช้ก็ปล่อยว่าง)
USE_ENABLE = False
ENABLE_SECRET = "cisco"

def _write_file(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def _build_inventory(ip: str) -> str:
    """
    ใช้ network_cli ต่อ Cisco IOS-XE
    ปิด host key checking เพื่อกัน interactive prompt
    """
    lines = [
        "[routers]",
        f"{ip} ansible_connection=ansible.netcommon.network_cli "
        f"ansible_network_os=cisco.ios.ios ansible_user={ROUTER_USER} ansible_password={ROUTER_PASS} "
        "ansible_ssh_common_args='-o StrictHostKeyChecking=no'",
        "",
        "[routers:vars]",
        "ansible_python_interpreter=/usr/bin/python3",
    ]
    if USE_ENABLE:
        lines.append("ansible_become=true")
        lines.append("ansible_become_method=enable")
        lines.append(f"ansible_become_password={ENABLE_SECRET}")
    return "\n".join(lines) + "\n"

def _playbook_ios_banner(message: str) -> str:
    """
    Playbook ตัวหลัก: ใช้ cisco.ios.ios_banner (ต้องมี collection: cisco.ios)
    """
    return dedent(f"""\
    - name: Configure MOTD banner via ios_banner
      hosts: routers
      gather_facts: no
      collections:
        - cisco.ios
      tasks:
        - name: Set MOTD banner (present)
          ios_banner:
            banner: motd
            text: "{message}"
            state: present
    """).strip() + "\n"

def _playbook_ios_config_fallback(message: str) -> str:
    """
    Fallback: ถ้าไม่มี collection cisco.ios ให้ใช้ ios_config แบบสั่ง command ตรง ๆ
    ใช้ delimiter @ (ต้องมั่นใจว่าไม่มีตัว @ ในข้อความ)
    """
    # เลือก delimiter ที่ไม่มีในข้อความ
    delim = "@"
    if delim in message:
        delim = "#"
        if delim in message:
            delim = "$"

    # สั่งคำสั่งแบบ block: banner motd <delim> <text> <delim>
    return dedent(f"""\
    - name: Configure MOTD banner via ios_config (fallback)
      hosts: routers
      gather_facts: no
      collections:
        - ansible.netcommon
        - cisco.ios
      tasks:
        - name: Set MOTD banner using ios_config
          cisco.ios.ios_config:
            lines:
              - "banner motd {delim}{message}{delim}"
    """).strip() + "\n"

def write_motd(student_id: str, ip: str, message: str) -> str:
    """
    ใช้ Ansible ตั้งค่า MOTD ให้เป็นข้อความที่รับมา
    คืนค่า:
      "Ok: success" ถ้าสำเร็จ
      "Error: <รายละเอียด>" ถ้าล้มเหลว
    """
    # กันเคสกลุ่ม user ส่งว่าง ๆ มา
    message = (message or "").strip()
    if not message:
        return "Error: Empty MOTD"

    # เตรียม temp dir สำหรับ inventory + playbook
    tmpdir = tempfile.mkdtemp(prefix="ans_motd_")
    inv_path = os.path.join(tmpdir, "hosts.ini")
    pb1_path = os.path.join(tmpdir, "pb_banner.yml")
    pb2_path = os.path.join(tmpdir, "pb_fallback.yml")

    _write_file(inv_path, _build_inventory(ip))
    _write_file(pb1_path, _playbook_ios_banner(message))
    _write_file(pb2_path, _playbook_ios_config_fallback(message))

    env = os.environ.copy()
    env["ANSIBLE_HOST_KEY_CHECKING"] = "False"  # ไม่ถาม host key
    # ทำให้ output สั้นลง (ถ้าอยากอ่าน JSON ก็ใส่ stdout callback json ได้)
    # env["ANSIBLE_STDOUT_CALLBACK"] = "yaml"

    # 1) ลองวิธีหลัก ios_banner ก่อน
    try:
        res = subprocess.run(
            ["ansible-playbook", "-i", inv_path, pb1_path, "-l", ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=120,
        )
        if res.returncode == 0:
            return "Ok: success"
        # ถ้า error เกี่ยวกับ collection/module ไม่เจอ ค่อย fallback
        txt = (res.stdout + "\n" + res.stderr).lower()
        if "couldn't resolve module/action 'ios_banner'" in txt or \
           "collection cisco.ios was not found" in txt or \
           "the task includes an option with an undefined variable" in txt or \
           "module not found" in txt:
            # ไป fallback
            pass
        else:
            return f"Error: {res.stderr.strip() or res.stdout.strip()}"
    except Exception as e:
        # ถ้ารันไม่ขึ้น ลอง fallback ต่อ
        pass

    # 2) Fallback: ios_config
    try:
        res2 = subprocess.run(
            ["ansible-playbook", "-i", inv_path, pb2_path, "-l", ip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            timeout=120,
        )
        if res2.returncode == 0:
            return "Ok: success"
        return f"Error: {res2.stderr.strip() or res2.stdout.strip()}"
    except Exception as e2:
        return f"Error: {str(e2)}"
    
