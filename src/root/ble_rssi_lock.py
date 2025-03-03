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