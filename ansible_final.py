import subprocess
import sys
import os

# ROUTER_MAP = {
#     "10.0.15.61": "CSR1KV-Pod1-1",
#     "10.0.15.62": "CSR1KV-Pod1-2",
#     "10.0.15.63": "CSR1KV-Pod1-3",
#     "10.0.15.64": "CSR1KV-Pod1-4",
#     "10.0.15.65": "CSR1KV-Pod1-5"
# }

# def showrun(student_id, router_ip):
    
#     router_name = ROUTER_MAP.get(router_ip) # <-- เราหา 'CSR1KV-Pod1-1' มาเก็บไว้
#     if not router_name:
#         return "Error: Unknown Router IP"
        
#     filename = f"show_run_{student_id}_{router_name}.txt"

#     command = [
#         sys.executable,
#         '-m',
#         'ansible.cli.playbook',
#         'playbook.yaml', 
#         '--limit', router_name,  # <--- แก้ไขตรงนี้ (จาก router_ip)
#         '-e', f'student_id={student_id}'
#     ]

#     # รันแบบปกติ ไม่ต้องมี env=... หรือ shell=True
#     result = subprocess.run(
#         command, 
#         capture_output=True, 
#         text=True
#     )

#     if 'ok=2' in result.stdout and 'failed=0' in result.stdout:
#         return filename
#     else:
#         print("--- Ansible Error Output ---")
#         print(result.stderr)
#         print(result.stdout)
#         print("----------------------------")
#         return "Error: Ansible"

def write_motd(student_id, router_ip, message):
    """เขียน MOTD Banner (Ansible)"""
    
    command = [
        sys.executable,
        '-m',
        'ansible.cli.playbook',
        'playbook_motd.yaml',
        '--limit', router_ip,
        '-e', f'motd_message={message}' # <--- 2. ส่ง "message" เข้าไป
    ]
    
    # (โค้ดบังคับ UTF-8 ... เหมือนเดิม)
    env = os.environ.copy() 
    env['PYTHONUTF8'] = '1' 
    env['LC_ALL'] = 'en_US.UTF-8'
    env['LANG'] = 'en_US.UTF-8'
    env['PYTHONIOENCODING'] = 'utf-8'

    result = subprocess.run(
        command, 
        capture_output=True, 
        text=True,
        encoding='utf-8', 
        env=env
    )
    
    # 3. ตรวจสอบผลลัพธ์ (Playbook นี้มีแค่ 1 task = ok=1)
    if 'ok=1' in result.stdout and 'failed=0' in result.stdout:
        return "Ok: success"
    else:
        print("--- Ansible Error Output ---")
        print(result.stderr)
        print(result.stdout)
        print("----------------------------")
        return "Error: Ansible MOTD failed"