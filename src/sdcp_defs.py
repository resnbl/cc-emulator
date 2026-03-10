from dataclasses import dataclass, field
import datetime
from enum import IntEnum

# Definitions gleaned from:
#   github.com/cbd-tech/SDCP-Smart-Device-Control-Protocol-V3.0.0/
#   github.com/danielcherubini/elegoo-homeassistant/

DISCOVERY_PORT = 3000
STATUS_PORT = 3030

# Status.CurrentStatus definitions
class MachStatus(IntEnum):
    UNKNOWN = -1
    IDLE = 0
    PRINTING = 1
    FILE_TRANFERRING = 2
    EXPOSURE_TESTING = 3
    DEVICES_TESTING = 4
    LEVELING = 5
    INPUT_SHAPING = 6
    STOPPING = 7
    STOPPED = 8
    HOMING = 9
    LOADING_UNLOADING = 10
    PID_TUNING = 11
    RECOVERY = 12

    @classmethod
    def from_int(cls, status_int: int) -> 'MachStatus':
        try:
            return cls(status_int)
        except ValueError:
            return MachStatus.UNKNOWN


# Status.PrintInfo.Status definitions
class InfoStatus(IntEnum):
    UNKNOWN = -1
    IDLE = 0
    HOMING = 1
    DROPPING = 2
    PRINTING = 3
    LIFTING = 4
    PAUSING = 5
    PAUSED = 6
    STOPPING = 7
    STOPPED = 8
    COMPLETE = 9
    FILE_CHECKING = 10
    RECOVERY = 12
    PRINTING_RECOVERY = 13
    LOADING = 15
    PREHEATING = 16
    LOADING18 = 18
    LOADING19 = 19
    LEVELING = 20
    LOADING21 = 21

    @classmethod
    def from_int(cls, status_int: int) -> 'InfoStatus':
        # if status_int in (18, 19, 21):
        #     return cls.LOADING
        # if status_int == cls.PRINTING_RECOVERY.value:
        #     return cls.PRINTING
        try:
            return cls(status_int)
        except ValueError:
            return InfoStatus.UNKNOWN


# Status.PrintInfo.ErrorNumber definitions (if present)
class PrintError(IntEnum):
    UNKNOWN = -1
    NONE = 0
    CHECK = 1
    FILEIO = 2
    INVALID_RESOLUTION = 3
    UNKNOWN_FORMAT = 4
    UNKNOWN_MODEL = 5

    @classmethod
    def from_int(cls, status_int: int) -> 'PrintError':
        try:
            return cls(status_int)
        except ValueError:
            return PrintError.UNKNOWN


@dataclass
class CurrTarget:          # current / maximum
    current: int = 0
    target: int = 0

    def update(self, curr: int, targ: int) -> bool:
        chgd = curr != self.current
        self.current = curr
        chgd |= targ != self.target
        self.target = targ

        return chgd


@dataclass
class PrinterStatus:
    """ Subset of available info from printer. """
    brand_id: str       # used in requests
    name: str
    ip_addr: str
    mb_id: str          # used in requests
    last_update: datetime.time = field(default_factory=datetime.time)
    curr_status: MachStatus = MachStatus.UNKNOWN
    prt_status: InfoStatus = InfoStatus.UNKNOWN
    bed_temps: CurrTarget = field(default_factory=CurrTarget)
    nozzle_temps: CurrTarget = field(default_factory=CurrTarget)
    box_temps: CurrTarget = field(default_factory=CurrTarget)
    light: bool = False
    layers: CurrTarget = field(default_factory=CurrTarget)
    times: CurrTarget = field(default_factory=CurrTarget)
    filename: str = ''
    prt_err: PrintError = PrintError.NONE
    free_mb: int = 0

    def time_left(self) -> str:
        ticks = self.times.target - self.times.current
        mins, secs = divmod(ticks, 60)
        hrs, mins = divmod(mins, 60)
        if hrs:
            return f'{hrs}h:{mins:02d}m'
        else:
            return f'{mins:02d}m'

    def __str__(self):
        text = (f'{self.last_update} {self.curr_status.name} {self.prt_status.name} '
                f'Layer: {self.layers.current}/{self.layers.target} '
                f'Nozzle: {self.nozzle_temps.current}/{self.nozzle_temps.target} '
                f'Bed: {self.bed_temps.current}/{self.bed_temps.target} '
                f'Box: {self.box_temps.current} Light: {'ON' if self.light else 'OFF'} ')

        if self.filename:
            text += f'Time: {self.time_left()} Filename: {self.filename} '
        if self.prt_err != PrintError.NONE:
            text += f'Error: {self.prt_err.name} '
        if self.free_mb != 0:
            text += f'Free MB: {self.free_mb} '
        return text
