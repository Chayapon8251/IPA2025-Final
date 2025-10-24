from ncclient import manager
from ncclient.xml_ import new_ele, sub_ele

# ข้อมูลเชื่อมต่อ
ROUTER_USER = "admin"
ROUTER_PASS = "cisco"
ROUTER_PORT = 830 # Port มาตรฐานของ NETCONF

def get_netconf_connection(router_ip):
    """สร้างการเชื่อมต่อ NETCONF"""
    try:
        conn = manager.connect(
            host=router_ip,
            port=ROUTER_PORT,
            username=ROUTER_USER,
            password=ROUTER_PASS,
            hostkey_verify=False, # ปิดการตรวจสอบ Hostkey
            device_params={'name': 'csr'},
            timeout=15
        )
        return conn
    except Exception as e:
        print(f"NETCONF Connection Error: {e}")
        return None

def get_interface_status(router_ip, interface_name):
    """ตรวจสอบสถานะ Interface (NETCONF) - (เวอร์ชันแก้ไข Bug)"""
    
    # 1. สร้าง XML Filter เพื่อขอข้อมูลเฉพาะ Interface นี้
    interface_filter = f"""
    <filter>
      <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
        <interface>
          <name>{interface_name}</name>
        </interface>
      </interfaces>
    </filter>
    """
    
    conn = get_netconf_connection(router_ip)
    if not conn:
        return "error"
        
    try:
        # 2. ส่ง <get-config>
        reply_str = conn.get_config(source='running', filter=interface_filter).data_xml
        
        # --- 3. นี่คือ Logic ที่แก้ไขแล้ว ---
        
        # 3.1 เช็คว่ามี Interface นี้อยู่หรือไม่ (เช็คจาก name)
        if f"<name>{interface_name}</name>" in reply_str:
            # 3.2 ถ้ามี, ค่อยเช็คว่ามัน enabled หรือ disabled
            if "<enabled>true</enabled>" in reply_str:
                return "exists_enabled"
            else:
                return "exists_disabled"
        else:
            # 3.3 ถ้าไม่เจอ name, ก็คือ "not_exists"
            return "not_exists"
            
    except Exception as e:
        print(f"NETCONF get_interface_status Error: {e}")
        return "error"
    finally:
        if conn:
            conn.close_session()

def create_interface(router_ip, student_id):
    """สร้าง Loopback Interface (NETCONF)"""
    interface_name = f"Loopback{student_id}"
    
    # 1. ตรวจสอบก่อน (ใช้ฟังก์ชันของตัวเอง)
    status = get_interface_status(router_ip, interface_name)
    if status != "not_exists":
        return f"Cannot create: Interface {interface_name}"

    # 2. คำนวณ IP
    last_3_digits = student_id[-3:]
    x = int(last_3_digits[0])
    y = int(last_3_digits[1:])
    ip_address = f"172.{x}.{y}.1"
    
    # 3. สร้าง XML Payload
    config_xml = f"""
    <config>
      <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
        <interface>
          <name>{interface_name}</name>
          <type xmlns:ianaift="urn:ietf:params:xml:ns:yang:iana-if-type">ianaift:softwareLoopback</type>
          <enabled>true</enabled>
          <ipv4 xmlns="urn:ietf:params:xml:ns:yang:ietf-ip">
            <address>
              <ip>{ip_address}</ip>
              <netmask>255.255.255.0</netmask>
            </address>
          </ipv4>
        </interface>
      </interfaces>
    </config>
    """
    
    conn = get_netconf_connection(router_ip)

    if not conn:
        return "Error: NETCONF Connection Failed"
        
    try:
        # --- (แก้ไข!) ---
        reply = conn.edit_config(target='running', config=config_xml, default_operation='merge')
        reply_str = str(reply)

        if reply.ok:
            return f"Interface {interface_name} is created successfully using Netconf"
        else:
            print(f"NETCONF create_interface Error: Router rejected config. Reply: {reply_str}")
            return f"Error: Router rejected config for {interface_name}."
        # --- (จบส่วนแก้ไข) ---
    except Exception as e:
        return f"NETCONF create_interface Exception: {e}"
    finally:
        if conn:
            conn.close_session()

def delete_interface(router_ip, student_id):
    """ลบ Loopback Interface (NETCONF)"""
    interface_name = f"Loopback{student_id}"
    
    # 1. ตรวจสอบก่อน
    status = get_interface_status(router_ip, interface_name)
    if status == "not_exists":
        return f"Cannot delete: Interface {interface_name}"

    # 2. สร้าง XML Payload สำหรับลบ
    config_xml = f"""
    <config>
      <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
        <interface operation="delete">
          <name>{interface_name}</name>
        </interface>
      </interfaces>
    </config>
    """
    
    conn = get_netconf_connection(router_ip)
    if not conn:
        return "Error: NETCONF Connection Failed"
        
    try:
        # --- (แก้ไข!) ---
        reply = conn.edit_config(target='running', config=config_xml)
        reply_str = str(reply)

        if reply.ok:
            return f"Interface {interface_name} is deleted successfully using Netconf"
        else:
            print(f"NETCONF delete_interface Error: Router rejected config. Reply: {reply_str}")
            return f"Error: Router rejected config for {interface_name}."
        # --- (จบส่วนแก้ไข) ---
    except Exception as e:
        return f"NETCONF delete_interface Error: {e}"
    finally:
        if conn:
            conn.close_session()

def set_interface_state(router_ip, student_id, enabled: bool):
    """Enable/Disable Interface (NETCONF)"""
    interface_name = f"Loopback{student_id}"
    
    # 1. ตรวจสอบก่อน
    status = get_interface_status(router_ip, interface_name)
    if status == "not_exists":
        if enabled:
            return f"Cannot enable: Interface {interface_name}"
        else:
            return f"Cannot shutdown: Interface {interface_name}"
            
    # 2. สร้าง XML Payload
    config_xml = f"""
    <config>
      <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
        <interface>
          <name>{interface_name}</name>
          <enabled>{'true' if enabled else 'false'}</enabled>
        </interface>
      </interfaces>
    </config>
    """
    
    conn = get_netconf_connection(router_ip)
    if not conn:
        return "Error: NETCONF Connection Failed"
        
    try:
        # --- (แก้ไข!) ---
        reply = conn.edit_config(target='running', config=config_xml, default_operation='merge')
        reply_str = str(reply)

        if reply.ok:
            if enabled:
                return f"Interface {interface_name} is enabled successfully using Netconf"
            else:
                return f"Interface {interface_name} is shutdowned successfully using Netconf"
        else:
            print(f"NETCONF set_interface_state Error: Router rejected config. Reply: {reply_str}")
            return f"Error: Router rejected config for {interface_name}."
        # --- (จบส่วนแก้ไข) ---
    except Exception as e:
        return f"NETCONF set_interface_state Error: {e}"
    finally:
        if conn:
            conn.close_session()