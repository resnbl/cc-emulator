"""Define the format of various messages sent by the printer"""
import json
import socket
import time


_disco_resp = {
    "Id": "979d4C788A4a78bC777A870F1A02867A5",  # Elegoo Brand ID?
    "Data": {
        "Name": "?",  # our host name
        "MachineName": "Centauri Carbon",  # model
        "BrandName": "Illy-Goo",
        "MainboardIP": "?",  # our IP address
        "MainboardID": "2c9018510147017000002c0000000000",
        "ProtocolVersion": "V3.0.0",
        "FirmwareVersion": "V1.1.29"
    }
}

def get_disco_resp() -> dict:
    """Initialize the UDP response data only once"""
    if _disco_resp['Data']['Name'] == "?":
        host_fqdn = ''
        addrs = []
        try:
            host_fqdn = socket.gethostname()
            addrs = socket.gethostbyname_ex(host_fqdn)[2]
            host_addr = addrs[0] if not addrs[0].startswith('127.') else addrs[1]
            _disco_resp['Data']['Name'] = 'Centauri Carbon'     # host_fqdn.replace('.local', '')
            _disco_resp['Data']['MainboardIP'] = host_addr
        except OSError as e:
            print(e)
            print(f'fqdn="{host_fqdn}" addrs="{addrs}"')

    return _disco_resp

"""
sdcp_command = {
    "Id": "979d4C788A4a78bC777A870F1A02867A5",  # Elegoo Brand ID?
    "Data": {
        "Cmd": 0,       # Request Status
        "Data": {},
        "RequestID": "?",
        "MainboardID": "?",
        "TimeStamp": 0,
        "From": 0
    },
    "Topic": "sdcp/request/?"   # mainboardID
}
"""

def is_status_request(s: str) -> dict | None:
    """If input is valid SDCP status request, return as object"""
    try:
        req = json.loads(s)
        if 'Id' in req and 'Data' in req:
            req_data = req['Data']
            if 'RequestID' in req_data and req_data.get('Cmd', -1) == 0:
                return req
    except json.decoder.JSONDecodeError:
        pass

    return None     # ignore this "request"

_sdcp_ack = {
    "Id": "979d4C788A4a78bC777A870F1A02867A5",  # Elegoo Brand ID?
    "Data": {
        "Cmd": 0,  # Request Status
        "Data": {
            "Ack": 0
        },
        "RequestID": "?",
        "MainboardID": "?",
        "TimeStamp": 0,
    },
    "Topic": "sdcp/response/?"  # mainboardID
}

def make_ack(req: dict) -> dict:
    """Generate Ack response to request for status"""
    req_data = req['Data']
    disco = get_disco_resp()    # ensure initialized
    # should really make a "deep copy"...
    ack_data = _sdcp_ack['Data']
    ack_data['RequestID'] = req_data['RequestID']
    ack_data['MainboardID'] = disco['Data']['MainboardID']
    ack_data['TimeStamp'] = int(time.time())
    _sdcp_ack['Topic'] = 'sdcp/response/' + disco['Data']['MainboardID']

    return _sdcp_ack
