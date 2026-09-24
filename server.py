"""Prototype gateway. One process owns short-lived, isolated DX sessions."""
import json, os, secrets, threading, time, re
from collections import defaultdict, deque
from flask import Flask, request, jsonify
from dxcluster import DXCluster
from propagation import predict

app=Flask(__name__)
app.config['MAX_CONTENT_LENGTH']=8192
ORIGINS=set(os.environ.get('ALLOWED_ORIGINS','https://ct1eew.github.io').split(','))
SERVERS={
 'portal':{'name':'Portal do Radioamador','host':'portaldoradioamador.pt','port':7300},
 'ea2cw':{'name':'EA2CW · Espanha','host':'cluster.gautxori.com','port':7300},
 'g1fef':{'name':'G1FEF · Reino Unido','host':'dxc.hamserve.uk','port':7300},
 'oe':{'name':'OE · Áustria','host':'dxcluster.oevsv.at','port':7300},
}
sessions={}; lock=threading.RLock(); rates=defaultdict(deque); prediction_slot=threading.BoundedSemaphore(1)

@app.before_request
def guard():
 if request.path=='/health':return
 if request.headers.get('Origin') not in ORIGINS:return jsonify(error='Origem não autorizada.'),403
 if request.method=='OPTIONS':return '',204
 # Bound work even when a caller spoofs Origin. No arbitrary destinations accepted.
 key=request.remote_addr; now=time.monotonic()
 with lock:
  q=rates[key]
  while q and now-q[0]>60:q.popleft()
  if len(q)>=90:return jsonify(error='Demasiados pedidos. Aguarde um minuto.'),429
  q.append(now)

@app.after_request
def headers(response):
 if request.headers.get('Origin') in ORIGINS:
  response.headers['Access-Control-Allow-Origin']=request.headers['Origin']
  response.headers['Vary']='Origin'
  response.headers['Access-Control-Allow-Headers']='Content-Type, Authorization'
  response.headers['Access-Control-Allow-Methods']='GET, POST, OPTIONS'
 response.headers['Cache-Control']='no-store'
 return response

@app.errorhandler(ValueError)
def bad_value(error):return jsonify(error=str(error)),400

@app.get('/health')
def health():return jsonify(status='ok',version='0.1.1')

@app.get('/servers')
def servers():return jsonify(servers=[{'id':k,'name':v['name']} for k,v in SERVERS.items()])

@app.post('/propagation')
def propagation():
 data=request.get_json()
 if not isinstance(data,dict):raise ValueError('Pedido inválido.')
 if not prediction_slot.acquire(blocking=False):return jsonify(error='Já existe uma previsão em cálculo. Tente novamente dentro de alguns segundos.'),429
 try:return jsonify(predict(data))
 finally:prediction_slot.release()

@app.post('/dx/connect')
def connect():
 data=request.get_json()
 if not isinstance(data,dict):raise ValueError('Pedido inválido.')
 server=SERVERS.get(data.get('server'));call=str(data.get('call','')).strip().upper()
 if not server or not re.fullmatch(r'[A-Z0-9/]{3,20}(?:-[0-9]{1,2})?',call):raise ValueError('Escolha um servidor e indique um indicativo válido.')
 with lock:
  if len(sessions)>=20:return jsonify(error='Serviço ocupado. Tente mais tarde.'),503
  if sum(s['ip']==request.remote_addr for s in sessions.values())>=3:return jsonify(error='Já existem três ligações neste endereço. Desligue uma ou aguarde um minuto.'),429
  token=secrets.token_urlsafe(32);cluster=DXCluster()
  cluster.connect({**server,'call':call})
  sessions[token]={'cluster':cluster,'used':time.monotonic(),'ip':request.remote_addr}
 return jsonify(token=token)

def session():
 token=request.headers.get('Authorization','').removeprefix('Bearer ')
 with lock:
  item=sessions.get(token)
  if item:item['used']=time.monotonic()
 return token,item

@app.get('/dx/status')
def status():
 _,item=session()
 if not item:return jsonify(error='A ligação expirou. Volte a ligar.'),410
 return jsonify(item['cluster'].snapshot())

@app.post('/dx/disconnect')
def disconnect():
 token=request.headers.get('Authorization','').removeprefix('Bearer ')
 if not token and request.mimetype=='text/plain':token=request.get_data(as_text=True).strip()
 if not re.fullmatch(r'[A-Za-z0-9_-]{32,64}',token):return jsonify(error='Sessão inválida.'),400
 with lock:item=sessions.pop(token,None)
 if item:item['cluster'].disconnect()
 return jsonify(status='Desligado')

def reap():
 while True:
  time.sleep(5);now=time.monotonic()
  with lock:
   expired=[sessions.pop(k) for k,v in list(sessions.items()) if now-v['used']>45]
   for ip in list(rates):
    if not rates[ip] or now-rates[ip][-1]>60:del rates[ip]
  for item in expired:item['cluster'].disconnect()
threading.Thread(target=reap,daemon=True).start()

if __name__=='__main__':app.run(host='127.0.0.1',port=8770,threaded=True)
