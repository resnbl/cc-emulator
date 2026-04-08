#!/usr/bin/env python
"""
    Serve ("play back") Centauri Carbon messages recorded by cc_recorder.py
    This sort-of acts as an emulator and can be used to repeatably test other
    CC monitor programs without wasting printer resources.

    Called as:
    python3 cc_player.py [<log_file> [<speed>]]

    log-file is the path to where the log resides (default = "cc-log.json").
    speed is a multiplier for the delay between messages (default = "1.0").
"""

import sys
import asyncio
import json
from pathlib import Path

import websockets
from websockets.asyncio.server import serve, ServerConnection

import sdcp_messages as sdcp
from sdcp_defs import STATUS_PORT
import discovery
import print_server

SERVER_HOST = ''        # -> localhost


class StatusServer:
    """ Our Websocket server """
    def __init__(self, ps: print_server.PrintServer):
        self.ps = ps

    async def handler(self, conn: ServerConnection):
        # wait for Status Request message from connector
        async for message in conn:
            if req := sdcp.is_status_request(message):
                print('Received status request from:', conn.remote_address[0])
                ack = sdcp.make_ack(req)
                await conn.send(json.dumps(ack))
                break
            else:
                await conn.send('Who dat?')
                return  # end connection

        # Loop waiting for print server to produce new status records
        try:
            while True:
                async with self.ps.ready:
                    await self.ps.ready.wait()
                    if self.ps.next_status:
                        await conn.send(self.ps.next_status)
                    else:
                        print('Status connection ended from PrintServer')
                        return
        except websockets.ConnectionClosedError as cce:
            print('Connection error:', conn.remote_address[0])
            print(cce)
        except websockets.ConnectionClosedOK:
            print('Connection closed from:', conn.remote_address[0])

    async def serve_status(self):
        try:
            server = await serve(self.handler, SERVER_HOST, STATUS_PORT)
            await server.serve_forever()

        except asyncio.CancelledError:
            print('Status server cancelled')

async def ainput(prompt='Press ENTER to quit...\n'):
    # co-routine to wait for ENTER from keyboard
    try:
        await asyncio.to_thread(input, prompt)
    except asyncio.CancelledError:
        print('Input task cancelled')

async def main(input_log: Path, speed: float = 1.0):
    print('Playing back:', input_log)
    ps = print_server.PrintServer(print_log=input_log, speed=speed, verbose=True)
    ws = StatusServer(ps)

    done, pending = await asyncio.wait([
        asyncio.create_task(ainput(), name='Inputter'),
        asyncio.create_task(discovery.run_server(), name='Discovery'),
        asyncio.create_task(ws.serve_status(), name='Websocket Server'),
        asyncio.create_task(ps.print_stuff(), name='Printer'),
        ], return_when=asyncio.FIRST_COMPLETED)

    for task in pending:
        print('Cancelling task:', task.get_name())
        try:
            task.cancel()
            await task      # wait for their completions
            # print(task.get_name(), 'ended')
        except asyncio.CancelledError:
            pass

    print('All done!')

if __name__ == "__main__":
    asyncio.run(main(
        Path('cc-log.json' if len(sys.argv) <= 1 else sys.argv[1]),
        1.0 if len(sys.argv) <= 2 else float(sys.argv[2])
        )
    )
