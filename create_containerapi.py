

from flask import Flask, render_template, request
import requests
import urllib3
import time
import paramiko
from paramiko import RSAKey
from time import sleep

# Disable SSL warnings (not recommended for production)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Flask app initialization
app = Flask(__name__)

# Proxmox API details
PROXMOX_URL = "https://192.168.1.252:8006/api2/json"
TOKEN_ID = "pythonapi@pam!apipython"
TOKEN_SECRET = "8b13892c-c6e9-43c0-b128-3f17dd0f932a"
NODE = "innprox-02"

# Auth headers
headers = {
    "Authorization": f"PVEAPIToken={TOKEN_ID}={TOKEN_SECRET}",
    "Content-Type": "application/json"
}

# Get next available VM ID
def get_available_vmid(node):
    url = f"{PROXMOX_URL}/cluster/nextid"
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code == 200:
        return response.json()['data']
    else:
        return None



def start_vm(vmid):
        hostname = '192.168.1.252'
        username = 'root'
        private_key_path = '/home/innuser002/.ssh/id_rsa'
        port = 22
        
        # SSH client setup
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        private_key = RSAKey.from_private_key_file(private_key_path)
        ssh_client.connect(hostname, port=port, username=username, pkey=private_key)

        # Command to start the container/VM
        stdin, stdout, stderr = ssh_client.exec_command(f'pct start {vmid}')
        result = stdout.read().decode().strip()
        error = stderr.read().decode()
        #  Execute the container creation command
        ssh_client.close()

        if error:
            raise Exception(f"Error starting VM {vmid}: {error}")

        return result
def install_mongodb_inside_lxc(vmid):
    hostname = '192.168.1.252'
    username = 'root'
    private_key_path = '/home/innuser002/.ssh/id_rsa'
    port = 22
    script_on_host = '/root/mongo.sh'
    script_inside_lxc = '/root/mongo.sh'
    # 1. SSH into host
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    private_key = RSAKey.from_private_key_file(private_key_path)
    ssh_client.connect(hostname, port=port, username=username, pkey=private_key)

     # Step 1: Push script
    push_cmd = f"pct push {vmid} {script_on_host} {script_inside_lxc} --perms 755"
    stdin, stdout, stderr = ssh_client.exec_command(push_cmd)
    err = stderr.read().decode().strip()
    if err:
        ssh_client.close()
        raise Exception(f"❌ Error pushing script: {err}")

    # Step 2: Execute it
    exec_cmd = f"pct exec {vmid} -- bash {script_inside_lxc}"
    stdin, stdout, stderr = ssh_client.exec_command(exec_cmd)
    output = stdout.read().decode().strip()
    err = stderr.read().decode().strip()

    ssh_client.close()

    if err:
        raise Exception(f"❌ Error running script in LXC {vmid}: {err}")

    return output

@app.route('/')
def index():
    vmid = get_available_vmid(NODE)
    return render_template('lxc.html', vmid=vmid)


@app.route('/create_lxc', methods=['POST'])
def create_lxc():
    try:
        # Get form data
        name = request.form['name']
        password = request.form['password']
        cores = request.form['cores']
        memory = request.form['memory']
        storage_size = request.form['storage_size']
        key = request.form['key']

        # Get the next available VM ID
        vmid = get_available_vmid(NODE)
        if not vmid:
            return render_template('lxc.html', message="Failed to get available VM ID.")

        # LXC configuration payload (required fields)
        payload = {
            "vmid": int(vmid),
            "ostemplate": "storage1:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst",
            "hostname": name,
            "password": password, 
            "ssh-public-keys": key,
            "storage": "storage1",
            "memory": int(memory),
            "cores": int(cores),
            "rootfs": f"storage1:{storage_size}",
            "net0": "name=eth0,bridge=vmbr0,ip=dhcp",
        }

        # API request to create the LXC container
        create_url = f"{PROXMOX_URL}/nodes/{NODE}/lxc"
        response = requests.post(create_url, headers=headers, json=payload, verify=False)
        
        # Check creation response
        if response.status_code == 200:
          
                message = f"✅ LXC container {vmid} created successfully on node {NODE}."
                 # Start the VM automatically after creation
                sleep(10)
                try:
                    start_vm(vmid)
                    message += " The lxc has been started automatically."
                    sleep(15)
                    try:
                        output = install_mongodb_inside_lxc(vmid)
                        message += " 🛠️ Script installed MongoDB successfully."
                        print(output)
                    except Exception as script_err:
                        message += f" ⚠️ Script error: {script_err}"
                except Exception as e:
                    message += f" However, there was an error starting the VM: {str(e)}"
                  
        else:
            message = f"❌ Failed to create LXC: {response.text}"
            

        return render_template('lxc.html', message=message)
    
    

    except Exception as e:
        return render_template('lxc.html', message=f"❗ Error occurred: {str(e)}")

if __name__ == "__main__":
    app.run(debug=True, port=50001)
