#import os
#import gc
import supervisor
import board
import busio
from digitalio import DigitalInOut
import main.lib.adafruit_requests as requests
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_esp32spi import adafruit_esp32spi
from main.secrets import secrets

class OTAUpdater:

    def __init__(self, github_repo, module='', main_dir='', headers={}):
        print('in OTAUpdater.__init__')
        self.github_repo = github_repo.rstrip('/').replace('https://github.com', 'https://api.github.com/repos')
        print ('self.github_repo: ', self.github_repo)
        self.main_dir = main_dir
        print ('self.main_dir: ', self.main_dir)
        self.module = module.rstrip('/')
        print ('self.module: ', self.module)
        
    @staticmethod
    def using_network():
        print('in using_network')
        # using AirLift Shield:
        esp32_cs = DigitalInOut(board.D10)
        esp32_ready = DigitalInOut(board.D9)
        esp32_reset = DigitalInOut(board.D5)

        spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
        esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

        requests.set_socket(socket, esp)

        if esp.status == adafruit_esp32spi.WL_IDLE_STATUS:
            print("ESP32 found and in idle mode")
        print("Firmware vers.", esp.firmware_version)
        print("MAC addr:", [hex(i) for i in esp.MAC_address])

        print("Connecting to AP...")
        while not esp.is_connected:
            try:
                esp.connect_AP(secrets["ssid"], secrets["password"])
            except RuntimeError as e:
                print("could not connect to AP, retrying: ", e)
                continue
        print("Connected to", str(esp.ssid, "utf-8"), "\tRSSI:", esp.rssi)
        print("My IP address is", esp.pretty_ip(esp.ip_address))

#        print('in using_network')
#        import network
#        sta_if = network.WLAN(network.STA_IF)
#        if not sta_if.isconnected():
#            print('connecting to network...')
#            sta_if.active(True)
#            sta_if.connect(ssid, password)
#            while not sta_if.isconnected():
#                pass
#        print('network config:', sta_if.ifconfig())

    def check_for_update_to_install_during_next_reboot(self):
        print('in check_for_update_to_install_during_next_reboot')
        print('self.main_dir: ', self.main_dir)
        current_version = self.get_version(self.modulepath(self.main_dir))
        latest_version = self.get_latest_version()

        print('Checking version... ')
        print('\tCurrent version: ', current_version)
        print('\tLatest version: ', latest_version)
        if latest_version > current_version:
            print('New version available, will download and install on next reboot')
            os.mkdir(self.modulepath('next'))
            with open(self.modulepath('next/.version_on_reboot'), 'w') as versionfile:
                versionfile.write(latest_version)
                versionfile.close()

    def download_and_install_update_if_available(self, ssid, password):
        print('in download_and_install_update_if_available')
        print(os.listdir(self.module))
        if 'next' in os.listdir(self.module):
            print('found next')
            if '.version_on_reboot' in os.listdir(self.modulepath('next')):
                print('found .version_on_reboot')
                latest_version = self.get_version(self.modulepath('next'), '.version_on_reboot')
                print('New update found: ', latest_version)
                self._download_and_install_update(latest_version, ssid, password)
        else:
            print('No new updates found...')

    def _download_and_install_update(self, latest_version, ssid, password):
        print('in _download_and_install_update')
        OTAUpdater.using_network()
        source = self.github_repo + '/contents/' + self.main_dir
        print('source: ', source)
        self.download_all_files(source, latest_version)
        self.rmtree(self.modulepath(self.main_dir))
        os.rename(self.modulepath('next/.version_on_reboot'), self.modulepath('next/.version'))
        os.rename(self.modulepath('next'), self.modulepath(self.main_dir))
        print('Update installed (', latest_version, '), will reboot now')
        supervisor.reload()

    def apply_pending_updates_if_available(self):
        if 'next' in os.listdir(self.module):
            if '.version' in os.listdir(self.modulepath('next')):
                pending_update_version = self.get_version(self.modulepath('next'))
                print('Pending update found: ', pending_update_version)
                self.rmtree(self.modulepath(self.main_dir))
                os.rename(self.modulepath('next'), self.modulepath(self.main_dir))
                print('Update applied (', pending_update_version, '), ready to rock and roll')
            else:
                print('Corrupt pending update found, discarding...')
                self.rmtree(self.modulepath('next'))
        else:
            print('No pending update found')

    def download_updates_if_available(self):
        current_version = self.get_version(self.modulepath(self.main_dir))
        latest_version = self.get_latest_version()

        print('Checking version... ')
        print('\tCurrent version: ', current_version)
        print('\tLatest version: ', latest_version)
        if latest_version > current_version:
            print('Updating...')
            os.mkdir(self.modulepath('next'))
            self.download_all_files(self.github_repo + '/contents/' + self.main_dir, latest_version)
            with open(self.modulepath('next/.version'), 'w') as versionfile:
                versionfile.write(latest_version)
                versionfile.close()

            return True
        return False

    def rmtree(self, directory):
        for entry in os.ilistdir(directory):
            is_dir = entry[1] == 0x4000
            if is_dir:
                self.rmtree(directory + '/' + entry[0])

            else:
                os.remove(directory + '/' + entry[0])
        os.rmdir(directory)

    def get_version(self, directory, version_file_name='.version'):
        print('in get_version(', directory, ',', version_file_name, ')')
        if version_file_name in os.listdir(directory):
            f = open(directory + '/' + version_file_name)
            version = f.read()
            f.close()
            return version
        return '0.0'

    def get_latest_version(self):
        print('in get_latest_version')
        OTAUpdater.using_network()
        dest_path = self.github_repo + '/releases/latest'
        print('dest_path: ', dest_path)
        latest_release = requests.get(dest_path)
        print('latest_release: ', latest_release)
#        latest_release = self.http_client.get(self.github_repo + '/releases/latest')
        version = latest_release.json()['tag_name']
        print('version: ', version)
        latest_release.close()
        return version

    def download_all_files(self, root_url, version):
        #file_list = self.http_client.get(root_url + '?ref=refs/tags/' + version)
        dest_path = root_url + '?ref=refs/tags/' + version
        print('dest_path: ', dest_path)
        file_list = requests.get(dest_path)
        for file in file_list.json():
            if file['type'] == 'file':
                download_url = file['download_url']
                download_path = self.modulepath('next/' + file['path'].replace(self.main_dir + '/', ''))
                self.download_file(download_url.replace('refs/tags/', ''), download_path)
            elif file['type'] == 'dir':
                path = self.modulepath('next/' + file['path'].replace(self.main_dir + '/', ''))
                os.mkdir(path)
                self.download_all_files(root_url + '/' + file['name'], version)

        file_list.close()
 
    def download_file(self, url, path):
        print('url: ', url, '\path: ', path)
        with open(path, 'w') as outfile:    
            response = requests.get(url)
            try:
                outfile.write(response.text) 
            except RuntimeError as e:
                print('error caught while downloading file')
                print(type(e))    # the exception instance
                print(e.args)     # arguments stored in .args
                print(e)          # __str__ allows args to be printed directly,
                                  # but may be overridden in exception subclasses
            finally:
                response.close()
                outfile.close()
                gc.collect()

    def modulepath(self, path):
        return self.module + '/' + path if self.module else path


# class Response:

#     def __init__(self, f):
#         self.raw = f
#         self.encoding = 'utf-8'
#         self._cached = None

#     def close(self):
#         if self.raw:
#             self.raw.close()
#             self.raw = None
#         self._cached = None

#     @property
#     def content(self):
#         if self._cached is None:
#             try:
#                 self._cached = self.raw.read()
#             finally:
#                 self.raw.close()
#                 self.raw = None
#         return self._cached

#     @property
#     def text(self):
#         return str(self.content, self.encoding)

#     def json(self):
#         import ujson
#         return ujson.loads(self.content)


# class HttpClient:

#     def __init__(self, headers={}):
#         print('in HttpClient.__init__')
#         self._headers = headers

#     def request(self, method, url, data=None, json=None, headers={}, stream=None):
#         print('in HttpClient.request')
#         def _write_headers(sock, _headers):
#             print('in HttpClient.request._write_headers')
#             for k in _headers: 
#                 sock.write(b'{}: {}\r\n'.format(k, _headers[k]))

#         try:
#             proto, dummy, host, path = url.split('/', 3)
#         except ValueError:
#             proto, dummy, host = url.split('/', 2)
#             path = ''
#         if proto == 'http:':
#             port = 80
#         elif proto == 'https:':
#             import ussl
#             port = 443
#         else:
#             raise ValueError('Unsupported protocol: ' + proto)

#         if ':' in host:
#             host, port = host.split(':', 1)
#             port = int(port)

#         ai = usocket.getaddrinfo(host, port, 0, usocket.SOCK_STREAM)
#         ai = ai[0]

#         s = usocket.socket(ai[0], ai[1], ai[2])
#         try:
#             s.connect(ai[-1])
#             if proto == 'https:':
#                 s = ussl.wrap_socket(s, server_hostname=host)
#             s.write(b'%s /%s HTTP/1.0\r\n' % (method, path))
#             if not 'Host' in headers:
#                 s.write(b'Host: %s\r\n' % host)
#             # Iterate over keys to avoid tuple alloc
#             _write_headers(s, self._headers)
#             _write_headers(s, headers)

#             # add user agent
#             s.write('User-Agent')
#             s.write(b': ')
#             s.write('MicroPython OTAUpdater')
#             s.write(b'\r\n')
#             if json is not None:
#                 assert data is None
#                 import ujson
#                 data = ujson.dumps(json)
#                 s.write(b'Content-Type: application/json\r\n')
#             if data:
#                 s.write(b'Content-Length: %d\r\n' % len(data))
#             s.write(b'\r\n')
#             if data:
#                 s.write(data)

#             l = s.readline()
#             # print(l)
#             l = l.split(None, 2)
#             status = int(l[1])
#             reason = ''
#             if len(l) > 2:
#                 reason = l[2].rstrip()
#             while True:
#                 l = s.readline()
#                 if not l or l == b'\r\n':
#                     break
#                 # print(l)
#                 if l.startswith(b'Transfer-Encoding:'):
#                     if b'chunked' in l:
#                         raise ValueError('Unsupported ' + l)
#                 elif l.startswith(b'Location:') and not 200 <= status <= 299:
#                     raise NotImplementedError('Redirects not yet supported')
#         except OSError:
#             s.close()
#             raise

#         resp = Response(s)
#         resp.status_code = status
#         resp.reason = reason
#         return resp

#     def head(self, url, **kw):
#         return self.request('HEAD', url, **kw)

#     def get(self, url, **kw):
#         return self.request('GET', url, **kw)

#     def post(self, url, **kw):
#         return self.request('POST', url, **kw)

#     def put(self, url, **kw):
#         return self.request('PUT', url, **kw)

#     def patch(self, url, **kw):
#         return self.request('PATCH', url, **kw)

#     def delete(self, url, **kw):
#         return self.request('DELETE', url, **kw)
