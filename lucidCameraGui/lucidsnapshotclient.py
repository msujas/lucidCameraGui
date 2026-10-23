import socket
from .lucidsnapshotserver import EPORT

class LucidSnapshotClient():
    def __init__(self, host='localhost', port=EPORT):
        self.host = host
        self.port = port
    def sendmessage(self, message:str):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((self.host,self.port))
        s.sendall(f'{message}\n'.encode())
        return s.recv(1024).decode()
    def runexporter(self, dirname, waittime):
        data = self.sendmessage(f'run {dirname}|{waittime}')
        return data
    def stopexporter(self):
        data = self.sendmessage('stop')
        return data
    def getstatus(self):
        return self.sendmessage('status')