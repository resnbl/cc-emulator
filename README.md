# Centauri Carbon Emulator

## Purpose

I am developing a monitor for my Elegoo Centauri Carbon (CC) printer using a Cheap
Yellow Display (CYD) programmed in MicroPython (both of these items are new to me).
I quickly realized that in order to test my device's code,
I would need to keep my printer running and producing status messages.
This seemed problematic, especially when I found that an error in my
code could cause the CC to lock up hard and require a power-down and rest
before starting up again.

So instead I created this "emulator" (using the term quite loosely)
for the desktop that can record the status messages produced during a
print by the real printer. Then they can be played 
back in a convenient and repeatble fashion while I tested my device.

## Background

The Centauri Carbon acts a Websocket server - this is how your desktop slicer
sends files to and retrieves status updates from it. The messages conform
to the "standard" (another loose term here) detailed at:

https://github.com/cbd-tech/SDCP-Smart-Device-Control-Protocol-V3.0.0

(Note the examples shown in the documentation are for a resin printer, which
explains why Elegoo varied from it. I expect other manufacturers to do the same.)

## The files

### cc_recorder.py

This script is a Websocket client that will connect to a live CC printer and
create a JSON-format log file from the messages it receives. At startup, it will
broadcast a query to all devices on the local network and then connect to the
first printer that responds. This is needed even if the printer's IP address
is known in advance because the response contain parameters needed in the
following step.

Once a websocket connection to the printer is created, a single message is sent
to it requesting "status" updates. The program loops, receiving the messages
until it is stopped by pressing ENTER at the terminal/command line.

```shell
python3 cc_recorder.py <logfile> <ip-addr>
```

`logfile` is where the messages are stored. Default = "cc-log.json".

`ip-addr` is an optional specific printer's IP address to connect with.
Useful when more thanone printer (or a printer and `cc_player`) is active
on the network.

#### Update:

`cc_recorder` has been updated to replace the original TimeStamp field (Unix epoch
number of seconds since 1970-01-01) with the relative number of seconds
since the previous message. This allows for easier manual editing of files
to reduce the number (and time) of emulated records.

### cc_player.py

This script is a Websocket server that a monitor program can connect to
without bothering a real printer. It responds to broadcast requests, using the
desktop's IP address and machine name in place of the normal CC ones. When it
gets a request for status messages, it will send them to the client until it
disconnects or the program is terminated (press ENTER at the terminal).

The messages are read from a file created by `cc_recorder.py`. Some
machine-specific fields are replaced such as the "TimeStamp" field,
which gets the current time.
Before the message is sent, this program delays for the
number of seconds difference between the previous and current messages. This
more closely emulates a real printer's operation than would just flooding the
client with a slew of messages.

When the end of the file is reached, after a short delay, the program starts
over again at the beginning of the file.

```shell
python3 cc_player.py <logfile> <speed>
```

`logfile` contains messages to be sent. Default = "cc-log.json".

`speed` is a rate multiplier for the delay between messages.
0.5 is used for half-speed; 1.0 for normal speed (default) and 2.0 would be
double-speed.

#### Update:
`cc_player` has been updated to handle the "record relative" TimeStamp fields
produced by `cc_recorder`. (It will also handle the older "full timestamp"
files as well.)

### status_changes.py

This script will process a file created by `cc_recorder.py` and output a
record whenever the "Machine" or "Print" status changes along with the number
of seconds spent in that state. This allows one to get an overview of the
printer's "state changes". (Without this, I never would have realized that the
"Machine" status was changing while the "Print" status was staying in "IDLE".)

```shell
python3 status_changes.py <logfile> <outfile>
```

`logfile` is where the messages are stored. Default = "cc-log.json".

`outfile` is where to store the output. Default = the `logfile` path with '.json'
replaced by '.txt'.
