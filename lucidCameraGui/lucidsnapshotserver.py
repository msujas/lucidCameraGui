import asyncio
from .lucidserver import PORT
from .lucidclient import LucidClient
import argparse, subprocess, os
from PIL import Image
import time
from datetime import datetime
import cv2

EPORT = 56737

def getdtstring():
    t = time.time()
    dt = datetime.fromtimestamp(t)
    return f'{dt.year:04d}{dt.month:02d}{dt.day:02d}_{dt.hour:02d}{dt.minute:02d}{dt.second:02d}'

def parseargs():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', type = str, default='127.0.0.1', help='host for export server (default localhost)')
    ap.add_argument('--port',type = int, default=EPORT, help= f'export server port (default {EPORT})')
    ap.add_argument('--lhost',type = str, help='Lucid server host', required=True)
    ap.add_argument('--lport',type = int,default=PORT, help=f'lucid server port (default {PORT})')
    #ap.add_argument('--username',type=str,help = 'username on Lucid camera PC (needed to copy snapshots over)',required=True)
    args = ap.parse_args()
    return args.host, args.port, args.lhost, args.lport

class LucidExportServer():
    def __init__(self):
        self.host,self.port,self.lhost,self.lport = parseargs()
        self.lclient = LucidClient(self.lhost,self.lport)
        print(f'Using Lucid server at {self.lhost}:{self.lport}')
        self.looptask: asyncio.Task | None = None
        self.shutdownevent = asyncio.Event()
    async def mainloop(self, localdir, waittime):
        try:
            while True:
                array = self.lclient.requestnewimage()
                outfile = f'{localdir}/{getdtstring()}.png'
                print(f'saving {outfile}')
                im = Image.fromarray(cv2.cvtColor(array, cv2.COLOR_BGR2RGB))
                im.save(outfile)
                await asyncio.sleep(waittime)
        except asyncio.CancelledError:
            print('main loop stopped')
            raise
        except TimeoutError | AttributeError:
            print('no data returned. Check Lucid server is running')
            raise asyncio.CancelledError
        except:
            print('error. Loop stopped')

    def is_running(self):
        return self.looptask is not None and not self.looptask.done()

    async def processCommand(self,line:str):
        cmd = line.split()[0]
        args = line.replace(cmd,'').strip()

        match cmd.lower():
            case 'run':
                try:
                    localdir,waittime = args.split('|')
                except ValueError:
                    return "invalid arguments. Must be in format 'run <dirname>|<waittime>"
                waittime = float(waittime)
                if self.is_running():
                    self.looptask.cancel()
                self.looptask = asyncio.create_task(self.mainloop(localdir,waittime))
                return 'started'
            case 'stop':
                if not self.is_running():
                    return 'not running'
                self.looptask.cancel()
                try:
                    await self.looptask
                except asyncio.CancelledError:
                    pass
                return 'stopped'
            case 'status':
                return 'running' if self.is_running() else 'not running'
            case _:
                return f'unknown command {cmd}'

    async def handleclient(self,reader:asyncio.StreamReader, writer:asyncio.StreamWriter):
        addr = writer.get_extra_info('peername')
        print(f'client connected: {addr}')
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                line = data.decode().strip()
                if not line:
                    continue
                if line.lower() =='quit':
                    writer.write('bye\n')
                    await writer.drain()
                    break
                reply = await self.processCommand(line)
                writer.write(f'{reply}\n'.encode())
                await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            print(f'client disconnected: {addr}')

    async def run(self):
        server = await asyncio.start_server(self.handleclient, self.host,self.port)
        print(f'listening on {self.host}:{self.port}')
        async with server:
            await self.shutdownevent.wait()
        if self.is_running():
            self.looptask.cancel()
        print('server closed')

def main():
    try:
        asyncio.run(LucidExportServer().run())
    except KeyboardInterrupt:
        print('caught keyboard interrupt. Exiting')