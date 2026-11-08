"""NuGet canonical content hash and certificate verification; raw archive SHA is separate."""
import argparse,base64,hashlib,json,re,subprocess
from pathlib import Path
def verify(package,dotnet,expected):
 result=subprocess.run([str(dotnet),'nuget','verify','--all',str(package)],capture_output=True,text=True)
 content=re.search(r'Content hash: ([A-Za-z0-9+/=]+)',result.stdout)
 if result.returncode or not content or content[1]!=expected or 'Signature type: Repository' not in result.stdout:raise ValueError('SIGNED_PACKAGE_OR_LOCK_HASH_NOT_VERIFIED')
 return {'nugetContentHash':content[1],'rawArchiveSha256':hashlib.sha256(package.read_bytes()).hexdigest(),'rawArchiveSha512':base64.b64encode(hashlib.sha512(package.read_bytes()).digest()).decode(),'signatureVerified':True,'lockHashMatched':True}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,required=True);p.add_argument('--dotnet',type=Path,required=True);p.add_argument('--expected-content-hash',required=True);a=p.parse_args();print(json.dumps(verify(a.package,a.dotnet,a.expected_content_hash)))
