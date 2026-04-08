#!/usr/bin/env python
"""
    Scan Centauri Carbon messages recorded by cc_recorder.py and output
    only status changes.

    Called as:
    python3 status_changes.py [<log_file> [<out_file>]]

    log-file is the path to where the log resides (default = "cc-log.json").
    out_file is the path to an output file (default = "<log_file>.txt")
"""

import sys
import json
from pathlib import Path

from sdcp_defs import MachStatus, InfoStatus


def main(inp: Path, outp: Path):
    """ Output records every time the Mchine status and/or Printer status changes """
    prev_ms = MachStatus.UNKNOWN
    prev_ps = InfoStatus.UNKNOWN
    duration = 0

    with open(outp, 'w') as outf:
        print('Status read from:', inp, file=outf)
        print(f'{"Time":4}  {"Machine Status":18} {"PrintInfo Status":18}', file=outf)

        with open(inp) as inf:
            while line := inf.readline().rstrip(', \n'):
                if '{' in line:     # is data record, not '[' or ']'
                    rec: dict = json.loads(line)
                    dur = rec['TimeStamp'] if 'TimeStamp' in rec else 0

                    if 'Status' in rec:
                        status = rec['Status']
                        ms = MachStatus.from_int(status['CurrentStatus'][0])
                        prt_info = status['PrintInfo']
                        ps = InfoStatus.from_int(prt_info['Status'])

                        if prev_ms != ms or prev_ps != ps:      # status change
                            print(f'{duration:4d}  {ms.name:18} {ps.name:18}', file=outf)
                            prev_ms = ms
                            prev_ps = ps
                            duration = 0
                    # else ignore "Attributes" and "Acks"

                    duration += dur


if __name__ == "__main__":
    proj_dir = Path(__file__).parent.parent
    in_path = Path(proj_dir / 'cc-log.json' if len(sys.argv) <= 1 else sys.argv[1])
    if in_path.exists():
        out_path = sys.argv[2] if len(sys.argv) > 2 else in_path.with_suffix('.txt')
        print('Input:', in_path, 'Output:', out_path)
        main(in_path, out_path)
    else:
        print('Input not found:', in_path)
