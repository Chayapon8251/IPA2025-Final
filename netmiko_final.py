import re
from netmiko import ConnectHandler

ROUTER_USER = "admin"
ROUTER_PASS = "cisco"
DEVICE_TYPE = "cisco_ios"

def _connect(ip: str):
    return ConnectHandler(
        device_type=DEVICE_TYPE,
        host=ip,
        username=ROUTER_USER,
        password=ROUTER_PASS,
        # secret=ROUTER_PASS,  # ถ้าต้อง enter enable ให้ uncomment
        fast_cli=False,
    )

def _parse_banner_from_run(run_text: str):
    """
    ดึงข้อความ banner motd จาก show running-config
    รูปแบบทั่วไป:
      banner motd ^<ข้อความหลายบรรทัด>^
    หรือใช้ delimiter ตัวอื่น เช่น @, #, $, !
    """
    # หา 'banner motd <delim>...<delim>' แบบ DOTALL
    m = re.search(r"^banner\s+motd\s+(\S)\n?(.*?)\1\s*$",
                  run_text, flags=re.MULTILINE | re.DOTALL)
    if not m:
        # บางเครื่องอาจขึ้นบรรทัดเดียว: banner motd ^ข้อความ^
        m = re.search(r"^banner\s+motd\s+(\S)(.*?)\1\s*$",
                      run_text, flags=re.MULTILINE | re.DOTALL)
    if not m:
        return None

    body = m.group(2)
    # ทำความสะอาด CR/LF และช่องว่างส่วนเกินหัว-ท้าย
    body = body.replace("\r", "")
    body = body.strip("\n")
    return body.strip()

def read_motd(ip: str) -> str:
    """
    คืนค่า:
      - ข้อความ MOTD (string) เมื่อพบ
      - "Error: No MOTD Configured" เมื่อไม่พบ
      - "Error: <รายละเอียด>" เมื่อมีข้อผิดพลาด
    """
    try:
        conn = _connect(ip)
        # ถ้ามี enable: conn.enable()

        # 1) ลอง show banner motd (ถ้ามีจะตอบข้อความตรง ๆ)
        out = conn.send_command("show banner motd", expect_string=r"#|\$")
        if out and "No banner configured" not in out and "% No" not in out:
            # ทำความสะอาด
            msg = out.strip()
            # บางรุ่นอาจใส่ prompt ปิดท้าย ตัดบรรทัด prompt ออกถ้าจำเป็น
            return msg

        # 2) fallback: อ่านจาก show running-config แล้ว regex เอาเฉพาะตัวข้อความ
        run = conn.send_command("show running-config", expect_string=r"#|\$", delay_factor=2)
        motd = _parse_banner_from_run(run)
        if motd:
            return motd

        return "Error: No MOTD Configured"

    except Exception as e:
        return f"Error: {e}"
