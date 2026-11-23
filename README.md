# ble_rssi_lock

Tools for (un)locking unix based computer with bluetooth rssi distance range.


## Requirements

- Python 3.12 or newer (verified on Python 3.14)
- BlueZ and a working Bluetooth adapter (`bluez`)
- `xfce4-screensaver-command` (`xfce4-screensaver`)

### Install the dependencies

The systemd units below always run `/usr/bin/python3`, so the dependencies must be importable
by the **system** interpreter: having them in a virtualenv is not enough.

On Debian/Ubuntu, the simplest route is the distribution packages:

```shell
sudo apt-get install python3-bleak python3-systemd
```

The only very important dependency is `bleak`, a python library for bluetooth low energy,
packaged as `python3-bleak`. `python3-systemd` provides
`systemd.journal.JournalHandler`, which the script uses to write into the journal.

With pip instead:

```shell
sudo apt-get install libsystemd-dev python3-dev
pip install --user --break-system-packages -r requirements.txt
```

`systemd-python` only ships as a source distribution, hence the two `-dev` packages. On recent
Debian/Ubuntu releases the system interpreter is marked "externally managed" (PEP 668), so pip
refuses to touch it without `--break-system-packages`; `--user` installs into `~/.local`, which
`/usr/bin/python3` does read.

Prefer a virtualenv? Then `ExecStart` has to point at its interpreter, otherwise the service
dies immediately with `ModuleNotFoundError: No module named 'bleak'`:

```ini
ExecStart=/path/to/venv/bin/python /usr/local/bin/ble_rssi_lock.py
```

Leave `bleak` unpinned (`bleak>=1.0`). `bleak==0.22.3` declares `Requires-Python <3.14` and
cannot even be installed on a current interpreter. `bleak` 1.0 dropped `BLEDevice.rssi`, but
the script reads `AdvertisementData.rssi` through `discovered_devices_and_advertisement_data`,
so it works from 0.22 up to 3.x.

Also, you might think python code are the same between root and non root but it's not the case.
The main difference is the way to lock/unlock the screen. You can't use `xfce4-screensaver-command` as root.
You need to specify the `XDG_RUNTIME_DIR` and `DISPLAY` environment variables to make it work.


## Usage

You can deploy the service as root on non root.

Depending on your device distance with your computer, it will (un)lock your computer.

Simply retrieve your device `MAC_ADDRESS` by connecting it via bluetooth and launch the service.

`MAC_ADDRESS` must be the address your phone advertises over Bluetooth Low Energy, which is not
always the address the desktop bluetooth applet shows. If the service runs but never logs a
`rssi:` line, see [Find the right MAC address](#find-the-right-mac-address).

### Non root (recommended)

#### Config

Create a config file in `$HOME/.config/systemd/user/ble_rssi_lock/config.ini`
```shell
nano $HOME/.config/systemd/user/ble_rssi_lock/config.ini
```
with this content:
```ini
[Service]
mac_address=<PHONE_MAC_ADDRESS>
period=0.5

# Min distance and time before unlocking
# ~50cm
min_rssi=-65
# in seconds
min_timestamp=0.5


# Max distance and time before locking
# ~5m
max_rssi=-80
# in seconds
max_timestamp=2
```
Replace `PHONE_MAC_ADDRESS` by the mac address of your phone you can find when connecting phone to bluetooth.
You can modify rssi and timestamp variables to your needs.

#### Script

Create the python script in `/usr/local/bin/ble_rssi_lock.py` with this content:
```python
import os
import configparser
import subprocess
import time
import asyncio
import re
import logging
from systemd.journal import JournalHandler

log = logging.getLogger('ble_rssi_lock')
log.addHandler(JournalHandler())
log.setLevel(logging.INFO)

from bleak import BleakScanner

# Get the config file path from the environment variable
config_path = os.getenv('CONFIG_PATH')
if not config_path:
    raise ValueError("CONFIG_PATH environment variable not set")

# Load config.ini file
config = configparser.ConfigParser()
config.read(config_path)

mac_address = config['Service']['mac_address']
period = float(config['Service']['period']) or 0.5
min_rssi = float(config['Service']['min_rssi']) or -65 # ~50cm
min_timestamp = float(config['Service']['min_timestamp']) or 0.5 # in seconds
max_rssi = float(config['Service']['max_rssi']) or -80 # ~5m
max_timestamp = float(config['Service']['max_timestamp']) or 5 # in seconds

async def main():
    # Create a BleakScanner object with the detection callback
    scanner = BleakScanner()

    start_timestamp_locked = None
    start_timestamp_unlocked = None

    auto_locked = None

    # Start continuous scanning
    await scanner.start()
    try:
        while True:
            try:
                result = subprocess.check_output(['xfce4-screensaver-command', '-q'], text=True)
            except Exception:
                is_locked = False
            else:
                is_locked = re.search(r'\sactive', result)

            target_device = next((v for k, v in scanner.discovered_devices_and_advertisement_data.items() if k == mac_address), None)
            if target_device is not None:
                rssi = target_device[1].rssi
                log.info(f'rssi: {rssi}')
                print(rssi)

                current_timestamp = time.time()
                # unlock if locked and rssi greater than min_rssi during min_timestamp seconds
                if is_locked or auto_locked:
                    if rssi > min_rssi:
                        if start_timestamp_locked is None:
                            start_timestamp_locked = current_timestamp
                        if start_timestamp_locked + min_timestamp < current_timestamp:
                            log.info('Will attempt to unlock screen')
                            os.system('xfce4-screensaver-command -d')
                            start_timestamp_locked = None
                            if auto_locked:
                                auto_locked = False
                    else:
                        start_timestamp_locked = None
                # lock if unlocked and rssi lower than max_rssi during max_timestamp seconds
                else:
                    if rssi < max_rssi:
                        if start_timestamp_unlocked is None:
                            start_timestamp_unlocked = current_timestamp
                        if start_timestamp_unlocked + max_timestamp < current_timestamp and auto_locked != True:
                            log.info('Will attempt to lock screen')
                            os.system('xfce4-screensaver-command --lock')
                            start_timestamp_unlocked = None
                            auto_locked = True
                    else:
                        start_timestamp_unlocked = None

            await asyncio.sleep(period)
    except asyncio.CancelledError:
        await scanner.stop()

asyncio.run(main())
```

#### Service

Create a service file in `$HOME/.config/systemd/user/ble_rssi_lock.service`:
```shell
nano $HOME/.config/systemd/user/ble_rssi_lock.service
```
with this content
```service
[Unit]
Description=BLE rssi autolock

[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/ble_rssi_lock.py
WorkingDirectory=%h
Environment=CONFIG_PATH=.config/systemd/user/ble_rssi_lock/config.ini
StandardOutput=inherit
StandardError=inherit
Restart=always

[Install]
WantedBy=default.target
```

Launch the service:
```shell
systemctl --user daemon-reload
systemctl --user enable --now ble_rssi_lock.service
systemctl --user restart ble_rssi_lock.service
```
Display logs:
```shell
journalctl --user -u ble_rssi_lock.service -f
```

The script reads `config.ini` once at startup, so restart the unit after every config change.
If a previous crash left the unit in a failed state, `systemctl --user restart` is not enough:
see [`Start request repeated too quickly`](#start-request-repeated-too-quickly).

### Root

#### Config

Create a config file in `/etc/ble_rssi_lock/config.ini`


```shell
sudo nano /etc/ble_rssi_lock/config.ini
```
with this content:
```ini
[Service]
mac_address=<PHONE_MAC_ADDRESS>
period=0.5

# Min distance and time before unlocking
 # ~50cm
min_rssi=-65
# in seconds
min_timestamp=0.5


# Max distance and time before locking
# ~5m
max_rssi=-80
# in seconds
max_timestamp=2
```
Replace `PHONE_MAC_ADDRESS` by the mac address of your phone you can find when connecting phone to bluetooth.
You can modify rssi and timestamp variables to your needs.

#### Script

Create the python script in `/usr/bin/ble_rssi_lock.py` with this content:
```python
import os
import configparser
import subprocess
import time
import asyncio
import re
import logging
from systemd.journal import JournalHandler

log = logging.getLogger('ble_rssi_lock')
log.addHandler(JournalHandler())
log.setLevel(logging.INFO)

from bleak import BleakScanner

# Get the config file path from the environment variable
config_path = os.getenv('CONFIG_PATH')
if not config_path:
    raise ValueError("CONFIG_PATH environment variable not set")

# Load config.ini file
config = configparser.ConfigParser()
config.read(config_path)

mac_address = config['Service']['mac_address']
period = float(config['Service']['period']) or 0.5
min_rssi = float(config['Service']['min_rssi']) or -65 # ~50cm
min_timestamp = float(config['Service']['min_timestamp']) or 0.5 # in seconds
max_rssi = float(config['Service']['max_rssi']) or -80 # ~5m
max_timestamp = float(config['Service']['max_timestamp']) or 5 # in seconds

async def main():
    # Create a BleakScanner object with the detection callback
    scanner = BleakScanner()

    start_timestamp_locked = None
    start_timestamp_unlocked = None

    auto_locked = None

    # Start continuous scanning
    await scanner.start()
    try:
        while True:
            try:
                result = subprocess.check_output(['xfce4-screensaver-command', '-q'], text=True, env={'XDG_RUNTIME_DIR': '/run/user/1000', 'DISPLAY': '0.0'})
            except Exception:
                is_locked = False
            else:
                is_locked = re.search(r'\sactive', result)

            target_device = next((v for k, v in scanner.discovered_devices_and_advertisement_data.items() if k == mac_address), None)
            if target_device is not None:
                rssi = target_device[1].rssi
                log.info(f'rssi: {rssi}')
                print(rssi)

                current_timestamp = time.time()
                # unlock if locked and rssi greater than min_rssi during min_timestamp seconds
                if is_locked or auto_locked:
                    if rssi > min_rssi:
                        if start_timestamp_locked is None:
                            start_timestamp_locked = current_timestamp
                        if start_timestamp_locked + min_timestamp < current_timestamp:
                            log.info('Will attempt to unlock screen')
                            os.system('XDG_RUNTIME_DIR=/run/user/1000 DISPLAY=:0.0 xfce4-screensaver-command -d')
                            start_timestamp_locked = None
                            if auto_locked:
                                auto_locked = False
                    else:
                        start_timestamp_locked = None
                # lock if unlocked and rssi lower than max_rssi during max_timestamp seconds
                else:
                    if rssi < max_rssi:
                        if start_timestamp_unlocked is None:
                            start_timestamp_unlocked = current_timestamp
                        if start_timestamp_unlocked + max_timestamp < current_timestamp and auto_locked != True:
                            log.info('Will attempt to lock screen')
                            os.system('XDG_RUNTIME_DIR=/run/user/1000 DISPLAY=:0.0 xfce4-screensaver-command --lock')
                            start_timestamp_unlocked = None
                            auto_locked = True
                    else:
                        start_timestamp_unlocked = None

            await asyncio.sleep(period)
    except asyncio.CancelledError:
        await scanner.stop()

asyncio.run(main())
```

#### Service

Create a service file in `/etc/systemd/system/ble_rssi_lock.service`:
```shell
sudo nano /etc/systemd/system/ble_rssi_lock.service
```
with this content
```service
[Unit]
Description=BLE rssi autolock

[Service]
ExecStart=/usr/bin/python3 /usr/bin/ble_rssi_lock.py
WorkingDirectory=%h
Environment=CONFIG_PATH=/etc/ble_rssi_lock/config.ini
StandardOutput=inherit
StandardError=inherit
Restart=always
User=yourusername

[Install]
WantedBy=multi-user.target
```

Unit files do not expand shell variables: `User=` needs a real user name, and `%h` is the
systemd specifier for the home directory of that user.

Launch the service
```shell
sudo systemctl daemon-reload
sudo systemctl enable ble_rssi_lock.service
sudo systemctl restart ble_rssi_lock.service
```

Display logs:
```shell
journalctl -u ble_rssi_lock.service -f
```

This is a system unit, so it logs to the system journal: drop the `--user` flag you use for the
non root deployment.

## Troubleshooting

### The service fails with `ModuleNotFoundError: No module named 'bleak'`

The dependencies live somewhere `/usr/bin/python3` cannot see, usually a virtualenv. Install
them for the system interpreter, or point `ExecStart` at the interpreter of the virtualenv.
`python3 -c "import bleak"` is the quickest way to check what the interpreter the unit runs can
actually import.

### `Start request repeated too quickly`

`Restart=always` combined with a script that exits right away burns the restart budget, and then
systemd refuses to start the unit again even once the real cause is fixed. Reset the counter
before restarting:

```shell
systemctl --user reset-failed ble_rssi_lock.service
systemctl --user restart ble_rssi_lock.service
```

### The unit is active but the journal shows no `rssi:` line

The script logs one line per reading, every `period` seconds, and only while it sees the
configured address. Nothing at all means the scanner never matches `mac_address`. The adapter is
rarely the suspect here; `hciconfig -a` should show `UP RUNNING`.

#### Find the right MAC address

`mac_address` must be the address the phone advertises over BLE, spelled exactly the way BlueZ
reports it: the script compares plain strings with `==`, so uppercase and colon separated.

Read the address in a bluetooth manager (`blueman-manager` device properties, or
`bluetoothctl devices`) and look at `AddressType`:

- `public`: stable, safe to configure.
- `random`: most phones rotate resolvable private addresses, so the entry stops being refreshed
  and the lock/unlock logic stays stuck on the last reading.

Then check what the scanner really receives:

```shell
timeout 25 python3 -c "
import asyncio
from bleak import BleakScanner
async def main():
    seen = await BleakScanner.discover(timeout=20, return_adv=True)
    for address, (device, adv) in sorted(seen.items(), key=lambda kv: -kv[1][1].rssi):
        print(f'{address}  rssi={adv.rssi}  name={device.name}')
asyncio.run(main())
"
```

If the phone shows up under another address, that is the address to configure.

### `AttributeError: 'BLEDevice' object has no attribute 'rssi'`

`bleak` 1.0 removed `BLEDevice.rssi`. Read the value on the advertisement data instead:
`BleakScanner.discover(timeout=20, return_adv=True)` returns `{address: (BLEDevice,
AdvertisementData)}` and `AdvertisementData.rssi` holds the current reading.

### `The unit file, source configuration file or drop-ins ... changed on disk`

Run `systemctl --user daemon-reload`, or `sudo systemctl daemon-reload` for the root unit, after
editing a unit file.

## TODO:

- support different screensavers
```shell
screensavers = {
  'GNOME': 'gnome-screensaver',
  'MATE': 'mate-screensaver-command',
  'XSCREENSAVER': 'xscreensaver',
  'XFCE4SCREENSAVERCOMMANDLOCK': 'xfce4-screensaver-command --lock'
}
```
- Make code more dynamic giving root/non root
- Make service more dynamic by putting the mac address directly inside the service.

```shell
To use the MAC address from the service file name as an argument, you can use a systemd template service. Here is how you can do it:

1. Create a template service file named `ble_rssi_lock@.service`:

sudo nano $HOME/.config/systemd/user/ble_rssi_lock@.service

2. Update the content of the template service file to use the MAC address as an argument:

[Unit]
Description=BLE rssi autolock for %I

[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/ble_rssi_lock.py %I
WorkingDirectory=$HOME
Environment=CONFIG_PATH=.config/systemd/user/ble_rssi_lock/config.ini
StandardOutput=inherit
StandardError=inherit
Restart=always

[Install]
WantedBy=default.target

3. Enable and start the service with the MAC address:


systemctl --user enable --now ble_rssi_lock@<MAC_ADDRESS>.service
systemctl --user restart ble_rssi_lock@<MAC_ADDRESS>.service


In this setup, `%I` is a placeholder that systemd replaces with the instance name (the MAC address in this case). The Python script can then retrieve this argument using `sys.argv[1]`.
```
