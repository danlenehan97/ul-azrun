import json,os,urllib.request,urllib.parse
tid=os.environ.get('AZURE_TENANT_ID'); cid=os.environ.get('AZURE_CLIENT_ID'); ft=os.environ.get('AZURE_FEDERATED_TOKEN_FILE')
print('ENV',tid,cid,ft,flush=True)
a=open(ft).read().strip()
d=urllib.parse.urlencode({'client_id':cid,'client_assertion_type':'urn:ietf:params:oauth:client-assertion-type:jwt-bearer','client_assertion':a,'scope':'https://management.azure.com/.default','grant_type':'client_credentials'}).encode()
try:
    r=urllib.request.urlopen(urllib.request.Request('https://login.microsoftonline.com/%s/oauth2/v2.0/token'%tid,data=d),timeout=30)
    j=json.loads(r.read()); tok=j['access_token']; print('ARMTOKEN',tok[:50],len(tok))
except Exception as e:
    print('AUTHERR',e); raise SystemExit
def g(u):
    try:
        x=urllib.request.urlopen(urllib.request.Request(u,headers={'Authorization':'Bearer '+tok}),timeout=60)
        return json.loads(x.read())
    except Exception as e:
        try: return {'err':str(e),'body':e.read()[:300].decode()}
        except Exception: return {'err':str(e)}
subs=g('https://management.azure.com/subscriptions?api-version=2022-12-01')
ids=[s['subscriptionId'] for s in subs.get('value',[])] if isinstance(subs,dict) else []
print('SUBS',ids)
for s in ids:
    v=g('https://management.azure.com/subscriptions/%s/providers/Microsoft.Compute/virtualMachines?api-version=2024-07-01'%s)
    print('VMS',s,json.dumps([(x.get('name'),x.get('location'),(x.get('properties',{}) or {}).get('hardwareProfile',{}).get('vmSize')) for x in (v.get('value',[]) if isinstance(v,dict) else [])])[:1500])
    p=g('https://management.azure.com/subscriptions/%s/providers/Microsoft.Network/publicIPAddresses?api-version=2024-05-01'%s)
    print('PIPS',s,json.dumps([(x.get('name'),(x.get('properties',{}) or {}).get('ipAddress')) for x in (p.get('value',[]) if isinstance(p,dict) else [])])[:2000])
