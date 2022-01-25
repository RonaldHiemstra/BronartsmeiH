"""Boot script.

This file is executed on every boot (including wake-boot from deepsleep)
"""
import gc
import time
import esp
import network
import webrepl
try:
    from config import Config
    from status import state
except ImportError:
    # Try to (hardcoded) connect to WIFI and start webrepl
    import recovery_boot
    raise

esp.osdebug(None)
gc.collect()

network_config = Config('network_config.json')


def connect_wifi(essid, password, accesspoints, timeout=60):
    """Connect to the specified essid with the given password.

    @param[in,out] accesspoints Set of accesspoints which will be extended with detected accesspoints.
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    project_name = network_config.get('project_name')
    if project_name is not None:
        wlan.config(dhcp_hostname=project_name)

    accesspoints |= set([accesspoint_info[0].decode() for accesspoint_info in wlan.scan()])
    if essid not in accesspoints:
        print('WARNING: %s not found in the list of detected accesspoints:' % essid)
        for accesspoint in detected_accesspoints:
            print('\t%s' % accesspoint)
    if not wlan.isconnected():
        print('connecting to network: %s...' % essid)
        wlan.connect(essid, password)
        state.set_state('WIFI', state.GREEN | state.BLINK, 'Connecting to access point')
        start_time = time.time()
        while not wlan.isconnected():
            print('.', end='')
            state.update()
            if time.time() - start_time > timeout:
                print('\nFailed to connect within %ds' % timeout)
                wlan.disconnect()
                wlan.active(False)
                state.set_state('WIFI', state.RED, 'Failed to connected to access point')
                return False
            time.sleep(0.3)
    state.set_state('WIFI', state.GREEN, 'Connected to access point')
    print('\nnetwork config:', wlan.ifconfig())
    return True


def start_ap():
    """Start ESP brewery in (open) accesspoint mode."""
    print('Starting local accesspoint ESP-brewery')
    wlan = network.WLAN(network.AP_IF)
    essid = 'ESP-brewery_%d' % hash(wlan.config('mac'))
    wlan.active(True)
    wlan.config(essid=essid)
    state.set_state('WIFI', state.GREEN | state.RED | state.BLINK, 'Access point active')


detected_accesspoints = set()

if not connect_wifi(network_config.get('ssid'), network_config.get('__password'), accesspoints=detected_accesspoints):
    start_ap()

webrepl.start()

state.start_auto_update()
