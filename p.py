import socket, time, ssl, subprocess
from concurrent.futures import ThreadPoolExecutor
T='20.74.153.201'
PEERS=['20.125.42.21','20.97.252.251','20.205.187.223','20.50.113.151','40.123.206.138','51.104.16.184','20.74.241.13','20.216.40.163','74.162.158.9','20.74.242.85']
PORTS=[22,80,443,3000,3389,8000,8080,8888,9000,9100,9400,10250,2375,6443,5000,7860,8081,1111,11434,8265,5985,8880]
def conn(ip,port,to=4):
    s=socket.socket(); s.settimeout(to); t0=time.time()
    try:
        s.connect((ip,port)); dt=round(time.time()-t0,2); bt=b''
        try:
            s.settimeout(2); s.send(b'GET / HTTP/1.0\r\nHost: %s\r\n\r\n'%ip.encode()); bt=s.recv(300)
        except Exception as e: bt=b'ERR:'+type(e).__name__.encode()
        return (ip,port,'OPEN',dt,bt[:120])
    except Exception as e: return (ip,port,type(e).__name__,round(time.time()-t0,2),b'')
    finally: s.close()
jobs=[(T,p) for p in PORTS]+[(ip,443) for ip in PEERS]+[(ip,22) for ip in PEERS]+[(ip,3389) for ip in PEERS]
with ThreadPoolExecutor(max_workers=48) as ex:
    for r in sorted(ex.map(lambda a: conn(*a), jobs), key=lambda x:(x[0],x[1])):
        if r[2]=='OPEN' or r[0]==T: print('TCP',r[0],r[1],r[2],r[3],repr(r[4])[:160],flush=True)
print('=== HTTP routes ===',flush=True)
PATHS=['/','/brand','/index.html','/health','/healthz','/status','/api','/api/status','/api/v1','/v1','/v1/models','/api/models','/models','/docs','/api-docs','/swagger','/openapi.json','/graphql','/metrics','/debug','/env','/admin','/login','/api/jobs','/api/predict','/api/upload','/robots.txt','/favicon.ico','/.env','/config.json']
for p in PATHS:
    for scheme,port in (('http',80),('https',443),('http',3000),('http',8080),('http',8000)):
        r=subprocess.run(['curl','-sk','-m','8','-o','/tmp/b.out','-w','%{http_code} %{size_download} %{content_type}','-D','/tmp/h.out',f'{scheme}://{T}:{port}{p}'],capture_output=True,text=True,timeout=12)
        out=r.stdout.strip()
        if out and not out.startswith('000 0'):
            try: body=open('/tmp/b.out','rb').read(200)
            except Exception: body=b''
            try: hd=open('/tmp/h.out',errors='replace').read()[:400].replace('\n','|')
            except Exception: hd=''
            print(f'HTTP {scheme}:{port}{p} => {out} :: {hd} :: {body!r}',flush=True)
try:
    ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    with socket.create_connection((T,443),timeout=6) as raw:
        with ctx.wrap_socket(raw,server_hostname=T) as ss:
            print('TLS',ss.version(),ss.getpeercert(binary_form=False),flush=True)
except Exception as e: print('TLSERR',type(e).__name__,str(e)[:200],flush=True)
print('=== PEER 443 HTTP ===',flush=True)
for ip in ['20.125.42.21','20.97.252.251']:
    for p in ['/','/brand','/health','/api','/api/status','/v1/models','/metrics','/openapi.json','/favicon.ico','/.env']:
        r=subprocess.run(['curl','-sk','-m','8','-o','/tmp/b2.out','-w','%{http_code} %{size_download}','-D','/tmp/h2.out',f'https://{ip}{p}'],capture_output=True,text=True,timeout=12)
        out=r.stdout.strip()
        if out and not out.startswith('000 0') and not out.startswith('404'):
            try: body=open('/tmp/b2.out','rb').read(200)
            except Exception: body=b''
            print(f'PEER {ip}{p} => {out} :: {body!r}',flush=True)
print('=== done ===',flush=True)
