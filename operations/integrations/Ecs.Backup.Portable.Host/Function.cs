using System.Security.Cryptography;
using System.Text.Json;
using Amazon.Lambda.Core;
using Amazon.Lambda.SQSEvents;
using Sentinel.Portable;
using Sentinel.Operations;
using Sentinel.Portable.Lambda;
[assembly: LambdaSerializer(typeof(Amazon.Lambda.Serialization.SystemTextJson.DefaultLambdaJsonSerializer))]
namespace Ecs.Backup.Portable.Host;
public sealed class Function {
 private readonly Sentinel.Portable.Lambda.Function inner;
 public Function() {
  var config=ValidateBundle(AppContext.BaseDirectory);
  inner=new(n=>ReadableNotice.Render(n,config,true)); // This trial bundle is explicitly synthetic; no caller override.
 }
 public static Installation ValidateBundle(string root) {
  var raw=File.ReadAllBytes(Path.Combine(root,"sentinel.json"));
  using var doc=JsonDocument.Parse(File.ReadAllBytes(Path.Combine(root,"ecs-portable.json")));var p=doc.RootElement;
  if(p.EnumerateObject().Count()!=4 || p.GetProperty("schemaVersion").GetInt32()!=1 || p.GetProperty("upstreamCommit").GetString()!="b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828" || !p.GetProperty("syntheticTrial").GetBoolean() ||
   p.GetProperty("configSha256").GetString()!=Convert.ToHexStringLower(SHA256.HashData(raw)))throw new InvalidOperationException("Exact synthetic bundle metadata required.");
  var config=StrictJson.Installation(System.Text.Encoding.UTF8.GetString(raw));
  if(config.Account!="341936017254" || config.Region!="us-east-1" || config.Monitors.Length!=2 || config.Monitors.Count(m=>m.Kind=="sql-backup" && m.Selector=="full" && m.RequiredAssurance==Sentinel.Core.Assurance.Artifact)!=1 || config.Monitors.Count(m=>m.Kind=="report" && m.RequiredAssurance==Sentinel.Core.Assurance.Reported)!=1 || config.Monitors.Any(m=>m.Model!=Sentinel.Core.MonitorModel.Freshness || !m.Sources.SequenceEqual(new[]{"sql-observer"})) || config.WebhookEnvironment is not null)throw new InvalidOperationException("Backup-only trial profile required.");
  return config;
 }
 public TickSummary Tick(TickEvent request,ILambdaContext context)=>inner.Tick(request,context);
 public Task<SQSBatchResponse> Ingest(SQSEvent request,ILambdaContext context)=>inner.Ingest(request,context);
 public HealthAssessment Watchdog(TickEvent request,ILambdaContext context)=>inner.Watchdog(request,context);
 public int Cleanup(TickEvent request,ILambdaContext context)=>inner.Cleanup(request,context);
}
