# LOGBOOK - Copyright 2026 Eduardo Arraia, CT7ASY. Todos os direitos reservados.
# Desenvolvido com assistencia de OpenAI Codex.
import re
import socket
import threading
from collections import deque

class DXCluster:
    def __init__(self):
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.thread = None
        self.sock = None
        self.spots = deque(maxlen=500)
        self.status = 'Desligado'
        self.sequence = 0

    def snapshot(self):
        with self.lock:
            return {'status': self.status, 'active': bool(self.thread and self.thread.is_alive() and not self.stop.is_set()), 'spots': list(self.spots)}

    def disconnect(self):
        self.stop.set()
        if self.sock:
            try: self.sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            self.sock.close()
        if self.thread: self.thread.join(timeout=12)
        with self.lock:
            self.status = 'Desligado'
            self.spots.clear()

    def connect(self, data):
        host = str(data.get('host', '')).strip()
        port = int(data.get('port', 7300))
        call = str(data.get('call', '')).strip().upper()
        if not host or len(host)>253 or not 1<=port<=65535 or not re.fullmatch(r'[A-Z0-9/]{3,20}(?:-[0-9]{1,2})?',call):
            raise ValueError('Preencha servidor, porta e indicativo validos.')
        self.disconnect()
        self.stop = threading.Event()
        with self.lock:
            self.status = 'A ligar...'
            self.spots.clear()
        self.thread = threading.Thread(target=self.run,args=(host,port,call,self.stop),daemon=True)
        self.thread.start()

    def parse(self,line):
        # Some DXSpider nodes append Telnet bell characters to live spots.
        line = line.replace('\x07', '')
        match=re.match(r'^DX de\s+([^: ]+):\s+([0-9]+(?:\.[0-9]+)?)\s+([A-Za-z0-9/\-]+)\s+(.*?)\s+(\d{4})Z(?:\s.*)?$',line.strip())
        historical=False
        if match:
            spotter,freq,call,comment,utc=match.groups()
        else:
            match=re.match(r'^\s*([0-9]+(?:\.[0-9]+)?)\s+([A-Za-z0-9/\-]+)\s+\d{1,2}-[A-Za-z]{3}-\d{4}\s+(\d{4})Z\s*(.*?)\s*<([^>]+)>\s*$',line)
            if not match:return
            freq,call,utc,comment,spotter=match.groups()
            historical=True
        if not 0<float(freq)<100000000 or int(utc[:2])>23 or int(utc[2:])>59:return
        with self.lock:
            self.sequence+=1
            (self.spots.append if historical else self.spots.appendleft)({'id':self.sequence,'historical':historical,'call':call.upper(),'freq':float(freq)/1000,'comment':comment,'spotter':spotter,'time':utc[:2]+':'+utc[2:]})

    def run(self,host,port,call,stop):
        while not stop.is_set():
            try:
                with socket.create_connection((host,port),timeout=10) as sock:
                    self.sock=sock
                    sock.settimeout(1)
                    buffer=''; prompt=''; logged=False; requested=False; telnet=0; command=0
                    with self.lock:self.status='Ligado - a aguardar login'
                    while not stop.is_set():
                        try: packet=sock.recv(4096)
                        except socket.timeout:continue
                        if not packet:raise OSError('Ligacao terminada pelo servidor')
                        clean=bytearray()
                        for byte in packet:
                            if telnet==0:
                                if byte==255:telnet=1
                                else:clean.append(byte)
                            elif telnet==1:
                                if byte in (251,252,253,254):command=byte;telnet=2
                                elif byte==250:telnet=3
                                else:telnet=0
                            elif telnet==2:
                                if command in (251,253):sock.sendall(bytes([255,254 if command==251 else 252,byte]))
                                telnet=0
                            elif telnet==3:
                                if byte==255:telnet=4
                            elif telnet==4:telnet=0 if byte==240 else 3
                        text=clean.decode('utf-8',errors='replace').replace('\r','')
                        prompt=(prompt+text)[-2048:]
                        if not logged and re.search(r'(?:login|call(?:sign)?|indicativo)\s*[:>]\s*$',prompt,re.I):
                            sock.sendall((call+'\r\n').encode('ascii'));logged=True;buffer='';text='';prompt=''
                            with self.lock:self.status='Ligado - a receber spots'
                        if logged and not requested and re.search(r'dxspider\s*>',prompt,re.I):
                            sock.sendall(b'sh/dx 30\r\n');requested=True
                            buffer='';text='';prompt=''
                        if re.search(r'password\s*:',prompt,re.I):
                            with self.lock:self.status='Este servidor requer palavra-passe. Escolha outro servidor.'
                            return
                        buffer+=text
                        while '\n' in buffer:
                            line,buffer=buffer.split('\n',1);self.parse(line)
                        buffer=buffer[-8192:]
            except OSError as error:
                if not stop.is_set():
                    with self.lock:self.status='Sem ligacao - nova tentativa em 15 s: '+str(error)
            finally:self.sock=None
            if stop.wait(15):break

cluster=DXCluster()
