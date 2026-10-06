import socket
import types, selectors
from .lucidserver import PORT
import pathlib
import logging
from .imageencoding import decodeimage, IMAGEENDSTRING
from selectors import SelectorKey, DefaultSelector
import matplotlib.pyplot as plt
import cv2
import time
import os
logger = logging.getLogger()
home = pathlib.Path.home()

class LucidClient():
    def __init__(self, host, port=PORT, connid = socket.gethostname()):
        self.host= host
        self.port = port
        self.connid = connid
        
        logfile = f'{home}/.config/lucidlog/client.log'
        os.makedirs(os.path.dirname(logfile),exist_ok=True)
        loglevel = logging.INFO

        logging.basicConfig(filename=logfile, level = loglevel, format = '%(asctime)s %(levelname)-8s %(message)s',
                            datefmt = '%Y/%m/%d_%H:%M:%S')
        
    def requestimage(self):
        '''
        requests currently stored image
        '''
        print(f'requesting image from {self.host}:{self.port}')
        data = self.multiClient(b'request!')
        if b'no image' in data:
            print('no image currently on server')
            return
        return decodeimage(data)

    def requestimagebytes(self):
        '''
        gets image byte string from server, but doesn't decode
        '''
        print(f'requesting image from {self.host}:{self.port}')
        return self.multiClient(b'request!')

    def saverequest(self):
        '''
        tells server to save a new image
        '''
        print(f'asking server to save an image at {self.host}:{self.port}')
        return self.multiClient(b'save!')

    def requestnewimage(self):
        data = self.multiClient(b"requestnew!")
        return decodeimage(data)

    def requestnewimage_old(self, waittime = 0.1):
        '''
        asks server to save a new image, then requests the stored image
        '''
        self.saverequest()
        time.sleep(waittime) #give time to encode image. Maybe unnecessary as now server waits for signal
        return self.requestimage()

    def takesnapshot(self):
        print(f'asking server to take snapshot at {self.host}:{self.port}')
        return self.multiClient(b'snapshot!').decode()

    def plotimage(self, dpi = 150):
        '''
        requests current image from server, then plots it
        '''
        image = self.requestimage()
        if image is None:
            return   
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        plt.figure(dpi = dpi)
        plt.imshow(image)
        plt.show()
        return image
    
    def plotnewimage(self, dpi = 150):
        '''
        asks server to save new image, then requests image and plots it
        '''
        self.saverequest()
        time.sleep(0.1)
        return self.plotimage(dpi=dpi)


    def multiClient(self,message):
        sel = selectors.DefaultSelector()
        server_addr = (self.host, self.port)
        print(f"Starting connection {self.connid} to {server_addr}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        #sock.setblocking(False)
        sock.connect_ex(server_addr)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        data = types.SimpleNamespace(
            connid=self.connid,
            msg_total=len(message),
            recv_total=0,
            messages=[message],
            outb=b"",
        )
        sel.register(sock, events, data=data)
        try:
            while True:
                events = sel.select(timeout=1)
                if events:
                    for key, mask in events:
                        receivedMessage = self.service_connection(key, mask,sel)

                # Check for a socket being monitored to continue.
                if not sel.get_map():
                    break
        except KeyboardInterrupt:
            print("Caught keyboard interrupt, exiting")
        except Exception as e:
            logger.exception(f'host: {self.host}, port {self.port}:\n{e}')
            raise e
        finally:
            sel.close()
        return receivedMessage

    def service_connection(self,key:SelectorKey, mask:int,sel:DefaultSelector):
        sock = key.fileobj
        data = key.data
        receivedMessage = b''
        possibleresponses = [b'ok!', b'invalid request!',b"no image stored currently!", b"camera not running!"]
        if mask & selectors.EVENT_READ:
            while True:
                recv_data = sock.recv(1024)  # Should be ready to read
                if recv_data:
                    #print(f"Received {recv_data!r} from connection {data.connid}")
                    receivedMessage+= recv_data
                    data.recv_total += len(recv_data)

                if not recv_data or IMAGEENDSTRING in receivedMessage or receivedMessage in possibleresponses or \
                receivedMessage.endswith(b'.png'):
                    print(f"Closing connection {data.connid}")
                    sel.unregister(sock)
                    sock.close()
                    if recv_data:
                        return receivedMessage
                    return
                
        if mask & selectors.EVENT_WRITE:
            if not data.outb and data.messages:
                data.outb = data.messages.pop(0)
            if data.outb:
                print(f"Sending data to connection {data.connid}")
                sent = sock.send(data.outb)  # Should be ready to write
                data.outb = data.outb[sent:]