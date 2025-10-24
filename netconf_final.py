from ncclient import manager
from lxml import etree
from ncclient.operations.rpc import RPCError

# ------------------------------
# ค่าคงที่เชื่อมต่ออุปกรณ์
# ------------------------------
ROUTER_USER = "admin"
ROUTER_PASS = "cisco"
ROUTER_PORT = 830

# YANG namespaces
NS_NATIVE = {"n": "http://cisco.com/ns/yang/Cisco-IOS-XE-native"}
NS_IETF = {"if": "urn:ietf:params:xml:ns:yang:ietf-interfaces"}
NS_NC = {"nc": "urn:ietf:params:xml:ns:netconf:base:1.0"}


# ------------------------------
# Utilities
# ------------------------------
def _parse_loop_name(interface_name_or_id: str):
    """
    รับค่าได้ทั้ง:
      - "Loopback66070039"
      - "66070039"
    คืนค่า: (loop_num:int, if_name_str:str) เช่น (66070039, "Loopback66070039")
    """
    s = interface_name_or_id.strip()
    if s.lower().startswith("loopback"):
        num = s[len("Loopback") :]
    else:
        num = s
        s = f"Loopback{num}"
    loop_num = int(num)  # ต้องเป็นตัวเลขล้วนสำหรับโมเดล native
    return loop_num, s


def _calc_ip_from_student_id(student_id: str):
    """
    ตามกติกาเดิมของคุณ:
      last_3_digits = student_id[-3:]
      x = int(last_3_digits[0])
      y = int(last_3_digits[1:])
      ip = f"172.{x}.{y}.1/24"
    """
    last_3 = student_id[-3:]
    x = int(last_3[0])
    y = int(last_3[1:])
    ip = f"172.{x}.{y}.1"
    mask = "255.255.255.0"
    return ip, mask


# ------------------------------
# NETCONF Connection
# ------------------------------
def get_netconf_connection(router_ip):
    try:
        conn = manager.connect(
            host=router_ip,
            port=ROUTER_PORT,
            username=ROUTER_USER,
            password=ROUTER_PASS,
            hostkey_verify=False,
            device_params={"name": "csr"},
            allow_agent=False,
            look_for_keys=False,
            timeout=20,
        )
        return conn
    except Exception as e:
        print(f"NETCONF Connection Error: {e}")
        return None


# ------------------------------
# Safe get_config helpers (รองรับอุปกรณ์ที่ไม่ยอมรับ type="subtree")
# ------------------------------
def _safe_get_config_subtree(conn, inner_xml: str):
    """
    พยายามเรียก get_config โดยใช้ filter แบบ tuple ('subtree', inner_xml)
    ถ้าอุปกรณ์ร้องว่า bad-attribute type/bad-element filter จะ fallback
    ไปใช้ <filter> ธรรมดา (ไม่มี type)
    """
    try:
        # วิธีมาตรฐานของ ncclient
        return conn.get_config(source="running", filter=("subtree", inner_xml))
    except Exception as e:
        msg = str(e)
        # fallback เมื่อโดน bad-attribute type / bad-element filter
        if "bad-attribute" in msg and "type" in msg or "bad-element" in msg and "filter" in msg:
            try:
                wrapper = f"<filter>{inner_xml}</filter>"
                return conn.get_config(source="running", filter=wrapper)
            except Exception as e2:
                raise e2
        raise e


# ------------------------------
# Read status (Robust)
# ------------------------------
def get_interface_status(router_ip, interface_name: str):
    """
    คืนค่า: "exists_enabled" | "exists_disabled" | "not_exists" | "error"
    กลยุทธ์:
      1) เช็ก native ก่อน: /native/interface/Loopback[name=<num>]
         - ถ้าไม่มี => not_exists
         - ถ้ามีและมี <shutdown/> => exists_disabled
         - ถ้ามีและไม่มี <shutdown/> => exists_enabled
      2) Fallback (ถ้า native ไม่เจอ): ใช้ IETF ietf-interfaces
    """
    loop_num, if_name = _parse_loop_name(interface_name)
    conn = get_netconf_connection(router_ip)
    if not conn:
        return "error"

    try:
        # (A) Native check
        native_inner = f"""
          <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
            <interface>
              <Loopback>
                <name>{loop_num}</name>
                <shutdown/>
              </Loopback>
            </interface>
          </native>
        """
        rep = _safe_get_config_subtree(conn, native_inner)
        root = etree.fromstring(rep.xml.encode())

        loop_nodes = root.xpath(
            "//n:native/n:interface/n:Loopback[n:name=$n]",
            namespaces=NS_NATIVE,
            n=str(loop_num),
        )
        if loop_nodes:
            # มีอินเทอร์เฟซแล้ว
            has_shutdown = (
                loop_nodes[0].find("{http://cisco.com/ns/yang/Cisco-IOS-XE-native}shutdown")
                is not None
            )
            return "exists_disabled" if has_shutdown else "exists_enabled"

        # (B) IETF fallback
        ietf_inner = f"""
          <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
            <interface>
              <name>{if_name}</name>
              <enabled/>
            </interface>
          </interfaces>
        """
        rep2 = _safe_get_config_subtree(conn, ietf_inner)
        r2 = etree.fromstring(rep2.xml.encode())

        nodes = r2.xpath(
            "//if:interfaces/if:interface[if:name=$n]",
            namespaces=NS_IETF,
            n=if_name,
        )
        if not nodes:
            return "not_exists"

        en = nodes[0].find("{urn:ietf:params:xml:ns:yang:ietf-interfaces}enabled")
        if en is None or (en.text or "").strip().lower() == "true":
            return "exists_enabled"
        else:
            return "exists_disabled"

    except Exception as e:
        print(f"NETCONF get_interface_status Error: {e}")
        return "error"
    finally:
        try:
            conn.close_session()
        except Exception:
            pass


# ------------------------------
# Create Loopback (Cisco Native)
# ------------------------------
def create_interface(router_ip, student_id: str):
    """
    สร้าง Loopback<student_id> โดยใช้ native:
      native/interface/Loopback[name=<num>]/ip/address/primary
    """
    loop_num, _ = _parse_loop_name(f"Loopback{student_id}")
    ip, mask = _calc_ip_from_student_id(student_id)

    # ตรวจสอบก่อน — ถ้าเช็กแล้ว error ให้ “ลองสร้างต่อ” ได้
    pre = get_interface_status(router_ip, f"Loopback{student_id}")
    if pre not in ("not_exists", "error"):
        return f"Cannot create: Interface Loopback{student_id}"

    conn = get_netconf_connection(router_ip)
    if not conn:
        return "Error: NETCONF Connection Failed"

    config_xml = f"""
    <config>
      <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
        <interface>
          <Loopback>
            <name>{loop_num}</name>
            <description>created-by-netconf</description>
            <ip>
              <address>
                <primary>
                  <address>{ip}</address>
                  <mask>{mask}</mask>
                </primary>
              </address>
            </ip>
          </Loopback>
        </interface>
      </native>
    </config>
    """

    try:
        rep = conn.edit_config(target="running", config=config_xml, default_operation="merge")
        if rep.ok:
            return f"Interface Loopback{student_id} is created successfully using Netconf"
        else:
            return f"Error: Router rejected config for Loopback{student_id}."
    except Exception as e:
        return f"NETCONF create_interface Exception: {e}"
    finally:
        try:
            conn.close_session()
        except Exception:
            pass


# ------------------------------
# Delete Loopback (Cisco Native)
# ------------------------------
def delete_interface(router_ip, student_id: str):
    loop_num, _ = _parse_loop_name(f"Loopback{student_id}")

    # ตรวจสอบก่อน — ถ้าเช็กแล้ว error ให้ “ลองลบต่อ” ได้
    pre = get_interface_status(router_ip, f"Loopback{student_id}")
    if pre == "not_exists":
        return f"Cannot delete: Interface Loopback{student_id}"

    conn = get_netconf_connection(router_ip)
    if not conn:
        return "Error: NETCONF Connection Failed"

    config_xml = f"""
    <config>
      <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
              xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
        <interface>
          <Loopback nc:operation="delete">
            <name>{loop_num}</name>
          </Loopback>
        </interface>
      </native>
    </config>
    """

    try:
        rep = conn.edit_config(target="running", config=config_xml)
        if rep.ok:
            return f"Interface Loopback{student_id} is deleted successfully using Netconf"
        else:
            return f"Error: Router rejected config for Loopback{student_id}."
    except Exception as e:
        return f"NETCONF delete_interface Error: {e}"
    finally:
        try:
            conn.close_session()
        except Exception:
            pass


# ------------------------------
# Enable / Disable (Cisco Native)
# ------------------------------
def set_interface_state(router_ip, student_id: str, enabled: bool):
    """
    ใช้ native: <shutdown/> เป็นตัวคุมสถานะ
      - disable: เพิ่ม <shutdown/>
      - enable: ลบ <shutdown/> (ถ้าไม่มีแล้ว ให้ถือว่าสำเร็จ)
    ทำให้ idempotent: เช็กก่อน-ทำ-เช็กหลัง และ ignore data-missing สำหรับเคส enable
    """
    loop_num, _ = _parse_loop_name(f"Loopback{student_id}")

    # 1) Pre-check
    pre = get_interface_status(router_ip, f"Loopback{student_id}")
    if pre == "not_exists":
        return (
            f"Cannot enable: Interface Loopback{student_id}"
            if enabled
            else f"Cannot shutdown: Interface Loopback{student_id}"
        )
    if enabled and pre == "exists_enabled":
        return f"Interface Loopback{student_id} is enabled successfully using Netconf (already)"
    if (not enabled) and pre == "exists_disabled":
        return f"Interface Loopback{student_id} is shutdowned successfully using Netconf (already)"

    conn = get_netconf_connection(router_ip)
    if not conn:
        return "Error: NETCONF Connection Failed"

    try:
        if enabled:
            # ลบ shutdown ถ้ามี; ถ้าไม่มีแล้ว บางรุ่นจะตอบ data-missing — ให้มองว่าโอเค
            config_xml = f"""
            <config>
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native"
                      xmlns:nc="urn:ietf:params:xml:ns:netconf:base:1.0">
                <interface>
                  <Loopback>
                    <name>{loop_num}</name>
                    <shutdown nc:operation="delete"/>
                  </Loopback>
                </interface>
              </native>
            </config>
            """
            try:
                _ = conn.edit_config(
                    target="running",
                    config=config_xml,
                    default_operation="merge",
                )
            except RPCError as e:
                # ถ้าลบไม่เจอ (data-missing) ให้ถือว่าสำเร็จ เพราะมัน "เปิด" อยู่แล้ว
                if getattr(e, "tag", None) != "data-missing":
                    raise

        else:
            # ปิด: ใส่ shutdown (merge ได้ตลอด)
            config_xml = f"""
            <config>
              <native xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-native">
                <interface>
                  <Loopback>
                    <name>{loop_num}</name>
                    <shutdown/>
                  </Loopback>
                </interface>
              </native>
            </config>
            """
            _ = conn.edit_config(
                target="running",
                config=config_xml,
                default_operation="merge",
            )

        # 3) Post-check ยืนยันผล
        post = get_interface_status(router_ip, f"Loopback{student_id}")
        if enabled and post == "exists_enabled":
            return f"Interface Loopback{student_id} is enabled successfully using Netconf"
        if (not enabled) and post == "exists_disabled":
            return f"Interface Loopback{student_id} is shutdowned successfully using Netconf"

        # ถ้าผลตรวจหลังทำไม่ตรง เปลี่ยนไปแจ้ง error พร้อมใบ้สถานะจริง
        return f"NETCONF set_interface_state Warning: final state = {post}"

    except Exception as e:
        return f"NETCONF set_interface_state Error: {e}"
    finally:
        try:
            conn.close_session()
        except Exception:
            pass