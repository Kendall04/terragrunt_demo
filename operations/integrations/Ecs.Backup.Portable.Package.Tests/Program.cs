using System.Diagnostics;
using System.IO.Compression;
using System.Reflection;
using System.Runtime.Loader;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
static class Program {
 static int checks;
 static void Check(bool ok,string label) { if(!ok)throw new Exception(label);checks++;Console.WriteLine("PASS "+label); }
 static string Sha(byte[] b)=>Convert.ToHexStringLower(SHA256.HashData(b));
 static int Main(string[] a) {
  try { if(a.Length==2 && a[0]=="--child")Child(a[1]);else Parent(a);Console.WriteLine(JsonSerializer.Serialize(new{checks,awsCalls=0,execution="WINDOWS_CLR_PACKAGE_LOAD_NOT_AWS_OR_LINUX"}));return 0; }
  catch(Exception e) {Console.Error.WriteLine(e);return 1;}
 }
 static void Parent(string[] a) {
  if(a.Length!=2)throw new ArgumentException("archive and descriptor required");
  var archive=Path.GetFullPath(a[0]);using var descriptor=JsonDocument.Parse(File.ReadAllBytes(a[1]));var d=descriptor.RootElement;
  var original=File.ReadAllBytes(archive);Check(Sha(original)==d.GetProperty("zipSha256").GetString(),"outer ZIP hash");
  Check(d.GetProperty("executionAuthorized").GetBoolean()==false && !d.GetProperty("includedSqlHostPublisher").GetBoolean(),"no execution authority or host publisher claim");
  var root=Path.Combine(Path.GetTempPath(),"ecs-portable-package-"+Guid.NewGuid().ToString("N"));Directory.CreateDirectory(root);
  try {
   using(var zip=ZipFile.OpenRead(archive)) {
    var names=new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    foreach(var e in zip.Entries) {
     Check(e.Name==e.FullName && e.Name.Length>0 && !Path.IsPathRooted(e.FullName) && !e.Name.Contains(':') && names.Add(e.Name) && ((e.ExternalAttributes>>16)&0xf000)!=0xa000,"safe unique flat entry "+e.Name);
     Check(e.Name.EndsWith(".dll",StringComparison.Ordinal) || e.Name.EndsWith(".json",StringComparison.Ordinal),"assembly/config only "+e.Name);
     e.ExtractToFile(Path.Combine(root,e.Name));
    }
    using var manifest=JsonDocument.Parse(File.ReadAllBytes(Path.Combine(root,"ecs-package-manifest.json")));var m=manifest.RootElement;
    Check(names.Count==d.GetProperty("payloadFiles").GetInt32() && names.Count==m.GetProperty("files").EnumerateObject().Count()+1,"exact payload inventory");
    foreach(var f in m.GetProperty("files").EnumerateObject())Check(names.Contains(f.Name) && Sha(File.ReadAllBytes(Path.Combine(root,f.Name)))==f.Value.GetProperty("sha256").GetString(),"payload hash "+f.Name);
    Check(m.GetProperty("sourceCommit").GetString()==d.GetProperty("sourceCommit").GetString() && m.GetProperty("upstreamCommit").GetString()=="b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828","source lineage");
    Check(Sha(File.ReadAllBytes(Path.Combine(root,"sentinel.json")))==d.GetProperty("configSha256").GetString(),"same IaC/package config bytes");
    Check(m.GetProperty("publisherContract").GetProperty("entryAttempts").GetInt32()==20 && m.GetProperty("publisherContract").GetProperty("perPendingEntryAttempts").GetInt32()==3 && m.GetProperty("publisherContract").GetProperty("copyOnlyPolicy").GetString()=="FULL_COPY_ONLY_CHECKSUM","20 entries / three tries / COPY_ONLY contract");
   }
   var self=Assembly.GetExecutingAssembly().Location;var stem=Path.GetFileNameWithoutExtension(self);
   foreach(var ext in new[]{".dll",".deps.json",".runtimeconfig.json"})File.Copy(Path.ChangeExtension(self,null)+ext,Path.Combine(root,stem+ext));
   var si=new ProcessStartInfo(Environment.GetEnvironmentVariable("DOTNET_HOST_PATH")??"dotnet") {UseShellExecute=false,RedirectStandardOutput=true,RedirectStandardError=true,WorkingDirectory=root};
   si.ArgumentList.Add(Path.Combine(root,stem+".dll"));si.ArgumentList.Add("--child");si.ArgumentList.Add(root);
   using var process=Process.Start(si)??throw new Exception("child start");var stdout=process.StandardOutput.ReadToEnd();var stderr=process.StandardError.ReadToEnd();process.WaitForExit();Console.Write(stdout);Console.Error.Write(stderr);Check(process.ExitCode==0,"isolated package factory/serializer child");
  } finally {
   Check(Path.GetFullPath(root).StartsWith(Path.GetFullPath(Path.GetTempPath()).TrimEnd(Path.DirectorySeparatorChar)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase) && Path.GetFileName(root).StartsWith("ecs-portable-package-",StringComparison.Ordinal),"owned temporary cleanup path");
   Directory.Delete(root,true);
  }
  Check(Sha(File.ReadAllBytes(archive))==Sha(original),"original immutable ZIP unchanged");
 }
 static void Child(string root) {
  Check(Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar)==AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar),"factory loads from extracted package root");
  AssemblyLoadContext.Default.Resolving+=(_,n)=> {var p=Path.Combine(root,n.Name+".dll");return File.Exists(p)?AssemblyLoadContext.Default.LoadFromAssemblyPath(p):null;};
  var assembly=AssemblyLoadContext.Default.LoadFromAssemblyPath(Path.Combine(root,"Ecs.Backup.Portable.Host.dll"));
  var function=assembly.GetType("Ecs.Backup.Portable.Host.Function",true)!;
  var factory=Activator.CreateInstance(function)!;Check(factory is not null,"actual default factory constructs without AWS invocation");
  var installation=function.GetMethod("ValidateBundle")!.Invoke(null,[root])!;var profile=installation.GetType().GetProperty("Operations")!.GetValue(installation)!;
  Check((int)profile.GetType().GetProperty("MaxAttempts")!.GetValue(profile)! == 3,"packaged durable notice attempts capped at three");
  var dispatch=profile.GetType().GetMethod("Dispatch")!.Invoke(profile,[1,"package-proof"])!;
  Check(!(bool)dispatch.GetType().GetProperty("RetryCriticalBeyondLimit")!.GetValue(dispatch)!,"critical notices cannot exceed attempt limit");

  var inner=function.GetField("inner",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(factory)!;
  Check(inner.GetType().GetField("snsFormat",BindingFlags.Instance|BindingFlags.NonPublic)!.GetValue(inner) is Delegate,"real readable SNS formatter injected");
  var attribute=assembly.GetCustomAttributesData().Single(x=>x.AttributeType.FullName=="Amazon.Lambda.Core.LambdaSerializerAttribute");
  var serializerType=(Type)attribute.ConstructorArguments.Single().Value!;var serializer=Activator.CreateInstance(serializerType)!;
  Check(serializerType.FullName=="Amazon.Lambda.Serialization.SystemTextJson.DefaultLambdaJsonSerializer","declared Lambda serializer loads");
  foreach(var (name,mode) in new[]{("Tick","tick"),("Ingest",""),("Watchdog","watchdog"),("Cleanup","cleanup")}) {
   var method=function.GetMethod(name)!;var parameters=method.GetParameters();Check(parameters.Length==2 && parameters[1].ParameterType.FullName=="Amazon.Lambda.Core.ILambdaContext","handler signature "+name);
   var raw=name=="Ingest"?"{\"Records\":[]}":"{\"Deployment\":\"ecs-portable-r20261026p1\",\"Mode\":\""+mode+"\"}";
   using var input=new MemoryStream(Encoding.UTF8.GetBytes(raw));
   var value=serializerType.GetMethods().Single(x=>x.Name=="Deserialize" && x.IsGenericMethodDefinition).MakeGenericMethod(parameters[0].ParameterType).Invoke(serializer,[input]);
   Check(value is not null,"serializer request "+name);using var output=new MemoryStream();
   serializerType.GetMethods().Single(x=>x.Name=="Serialize" && x.IsGenericMethodDefinition).MakeGenericMethod(parameters[0].ParameterType).Invoke(serializer,[value,output]);
   Check(output.Length>0,"serializer roundtrip "+name);
  }
  var path=Path.Combine(root,"sentinel.json");var saved=File.ReadAllBytes(path);File.AppendAllText(path," ");
  bool rejected=false;try{Activator.CreateInstance(function);}catch(TargetInvocationException e) when(e.InnerException is InvalidOperationException){rejected=true;}finally{File.WriteAllBytes(path,saved);}
  Check(rejected,"factory refuses altered config before transport");Check(Activator.CreateInstance(function) is not null,"restored exact fixture accepted");
 }
}
