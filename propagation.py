# LOGBOOK - Copyright 2026 Eduardo Arraia, CT7ASY.
# Desenvolvido com assistencia de OpenAI Codex.
import json, math, re, time, threading
from datetime import date
from urllib.request import Request, build_opener, HTTPCookieProcessor
from http.cookiejar import CookieJar
from urllib.parse import urlencode
from urllib.error import URLError, HTTPError
import socket
_cache = {}
_lock = threading.Lock()
def center(value):
    s=str(value).upper()
    if not re.fullmatch(r'[A-R]{2}[0-9]{2}(?:[A-X]{2}(?:[0-9]{2}(?:[A-X]{2})?)?)?',s):raise ValueError('Locator invalido.')
    x=(ord(s[0])-65)*20-180;y=(ord(s[1])-65)*10-90;dx=20;dy=10
    for i in range(2,len(s),2):
        letters=i%4==0;base=24 if letters else 10;dx/=base;dy/=base
        x+=(ord(s[i])-65 if letters else int(s[i]))*dx
        y+=(ord(s[i+1])-65 if letters else int(s[i+1]))*dy
    return y+dy/2,x+dx/2

def predict(data):
    tx=center(data.get('tx',''));rx=center(data.get('rx',''))
    mode=str(data.get('mode','38'));path=str(data.get('path','0'));power=float(data.get('power',100))
    antennas={'d10m.ant','d20m.ant','v14.ant','3el20m.ant'}
    ta=data.get('txantenna','d10m.ant');ra=data.get('rxantenna','d10m.ant')
    if mode not in {'19','38','13','17','49'} or path not in {'0','1'} or not 1<=power<=1500 or ta not in antennas or ra not in antennas:raise ValueError('Configuracao de propagacao invalida.')
    a,b=map(math.radians,tx);c,d=map(math.radians,rx);dl=d-b
    dist=6371*math.acos(max(-1,min(1,math.sin(a)*math.sin(c)+math.cos(a)*math.cos(c)*math.cos(dl))))
    bearing=math.degrees(math.atan2(math.sin(dl)*math.cos(c),math.cos(a)*math.sin(c)-math.sin(a)*math.cos(c)*math.cos(dl)))%360
    bx=math.cos(c)*math.cos(dl);by=math.cos(c)*math.sin(dl)
    midlat=math.degrees(math.atan2(math.sin(a)+math.sin(c),math.hypot(math.cos(a)+bx,by)))
    midlon=math.degrees(b+math.atan2(by,math.cos(a)+bx))
    params=dict(date=date.today().isoformat(),txname=data['tx'],rxname=data['rx'],txlat=tx[0],txlon=tx[1],rxlat=rx[0],rxlon=rx[1],txpower=power*.0008,txmode=mode,method='30',mintoa='3.00',noise='150',path=path,ssn='-1',es='0',deg=bearing,km=dist,lpmplat=-midlat,lpmplon=(midlon+360)%360-180)
    for i in range(1,10):
        suffix='' if i==1 else str(i);params['txantenna'+suffix]=ta;params['rxantenna'+suffix]=ra
    key=urlencode(params)
    cached = _cache.get(key)
    if cached and time.time()-cached[0]<1800:return cached[1]
    with _lock:
        if key in _cache and time.time()-_cache[key][0]<1800:return _cache[key][1]
        opener=build_opener(HTTPCookieProcessor(CookieJar()))
        try:
            with opener.open('https://www.voacap.com/hf/',timeout=15) as landing: landing.read()
            req=Request('https://www.voacap.com/hf/wheel2.php',data=key.encode(),headers={'Content-Type':'application/x-www-form-urlencoded','User-Agent':'Logbook/1.0','Referer':'https://www.voacap.com/hf/'})
            with opener.open(req,timeout=60) as response:table=json.loads(response.read(200000))
        except HTTPError as e:
            raise ValueError(f'O VOACAP recusou a consulta (HTTP {e.code}). Tente mais tarde.') from e
        except (TimeoutError, socket.timeout) as e:
            raise ValueError('O VOACAP não respondeu a tempo.') from e
        except URLError as e:
            raise ValueError('Não foi possível ligar ao VOACAP. Verifique o acesso a www.voacap.com/hf/ e tente novamente.') from e
        except (ValueError, TypeError) as e:
            raise ValueError('O VOACAP devolveu uma resposta inválida. Tente novamente mais tarde.') from e
        if isinstance(table,dict) and '24' in table and '0' not in table:table['0']=table.pop('24')
        bands=['3','5','7','10','14','18','21','24','28']
        if not isinstance(table,dict) or any(str(h) not in table for h in range(24)):raise ValueError('Resposta VOACAP incompleta.')
        for h in range(24):
            for band in bands:
                v=float(table[str(h)][band])
                if not math.isfinite(v) or not 0<=v<=1:raise ValueError('Resposta VOACAP invalida.')
                table[str(h)][band]=v
        result={'table':table,'date':params['date'],'source':'VOACAP Online'}
        if len(_cache)>30:_cache.clear()
        _cache[key]=(time.time(),result)
        return result
