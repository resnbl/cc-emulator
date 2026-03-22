#!/usr/bin/env python
"""
    Record messages from a Centauri Carbon printer to a log file for cc_player.py

    Called as:
    python3 cc_recorder.py [<log-file> [<ip-addr>]]

    log-file is the path to where the log is written (default = "cc-log.json").
    ip-addr is the IP address of the printer to monitor (default = "255.255.255.255"
        which will broadcast to all devices on the local network and will use
        the first (only?) one to respond).
"""

import sys
from pathlib import Path
import asyncio
import socket
import json
import time

import websockets

from sdcp_defs import PrinterStatus, DISCOVERY_PORT, STATUS_PORT

class MsgLogger:
    """ Output recorded messages as:
        [
            {<item>:<value>, ...},
            {<item>:<value>, ...},
            ...,
            {<item>:<value>, ...},
        ]
    (ensure no trailing comma on last message per JSON standards).
    Note this class is expected to be used as a "context manager".
    """
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_file = None
        self.first = True

    def __enter__(self):
        self.log_file = open(self.log_path, 'w')
        return self

    def log(self, msg: str):
        if self.first:
            self.log_file.write('[\n  ')
            self.first = False
        else:
            self.log_file.write(',\n  ')
        self.log_file.write(msg)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.log_file:
            self.log_file.write('\n]')
            self.log_file.close()
        return False    # propagate Exceptions


# Some logic lifted from github.com/sheffieldnikki/centauri-carbon-monitor/

"""
    Expected response from any SDCP printers (like the Elegoo Centauri Carbon):
    {
        "Id": "<32-char hex string>",               # Machine brand ID
        "Data": {                                       
            "Name": "Centauri Carbon",              # Machine name
            "MachineName": "Centauri Carbon",       # Machine model
            "BrandName": "ELEGOO",                  # Brand name
            "MainboardIP": "192.168.x.y",           # local IP address
            "MainboardID": "<32-char hex string>",  # serial # ?
            "ProtocolVersion": "V3.0.0",
            "FirmwareVersion": "V1.1.29"
        }
    }
"""

def scan_network(disco_addr: str) -> list[PrinterStatus]:
    """ Scan local network for SDCP printers with UDP broadcast.
        We broadcast even when given a specific IP address
        in order to retrieve fields needed for subsequent requests.
    """
    printers = []
    broadcast_address = (disco_addr, DISCOVERY_PORT)
    broadcast_message = "M99999"    # only SDCP printers respond to this msg (?)
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print("Searching for SDCP printers on local network...\n")
    try:
        udp_socket.sendto(broadcast_message.encode(), broadcast_address)
        udp_socket.settimeout(3)
        while True:     # note: will get multiple responses if more than one printer online
            try:
                response, ipaddr = udp_socket.recvfrom(1024)
                response_json = json.loads(response.decode())
                if "Data" not in response_json or "Id" not in response_json:
                    print(f"Response from {ipaddr[0]} unrecognised as SDCP")
                    continue

                data = response_json["Data"]
                printers.append(PrinterStatus(brand_id=response_json["Id"],
                                              name=data['Name'],
                                              ip_addr=data['MainboardIP'],
                                              mb_id=data['MainboardID']))

            except json.JSONDecodeError:
                print(f"Response from {ipaddr[0]} is invalid JSON") # noqa
            except socket.timeout:
                break
    finally:
        udp_socket.close()

    return printers


def make_status_req(printer: PrinterStatus, req_no=0) -> str:
    """ Centauri Carbon ignores the values of some of these fields,
        but they *must* be filled in with the proper data type values
        or the printer will freeze hard! """
    req = {
        'Id': printer.brand_id,
        'Data': {
            'Cmd': 0,                           # 0 -> Request Status
            'Data': {},
            'RequestID': str(req_no),           # arbitrary
            'MainboardIP': printer.ip_addr,
            'Timestamp': int(time.time()),      # Unix-epoch seconds
            'From': 0,                          # got me?
        },
        'Topic': 'sdcp/request/' + printer.brand_id
    }

    return json.dumps(req)


async def monitor_printer(printer: PrinterStatus, log):
    """Monitor a single SDCP printer"""
    uri = f'ws://{printer.ip_addr}:{STATUS_PORT}/websocket'
    request_number = 0
    async for ws in websockets.connect(uri):
        try:
            request_number += 1
            request = make_status_req(printer, request_number)
            # print('Sending', request)
            await ws.send(request)
            prev_time = time.time()

            async for msg in ws:
                msg_obj = json.loads(msg)
                if 'Status' in msg_obj or 'Attributes' in msg_obj:  # filter out 'Ack' msgs
                    # set timestamp relative to previous message as debug aid
                    curr_time = time.time()
                    msg_obj['TimeStamp'] = int(curr_time - prev_time + 0.5)
                    prev_time = curr_time
                    log.log(json.dumps(msg_obj, separators=(',', ':')))     # compact output

        except json.JSONDecodeError:
            print(f"Response from {printer.mb_id} is invalid JSON")
        except websockets.exceptions.ConnectionClosed:
            pass
            # print(f"Connection closed to {printer.mb_id}")
            # restart connection...
        except asyncio.CancelledError:
            # print('monitor task cancelled')
            raise   # break out of loop


async def ainput(prompt='Press ENTER to quit...\n'):
    # co-routine to wait for ENTER from keyboard
    try:
        await asyncio.to_thread(input, prompt)
    except asyncio.CancelledError:
        # print('input task cancelled')
        raise


async def main(log_path: Path, disco_addr: str):
    with MsgLogger(log_path) as log:
        # Output is JSON list of JSON responses from printer
        printers = scan_network(disco_addr)
        if printers:
            printer = printers[0]       # use the first one found (I only have 1!)

            # Two tasks to allow console input to kill connection gracefully
            monitor = asyncio.create_task(monitor_printer(printer, log), name='monitor')
            inputter = asyncio.create_task(ainput(), name='console input')

            done, pending = await asyncio.wait([monitor, inputter],
                                               return_when=asyncio.FIRST_COMPLETED)
            # for task in done:
            #     print(task.get_name(), 'is complete')
            for task in pending:
                # print(task.get_name(), 'is pending')
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        else:
            print("No printers found")

    if not printers:
        log_path.unlink()


if __name__ == "__main__":
    asyncio.run(main(
        Path('cc-log.json' if len(sys.argv) <= 1 else sys.argv[1]),
        '255.255.255.255' if len(sys.argv) <= 2 else sys.argv[2]
        )
    )
