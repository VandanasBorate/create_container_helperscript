from flask import Flask, request, jsonify, render_template
import paramiko
from paramiko import RSAKey

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('marketplace.html') 



@app.route('/create_lxc', methods=['GET', 'POST'])
def lxc_container(): 


    if request.method == 'GET':
        try:


            file_name = request.args.get('file_name')
            print(f"Requested file: {file_name}")
            # Define your Proxmox node details for SSH connection
            hostname = '192.168.1.252'  # Proxmox node 1 IP (inprox)
            username = 'root'  # Proxmox username
            private_key_path = '/home/innuser002/.ssh/id_rsa'  # Path to your private SSH key
            port = 22

            print("Setting up SSH client...")

            # Create an SSH client instance
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Load the private key for authentication
            print(f"Loading private key from {private_key_path}...")
            private_key = RSAKey.from_private_key_file(private_key_path)

            # Connect to the Proxmox node
            print(f"Connecting to Proxmox server at {hostname}...")
            ssh_client.connect(hostname, port=port, username=username, pkey=private_key)
            # Execute the script to get next available LXC ID
            print("Fetching next available LXC ID...")
            stdin, stdout, stderr = ssh_client.exec_command('pvesh get /cluster/nextid')

            # Capture output and errors
            result = stdout.read().decode().strip()
            error = stderr.read().decode()
        
            if result:
                print(f"LXC ID fetched: {result}")
                return render_template('create_lxc.html', ct_id=result,file_name=file_name)

            if error:
                print(f"Script error: {error}")
                return f"Error occurred: {error}"
        
        except Exception as e:
            print(f"Error connecting to Proxmox: {str(e)}")
            return f"Error connecting to Proxmox: {str(e)}"
        
        finally:
            ssh_client.close()
            print("SSH connection closed.")


    elif request.method == 'POST':


      
        # Get form data from the submitted form
        vmid = request.form.get('vmid') 
        file = request.form.get('file_name') # LXC ID (Auto-generated)
        name = request.form.get('name')  # LXC Name
        password = request.form.get('pass')  # LXC Password
        # ssh_key = request.form.get('ssh')  # LXC SSH Key
        ssh_key = '"' + str(request.form.get('ssh', '')) + '"'

     
        print(f"Received SSH key: {ssh_key}")

        # Check if all form fields are filled
        if not vmid or not name or not password or not ssh_key:
            return render_template('create_lxc.html', error="All fields must be filled out!")

        try:
            # Define Proxmox node details for SSH connection
            hostname = '192.168.1.252'  # Proxmox node IP
            username = 'root'  # Proxmox username
            private_key_path = '/home/innuser002/.ssh/id_rsa'  # Path to your private SSH key
            port = 22

            print("Setting up SSH client...")

            # Create an SSH client instance
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Load private key for authentication
            print(f"Loading private key from {private_key_path}...")
            private_key = RSAKey.from_private_key_file(private_key_path)

            # Connect to Proxmox node
            print(f"Connecting to Proxmox server at {hostname}...")
            ssh_client.connect(hostname, port=port, username=username, pkey=private_key)

           
            command = f'/bin/bash {file} {vmid} {name} {password} {ssh_key}'

            # command = f'/bin/bash /root/my.sh {vmid} {name} {password} {ssh_key}'
            print(f"Executing command: {command}")

            # Execute the command
            stdin, stdout, stderr = ssh_client.exec_command(command)

            # Capture the output and errors
            result = stdout.read().decode().strip()
            error = stderr.read().decode().strip()

            if error:
                print(f"Error occurred: {error}")
                return render_template('create_lxc.html', error=f"Error occurred: {error}")

            if result:
                print(f"Script output: {result}")
                print("Fetching IP and MAC address of the container...")

                # Command to fetch the IPv4 address of eth0 (exclude IPv6)
                ip_command = f"pct exec {vmid} -- ip -4 a show eth0 | grep inet | awk '{{print $2}}' | cut -d'/' -f1"

                # Command to fetch the full MAC address (no truncation)
                mac_command = f"pct exec {vmid} -- ip link show eth0 | grep link/ether | awk '{{print $2}}'"

                # Execute the command for IP address
                stdin, stdout, stderr = ssh_client.exec_command(ip_command)
                ip_result = stdout.read().decode().strip()

                # Execute the command for MAC address
                stdin, stdout, stderr = ssh_client.exec_command(mac_command)
                mac_result = stdout.read().decode().strip()

                # Handle the case where results might be empty or not found
                ip_address = ip_result if ip_result else "N/A"
                mac_address = mac_result if mac_result else "N/A"

                print(f"IP Address: {ip_address}")
                print(f"MAC Address: {mac_address}")



                return render_template('create_lxc.html', success_message=f"LXC Container created successfully!",
                                      ip_address=ip_address, mac_address=mac_address)

                # return render_template('create_lxc.html', success_message=f"LXC Container created successfully!")
            
                
              

        except Exception as e:
            print(f"Error connecting to Proxmox: {str(e)}")
            return render_template('create_lxc.html', error=f"Error connecting to Proxmox: {str(e)}")

        finally:
            # Ensure the SSH client is closed to release resources
            ssh_client.close()
            print("SSH connection closed.")

if __name__ == '__main__':
    app.run(debug=True , port=5000)
