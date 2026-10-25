"""One-time transfer of qualified, immutable 0.4.0 assets. No builds or index updates."""
import hashlib, http.client, json, os, tempfile, time, urllib.parse, urllib.request
from pathlib import Path
REPO='MicroKeen/Mklink-AI-Probe'
TAG='v0.4.0'
COMMIT='0c9c2d97d8f69e70f17c67659f5a644fd6379182'
HOST='mklink-downloads-shanghai-1300298079.cos.ap-shanghai.myqcloud.com'
EXPECTED=[{'name': 'Mklink-AI-Probe-v0.4.0-Skill.zip', 'size': 98788966, 'sha256': '555710fff446f80776b3fab418343d1370b6a083faa38f7d568896ac63c3d300'}, {'name': 'Mklink-AI-Probe-v0.4.0-x64-Setup.exe', 'size': 184436475, 'sha256': 'b02d3efc79038923cb7a5702dbfbd177b6b711817af38a5cff6eb7d0b08de003'}, {'name': 'Mklink-AI-Probe-v0.4.0-x64-Setup.exe.sig', 'size': 428, 'sha256': 'd011c43f2f1e764760bbd77e7f04abe5b8fbf7317e295da08656957732036924'}, {'name': 'MKLink-Site-Agent-v0.4.0-windows-x86_64-portable.manifest.json', 'size': 2391, 'sha256': 'efe710ec55191bd0965a0405e2d77a87d6704126cedf093bb8c08956dd88a642'}, {'name': 'MKLink-Site-Agent-v0.4.0-windows-x86_64-portable.zip', 'size': 67072686, 'sha256': '8e75d66e09e1cad878b40e607118a5693ca534679ff9b7ab0835599530ad31a2'}, {'name': 'release-manifest.json', 'size': 1275, 'sha256': '9bf286c8f99c4eeaa533f5bdcfde8f7bb03ab1d1a499d11a571e9e693be72040'}, {'name': 'SHA256SUMS.txt', 'size': 562, 'sha256': '8f729caa0f2f4247e29604b11ba12e7e423309e7b41d337f5ab8b6d413f65dfb'}]
TOKEN=os.environ['GH_TOKEN']
def api(path):
 req=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,headers={'Authorization':'Bearer '+TOKEN,'User-Agent':'MKLink-qualified-release-transfer','Accept':'application/vnd.github+json'})
 with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)
def main():
 assert os.environ.get('GITHUB_REPOSITORY')==REPO
 tag=api('git/ref/tags/'+TAG)['object']
 if tag['type']=='tag':tag=api('git/tags/'+tag['sha'])['object']
 assert tag['type']=='commit' and tag['sha']==COMMIT
 release=api('releases/tags/'+TAG)
 assert not release['draft'] and not release['prerelease']
 for item in EXPECTED:
  previous=next((a for a in release['assets'] if a['name']==item['name']),None)
  if previous:
   assert previous['size']==item['size'] and previous['digest']=='sha256:'+item['sha256']
   print('Already verified:',item['name'],flush=True);continue
  with tempfile.TemporaryDirectory() as scratch:
   asset=Path(scratch)/item['name']
   for attempt in range(3):
    try:
     with urllib.request.urlopen('https://'+HOST+'/mklink/guard/health.json?transfer='+str(time.time()),timeout=60) as r:health=json.load(r)
     assert health['open'] and health['reason']=='ready'
     url=health['urls']['/mklink/releases/'+TAG+'/'+item['name']]['GET']
     assert urllib.parse.urlsplit(url).scheme=='https' and urllib.parse.urlsplit(url).hostname==HOST
     sha=hashlib.sha256();size=0
     with urllib.request.urlopen(url,timeout=120) as r,asset.open('wb') as out:
      assert urllib.parse.urlsplit(r.url).hostname==HOST
      while block:=r.read(1024*1024):out.write(block);sha.update(block);size+=len(block)
     assert size==item['size'] and sha.hexdigest()==item['sha256']
     break
    except Exception:
     if attempt==2:raise RuntimeError('COS download/check failed: '+item['name']) from None
     time.sleep(3)
   url=urllib.parse.urlsplit(release['upload_url'].split('{')[0]+'?name='+urllib.parse.quote(item['name']))
   assert url.scheme=='https' and url.hostname=='uploads.github.com'
   conn=http.client.HTTPSConnection(url.hostname,timeout=180)
   conn.putrequest('POST',url.path+'?'+url.query)
   for k,v in {'Authorization':'Bearer '+TOKEN,'User-Agent':'MKLink-qualified-release-transfer','Content-Type':'application/octet-stream','Content-Length':str(item['size'])}.items():conn.putheader(k,v)
   conn.endheaders()
   with asset.open('rb') as src:
    while block:=src.read(1024*1024):conn.send(block)
   response=conn.getresponse();status=response.status;response.read();conn.close()
   assert status==201, 'GitHub upload HTTP '+str(status)
   release=api('releases/tags/'+TAG)
   uploaded=next(a for a in release['assets'] if a['name']==item['name'])
   assert uploaded['size']==item['size'] and uploaded['digest']=='sha256:'+item['sha256']
   print('Uploaded and remote SHA256 verified:',item['name'],flush=True)
 assert len(release['assets'])==len(EXPECTED)
 print('All seven qualified assets present; release tag and update indexes unchanged.',flush=True)
if __name__=='__main__':main()
