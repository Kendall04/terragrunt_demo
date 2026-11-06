using System.Collections.Immutable;
using Amazon.DynamoDBv2;
using Amazon.DynamoDBv2.Model;
using Amazon.Runtime;
using Ecs.Backup.Portable.Host;
using Sentinel.Application;
using Sentinel.Core;
using Sentinel.Operations;
using Sentinel.Persistence.DynamoDb;
using Sentinel.Portable;

internal static class CurrentBacklogChecks {
 public static void Run(Installation c,Action<string,bool> check) {
  var now=DateTimeOffset.Parse("2026-11-06T06:00:00Z");
  var scope=new OperationalScope(c.Project,c.Environment,c.Consumer,"worker","portable");
  var row=new OutboxEntry(2,"id","aggregate",WorkKind.ArchiveDecision,null,"audit",false,false,1,OutboxStatus.Pending,now.AddMinutes(-1),0,0,null,null,null);
  var backlog=CurrentBacklog.Observe([row,row with{Id="future",DueAt=now.AddMinutes(1)},row with{Id="done",Status=OutboxStatus.Confirmed}],now,true);
  check("only actually due authoritative rows contribute",backlog.Due==1&&backlog.Archives==1&&backlog.Complete&&backlog.OldestDueAt==row.DueAt);
  var raw=OperationalRecord.Empty(scope,c.Operations,now) with{LastInvokedAt=now,LastCompletedAt=now,LastProgressAt=now,Backlog=backlog};
  var health=HealthEvaluator.Evaluate(scope,raw,c.Operations,now);
  check("current full observation can establish health",health.State==HealthState.HEALTHY_ACTIVE&&Function.HealthMetric(health)=="SentinelHealthMetric 1");
  foreach(var bad in new[]{backlog with{Complete=false},backlog with{Failed=1},backlog with{OldestArchiveAt=now-c.Operations.StalledAfter,OldestDueAt=now-c.Operations.StalledAfter}}) {
   var h=HealthEvaluator.Evaluate(scope,raw with{Backlog=bad},c.Operations,now);
   check("partial permanent or old work never emits healthy",Function.HealthMetric(h)=="SentinelHealthMetric 0");
  }
  var options=new DynamoOptions("table",c.Project,c.Environment,c.Consumer);var layout=new PhysicalLayout(options);
  using var client=new Reader(layout,row);var probe=new CurrentBacklog(client,options);var actual=probe.Read(now);
  check("bounded strongly consistent query and row read",probe.Requests==2&&client.Reads==1&&client.Queries==1&&actual==backlog);
  client.HasMore=true;check("continuation never treated as a complete sweep",!new CurrentBacklog(client,options).Read(now).Complete);
  check("watchdog view does not mutate historical journal",raw.Backlog==backlog&&raw.UnresolvedFailures==0);
 }
 sealed class Reader(PhysicalLayout layout,OutboxEntry row):AmazonDynamoDBClient(new AnonymousAWSCredentials(),new AmazonDynamoDBConfig{RegionEndpoint=Amazon.RegionEndpoint.USEast1}) {
  public bool HasMore;public int Reads,Queries;
  public override Task<QueryResponse> QueryAsync(QueryRequest r,CancellationToken t=default) {
   if(r.ConsistentRead!=true||r.Limit!=32||r.ExpressionAttributeValues[":w"].S!="W#")throw new Exception("Unbounded or eventually consistent read");Queries++;
   return Task.FromResult(new QueryResponse{Items=[layout.Item("W#pointer",row.Id)],LastEvaluatedKey=HasMore?layout.Key("W#pointer"):new()});
  }
  public override Task<GetItemResponse> GetItemAsync(GetItemRequest r,CancellationToken t=default) {
   if(r.ConsistentRead!=true||r.Key["SK"].S!=PhysicalLayout.Effect(row.Id))throw new Exception("Wrong authoritative row");Reads++;
   return Task.FromResult(new GetItemResponse{Item=layout.Item(PhysicalLayout.Effect(row.Id),row)});
  }
 }
}
