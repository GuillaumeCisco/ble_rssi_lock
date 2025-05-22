# ble_rssi_lock

Tools for (un)locking unix based computer with bluetooth rssi distance range.


## Requirements

- Python 3.12

```shell
sudo apt-get install libsystemd-dev python3-dev
pip install -r requirements.txt
```

The only very important dependency is `bleak` which is a python library for bluetooth low energy.
Also, you might think python code are the same between root and non root but it's not the case.
The main difference is the way to lock/unlock the screen. You can't use `xfce4-screensaver-command` as root.
You need to specify the `XDG_RUNTIME_DIR` and `DISPLAY` environment variables to make it work.


## Usage

You can deploy the service as root on non root.

Depending on your device distance with your computer, it will (un)lock your computer.

Simply retrieve your device `MAC_ADDRESS` by connecting it via bluetooth and launch the service.

### Non root (recommended)

#### Config

Put the config file in the user config directory:
```shell
mkdir -p $HOME/.config/systemd/user/ble_rssi_lock
cp src/config.ini $HOME/.config/systemd/user/ble_rssi_lock/config.ini
```

Replace `PHONE_MAC_ADDRESS` by the mac address of your phone you can find when connecting phone to bluetooth.
You can modify rssi and timestamp variables to your needs.

```shell
nano $HOME/.config/systemd/user/ble_rssi_lock/config.ini
```


#### Script

Put the python script in the user bin directory:
```shell
cp src/user/ble_rssi_lock.py /usr/local/bin/ble_rssi_lock.py
```

#### Service

Put the service file in the user config directory:
```shell
cp src/user/ble_rssi_lock.service $HOME/.config/systemd/user/ble_rssi_lock.service
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

### Root

#### Config

Put the config file in the system config directory:
```shell
mkdir -p /etc/ble_rssi_lock
cp src/config.ini /etc/ble_rssi_lock/config.ini
```

Replace `PHONE_MAC_ADDRESS` by the mac address of your phone you can find when connecting phone to bluetooth.
You can modify rssi and timestamp variables to your needs.

```shell
nano /etc/ble_rssi_lock/config.ini
```

#### Script

Put the python script in the system bin directory:
```shell
cp src/root/ble_rssi_lock.py /usr/bin/ble_rssi_lock.py
```

#### Service

Put the service file in the system config directory:
```shell
cp src/root/ble_rssi_lock.service /etc/systemd/system/ble_rssi_lock.service
```

Launch the service
```shell
sudo systemctl daemon-reload
sudo systemctl enable ble_rssi_lock.service
sudo systemctl restart ble_rssi_lock.service
```

Display logs:
```shell
journalctl --user -u ble_rssi_lock.service -f
```

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
