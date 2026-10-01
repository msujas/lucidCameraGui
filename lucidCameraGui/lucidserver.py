from PyQt6.QtNetwork import QTcpServer

PORT = 51678
class LucidServer(QTcpServer):
    def __init__(self, handler, host, port:int=PORT, parent = None):
        super().__init__(parent)
        self.handler = handler
        self.newConnection.connect(self._onConnection)
        self.listen(host, port)
        self.image = None
        
    def _onConnection(self):
        sock = self.nextPendingConnection()
        def onready():
            data = sock.readAll().data().decode()
            self.handler( data, sock)
        sock.readyRead.connect(onready)
        sock.disconnected.connect(sock.deleteLater)

