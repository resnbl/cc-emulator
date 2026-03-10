"""
    Accept messages broadcast on the local network looking for a Centauri Carbon printer.
    When sent the proper query message, this code responds with a JSON packet containing
    our network address and other information about the printer we are emulating.
"""
import asyncio
import json

import sdcp_messages
from sdcp_defs import DISCOVERY_PORT

DISCOVERY_QUERY = 'M99999'


class DiscoveryUDPProtocol(asyncio.DatagramProtocol):
    DISCO_RESP_BYTES = json.dumps(sdcp_messages.get_disco_resp()).encode()

    def connection_made(self, transport):
        self.transport = transport      # noqa

    def datagram_received(self, data, addr):
        message = data.decode().strip()
        if message == DISCOVERY_QUERY:
            print(f"Received query from {addr[0]}")
            self.transport.sendto(self.DISCO_RESP_BYTES, addr)
        # else:
        #     print('bogus msg:', message)


async def run_server():
    print("Starting UDP server")
    loop = asyncio.get_running_loop()
    transport, _ = await loop.create_datagram_endpoint(
        lambda: DiscoveryUDPProtocol(),
        local_addr=('0.0.0.0', DISCOVERY_PORT)      # 0.0.0.0 -> all interfaces!
    )

    try:
        # wait for an event that will never happen
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        print('Stopping Discovery server')
    finally:
        transport.close()
