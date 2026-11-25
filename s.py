import socket,time,ssl,subprocess
from concurrent.futures import ThreadPoolExecutor
ips=['20.97.252.251','20.205.187.223','20.125.42.21']
ports=[22,80,443,3389,5985,5986,8080,8443,9400,9100,8888,8000,5000,2375,2376,10250,10255,6443,3306,5432,6379,6006,7860,9090,9000,3000,8081,4243,8082,8880,7070]
def t(a):
    ip,p=a; s=socket.socket(); s.settimeout(3); t0=time.time()
    try:
        s.connect((ip,p)); 
        try:
            s.settimeout(2); s.send(b'HEAD / HTTP/1.0\r\n\r\n'); b=s.recv(200)
        except Exception: b=b''
        return (ip,p,'OPEN',round(time.time()-t0,2),b[:60])
    except Exception as e: return (ip,p,type(e).__name__,round(time.time()-t0,2),b'')
    finally: s.close()
jobs=[(ip,p) for ip in ips for p in ports]
with ThreadPoolExecutor(max_workers=48) as ex:
    for r in ex.map(t,jobs):
        if r[2]=='OPEN': print(*r, flush=True)
for ip in ips:
    try:
        ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
        with socket.create_connection((ip,443),timeout=5) as raw:
            with ctx.wrap_socket(raw,server_hostname=ip) as ss:
                c=ss.getpeercert(binary_form=False); print('CERT',ip,ss.version())
    except Exception as e: print('CERTERR',ip,type(e).__name__)
