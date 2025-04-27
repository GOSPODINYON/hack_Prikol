import socket, random
from threading import Thread, Lock
import web
import json
import time
import re

mode = "prod"
sock = None
writelock = Lock()
TMSILIST = []
CONNLIST = {}

RQ_INITIAL_ALLOC_RESPONSE = "{RAND} Server running in {MODE} mode, allocated {IMSI}, required {ACTION}"
RQ_REINITAL_RESPONSE = "{RAND} Server running in {MODE} mode, reallocation success {IMSI}, required {ACTION}"
RQ_REINIT_IMSI_NOT_FOUND_RESPONSE = "{RAND} Server running in {MODE} mode, {IMSI} reallocation rejected, REASON: no imsi found in db, required {ACTION}"
RQ_REINIT_IMSI_BLOCKED_RESPONSE = "{RAND} Server running in {MODE} mode, {IMSI} reallocation rejected, REASON: imsi temporarily disabled, required {ACTION}"

regex_groups_connhostport = "\('(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',\s*(\d{1,5})\)"
  
if mode == "dev":  
    print("Running on staging pmsi list will be ignored and new hosts will get TMSI assigned instead.")
elif mode == "prod":
    print("Using permament host list")
else:
    print("Invalid launch mode specified")

def setup_socket(host='0.0.0.0', port=12010):
    global sock
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))

def udp_server(socket, host='0.0.0.0', port=12010):
    print(f"UDP server is running on {host}:{port}")
 
    while True:
        try:
            data, addr = socket.recvfrom(1024)
            message = data.decode('utf-8')
            #print(f"Received message: {message} from {addr}")
            
            if message == "keepalivedconn":
                with open("./data/sessions.txt", 'r+') as f:
                    with writelock:
                        jsondata = json.load(f)
                        for conn, amsi in CONNLIST.items():
                            if conn == addr:
                                jsondata["vms"][str(amsi)]["lastKeepalive"] = "0"
                        f.seek(0)
                        f.write(json.dumps(jsondata))
                        f.truncate()
                        print(f"Processed keepalive to {addr}")
            elif message == "initial":
                print(f"Processing initial request to {addr}")
                imsi = random.randint(1000,20000)
                CONNLIST.update({addr: imsi})
                if mode == "dev":
                    response = RQ_INITIAL_ALLOC_RESPONSE.format(RAND=str(random.randint(100,9999999999999)), MODE=mode, IMSI=str(imsi), ACTION=None)
                    TMSILIST.append(imsi)
                    socket.sendto(response.encode('utf-8'), addr)
                    data, addr = socket.recvfrom(1024)
                    recvmessage = data.decode('utf-8')
                    new_vm = {
                        f"{imsi}": {
                            "status": "online",
                            "canonicalName": "Untitled",
                            "lastKeepalive": "0",
                            "blocked": "False"
                            "conn": f"{addr}"
                        }
                    }

                    with open("./data/sessions.txt", 'r+') as f:
                        with writelock:
                            oldjson = json.load(f)
                            f.seek(0)
                            oldjson["vms"].update(new_vm)
                            newjson = json.dumps(oldjson)
                            f.write(newjson)

                    print(f"Processed and added new host, IMSI: {imsi}, conn {addr}")
                elif mode == "prod":
                    response = RQ_INITIAL_ALLOC_RESPONSE.format(RAND=str(random.randint(100,9999999999999)), MODE=mode, IMSI=str(imsi), ACTION=None)
                    TMSILIST.append(imsi)
                    socket.sendto(response.encode('utf-8'), addr)
                    data, addr = socket.recvfrom(1024)
                    recvmessage = data.decode('utf-8')
                    new_vm = {
                        f"{imsi}": {
                            "status": "online",
                            "canonicalName": "Untitled",
                            "lastKeepalive": "0",
                            "blocked": "False",
                            "conn": f"{addr}"
                        }
                    }

                    with open("./data/sessions.txt", 'r+') as f:
                        with writelock:
                            oldjson = json.load(f)
                            f.seek(0)
                            oldjson["vms"].update(new_vm)
                            newjson = json.dumps(oldjson)
                            f.seek(0)
                            f.truncate()
                            f.write(newjson)

                    print(f"Processed and added new permament host, PMSI: {imsi}, conn {addr}")
            elif "reinitial" in message:
                reimsi = message[10:]
                with open("./data/sessions.txt", 'r+') as f:
                    with writelock:
                        oldjson = json.load(f)
                        f.seek(0)
                        try:
                            if oldjson["vms"][reimsi] != None:
                                if oldjson["vms"][reimsi]['blocked'] == "False":
                                    CONNLIST.update({addr: reimsi})
                                    oldjson["vms"][reimsi]['conn'] = str(addr)
                                    newjson = json.dumps(oldjson)
                                    f.seek(0)
                                    f.truncate()
                                    f.write(newjson)
                                    response = RQ_REINITAL_RESPONSE.format(RAND=str(random.randint(100,9999999999999)), MODE=mode, IMSI=str(reimsi), ACTION=None)
                                else:
                                    print("Tried to allocate blocked imsi")
                                    response = RQ_REINIT_IMSI_BLOCKED_RESPONSE.format(RAND=str(random.randint(100,9999999999999)), MODE=mode, IMSI=str(reimsi), ACTION=None)
                            else:
                                print("Tried to allocate non existing imsi")
                                response = RQ_REINIT_IMSI_NOT_FOUND_RESPONSE.format(RAND=str(random.randint(100,9999999999999)), MODE=mode, IMSI=str(reimsi), ACTION=None)
                        except Exception as e:
                            print("Tried to allocate non existing imsi")
                            response = RQ_REINIT_IMSI_NOT_FOUND_RESPONSE.format(RAND=str(random.randint(100,9999999999999)), MODE=mode, IMSI=str(reimsi), ACTION=None)
                socket.sendto(response.encode('utf-8'), addr)
                print(f"Processed re-inintal request for {reimsi}, conn {addr}")
            else:
                print(f"Received unprocessable message from client: {message}")
        except Exception as e:
            print(e)
            pass

            
def udp_sendto_nowait(socket, host, port, message=''):
    socket.sendto(message.encode('utf-8'), (host, port))

def to_send_reader(socket):
    while True:
        with open("./data/sendinfo.txt", 'r+') as f:
            data = json.load(f)
            try:
                for imsi, senddata in data.items():
                    senddata = data[imsi]['data']
                    for conn, amsi in CONNLIST.items():
                        if int(imsi) == int(amsi):
                            try:
                                socket.sendto(bytes(senddata, encoding='utf-8'), conn)
                                print("Info successfully sent!")
                            except Exception as e:
                                print("Exception sending data", e)
                        else:
                            pass
            except Exception as e:
                print(e)
            blank = {
                "0": {
                    "data": "dw"
                }
            } 
            f.truncate(0)
            f.seek(0)
            f.write(json.dumps(blank))
        time.sleep(1)

def keepaliver(socket):
    print("Keepalive thread launched")
    while True:
        for conn, imsi in CONNLIST.items():
            socket.sendto(bytes(random.randint(100,999)), conn)
        time.sleep(10)

def keepaliver_increaser():
    while True:
        try:
            with open("./data/sessions.txt", 'r+') as f:
                with writelock:
                    jsondata = json.load(f)
                    for conn, amsi in jsondata.items():
                        for iimsi, dkdata in amsi.items():
                            keepalivedata = int(jsondata["vms"][iimsi]["lastKeepalive"])
                            jsondata["vms"][iimsi]["lastKeepalive"] = str(keepalivedata + 1)
                    f.seek(0)
                    f.write(json.dumps(jsondata))
                    f.truncate()
                time.sleep(1)
        except Exception as e:
            print("Encountered an exception while increasing keepalive. Wrong sessions json")

def connlist_loader():
    with open("./data/sessions.txt", 'r') as f:
        jsondata = json.load(f)
        for conn, amsi in jsondata.items():
            for iimsi, dkdata in amsi.items():
                keepalivedata = int(jsondata["vms"][iimsi]["lastKeepalive"])
                conndata = str(jsondata["vms"][iimsi]["conn"])

                match = re.search(regex_groups_connhostport, conndata)
                ip = match.group(1)
                port = int(match.group(2))
                reconn = (ip, port)
                
                if keepalivedata < 300:
                    CONNLIST.update({reconn: iimsi})
                    print(f"CONNLIST updated with {conndata} host")

def start_web():
    www = web.Web()
    www.start()

if __name__ == "__main__":
    setup_socket()
    connlist_loader()
    udp_server_thread = Thread(target=udp_server, args=(sock,))
    udp_server_thread.start()
    web_server_thread = Thread(target=start_web)
    web_server_thread.start()
    conn_keepaliver_thread = Thread(target=keepaliver, args=(sock,))
    conn_keepaliver_thread.start()
    to_send_reader_thread = Thread(target=to_send_reader, args=(sock,))
    to_send_reader_thread.start()
    keepaliver_increaser_thread = Thread(target=keepaliver_increaser)
    keepaliver_increaser_thread.start()