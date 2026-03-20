"""
    Serve status messages as if we were actually "3D Printing" something.
    Messages are read from the supplied log file created by cc_recorder.py.
    Certain fields, like "MainboardIP" and "TimeStamp"are replaced with
    current values.

    Additionally, the "TimeStamp" field is used to compute a delay from the
    prior message as the real printer would not be continuously spewing packets.
    This delay is multiplied by the "speed" factor supplied on the command line:
    0.5 == half rate, 1.0 == normal speed, 2.0 == double time. Use higher values
    at your own risk...
"""
import asyncio
import json
import time
from pathlib import Path
from sdcp_defs import MachStatus, InfoStatus
import sdcp_messages


MB = 1024*1024      # bytes -> megabytes


class PrintServer:
    def __init__(self, print_log: Path, speed=1.0, verbose=False):
        self.print_log = print_log
        self.speed = min(max(0.0, speed), 3.0)
        self.verbose = verbose

        # fetch values we need for packet generation
        dp = sdcp_messages.get_disco_resp()
        self.name = dp['Data']['Name']
        self.machine_name = dp['Data']['MachineName']
        self.brand_name = dp['Data']['BrandName']
        self.mainboard_ip = dp['Data']['MainboardIP']

        # signal/mutex for when a new status message is available to be sent
        self.ready = asyncio.Condition()
        self.next_status = ''
        self.file_prev_time = 0
        self.job_counter = 0

    @staticmethod
    def now(t: int) -> str:
        tm = time.localtime(t)
        return f'{tm.tm_hour:02d}:{tm.tm_min:02d}:{tm.tm_sec:02d}'

    async def process_rec(self, rec: dict):
        # Status or Attributes record: delay before processing
        rec_time = rec['TimeStamp']
        if self.file_prev_time > 0:
            # delay until this record is reflected in printer status
            delay_secs = (rec_time - self.file_prev_time) / self.speed
            await asyncio.sleep(delay_secs)
        self.file_prev_time = rec_time

        async with self.ready:  # lock status until we've updated msg buffer
            blab = ''
            if 'Attributes' in rec:
                # Substitute "our" device info
                attrs = rec['Attributes']
                attrs['Name'] = self.name
                attrs['MachineName'] = self.machine_name
                attrs['BrandName'] = self.brand_name
                attrs['MainboardIP'] = self.mainboard_ip
                if self.verbose:
                    blab = f'Attributes: memory: {attrs['RemainingMemory'] // MB} MB'
            else:
                if self.verbose:
                    stats = rec['Status']
                    pinfo = stats['PrintInfo']
                    mach = MachStatus.from_int(stats['CurrentStatus'][0]).name
                    info = InfoStatus.from_int(pinfo['Status']).name
                    layers = f'{pinfo['CurrentLayer']}/{pinfo['TotalLayer']}'
                    if pinfo['TotalTicks']:
                        pct = int(100 * (pinfo['CurrentTicks'] + 0.5) / pinfo['TotalTicks'])
                    else:
                        pct = 0
                    blab = f'Status: Mach: {mach} Info: {info} Layers: {layers} Ticks: {pct}%'

            # update record time
            rec['TimeStamp'] = int(time.time())
            self.next_status = json.dumps(rec)
            if self.verbose:
                print(f'{self.now(rec["TimeStamp"])}: {blab}')
            self.ready.notify()

    async def print_model(self):
        self.file_prev_time = 0

        # In order to avoid loading and holding onto a large JSON object,
        # we "sub-parse" the file line by line
        with open(self.print_log) as jfile:
            while line := jfile.readline().rstrip(', \n'):
                if '{' in line:     # is data record, not '[' or ']'
                    rec = json.loads(line)
                    if 'TimeStamp' in rec:
                        await self.process_rec(rec)
                    # else ignore 'Id' (ack) records

        self.job_counter += 1
        print(f'Print job {self.job_counter} complete')

    async def print_stuff(self, delay_btwn_jobs=10):
        # Our print service
        try:
            while True:
                await asyncio.sleep(delay_btwn_jobs)
                await self.print_model()
        except asyncio.CancelledError:
            async with self.ready:
                self.next_status = None     # flag we're quitting
                self.ready.notify()
            print(f'Printer server cancelled - {self.job_counter} jobs completed')
