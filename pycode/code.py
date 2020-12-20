from main.ota_updater import OTAUpdater 
from main.secrets import secrets

def download_and_install_update_if_available():
    global o
    o = OTAUpdater('https://github.com/betpagal/House')
    o.download_and_install_update_if_available(secrets["ssid"], secrets["password"])

def start():
    o.check_for_update_to_install_during_next_reboot()
    from main.stair_slave import stair_slave
    project = stair_slave()

def boot():
    download_and_install_update_if_available()
    start()
    
boot()