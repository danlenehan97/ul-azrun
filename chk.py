import socket,time,sys
from concurrent.futures import ThreadPoolExecutor
ips=[l.strip() for l in open('ips.txt') if l.strip()]
def t(ip,port):
    s=socket.socket(); s.settimeout(4); t0=time.time()
    try:
        s.connect((ip,port)); return (ip,port,'OPEN',round(time.time()-t0,2))
    except Exception as e:
        return (ip,port,type(e).__name__,round(time.time()-t0,2))
    finally: s.close()
jobs=[(ip,p) for ip in ips for p in (22,2222,443,3389)]
with ThreadPoolExecutor(max_workers=64) as ex:
    for r in ex.map(lambda a:t(*a), jobs): print(*r, flush=True)
