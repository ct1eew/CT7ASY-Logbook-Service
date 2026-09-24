"""QRZ HTTPS requests. No credential persistence or payload logging."""
import urllib.request, urllib.parse, xml.etree.ElementTree as ET

def query(action,data):
 if not isinstance(data,dict):raise ValueError('Pedido inválido.')
 if action=='login':
  params={k:data.get(k,'') for k in ('username','password')}
 else:params={'s':data.get('key',''),'callsign':data.get('call','')}
 if any(not isinstance(v,str) or not v or len(v)>512 for v in params.values()):raise ValueError('Preenche os campos QRZ.')
 params['agent']='CT7ASY-Web-0.1.17'
 req=urllib.request.Request('https://xmldata.qrz.com/xml/current/',data=urllib.parse.urlencode(params).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
 with urllib.request.urlopen(req,timeout=18) as response:raw=response.read(262145)
 if len(raw)>262144:raise ValueError('Resposta QRZ demasiado grande.')
 root=ET.fromstring(raw)
 for element in root.iter():element.tag=element.tag.rsplit('}',1)[-1]
 error=root.findtext('Session/Error')
 if error:raise ValueError(error)
 key=root.findtext('Session/Key','')
 if not key:raise ValueError('Sessão QRZ expirada. Volta a ligar nos Perfis.')
 result={'key':key}
 if action=='lookup':
  call=root.find('Callsign')
  if call is None:raise ValueError('Indicativo não encontrado no QRZ.')
  result.update(name=' '.join(filter(None,[call.findtext('fname'),call.findtext('name')])),qth=call.findtext('addr2',''),country=call.findtext('country',''),grid=call.findtext('grid',''))
 if root.findtext('Session/SubExp')=='non-subscriber':result['message']='Conta QRZ sem subscrição XML: dados limitados.'
 return result
