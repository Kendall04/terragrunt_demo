using System.Collections.Immutable;
using Sentinel.Application;
using Sentinel.Core;
using Sentinel.Operations;
using Sentinel.Persistence.Fakes;

internal static class CheckpointChecks {
    internal static void Run(OperationalProfile profile, Action<string,bool> check) {
        var now=DateTimeOffset.Parse("2026-11-05T21:00:00Z");
        check("installed profile remains 64 requests and four jobs",profile.MaxRequests==64&&profile.MaxJobs==4);
        var budget=new OperationalBudget(profile,()=>now);budget.ReserveCheckpoint(8);
        for(var i=0;i<56;i++)budget.BeforeIo();
        var rejected=false;try{budget.BeforeIo();}catch(OperationCanceledException){rejected=true;}
        check("work cannot spend the checkpoint reservation",rejected&&budget.Requests==56);
        budget.BeginCheckpoint();for(var i=0;i<8;i++)budget.BeforeIo();
        rejected=false;try{budget.BeforeIo();}catch(OperationCanceledException){rejected=true;}
        check("checkpoint cannot exceed the original hard cap",rejected&&budget.Requests==64);

        var scope=new OperationalScope("ecs-demo","dev","local-checkpoint","worker","portable");
        foreach(var failure in new[]{false,true}) {
            budget=new OperationalBudget(profile,()=>now);budget.ReserveCheckpoint(8);
            var backing=new OperationalMemoryStore(new());
            var initial=OperationalRecord.Empty(scope,profile,now) with {Revision=1,UnresolvedFailures=4,LastError="PermanentEffectFailure"};
            backing.CompareExchange(null,initial);
            var storage=new MeteredStore(backing,budget);var directory=new Directory(scope,budget,now);
            var journal=new OperationalJournal(storage,profile);
            var result=new OperationalWorker(journal,directory,(entry,_,_)=>{
                if(failure) { while(true)budget.BeforeIo(); }
                for(var i=0;i<33;i++)budget.BeforeIo();
                directory.Entries[entry.Id]=entry with{Status=OutboxStatus.Confirmed};
                return new(entry.Id,CompletionStatus.Recorded,"transport double");
            },profile,()=>now,budget).Tick(scope,failure?"interrupted":"completed",now);
            var persisted=backing.Read(scope)!;
            check("checkpoint releases lease without resetting profile or historical failures "+failure,
                persisted.Owner is null&&persisted.LeaseUntil is null&&persisted.UnresolvedFailures==4&&persisted.ProfileHash==initial.ProfileHash&&budget.Requests<=64);
            check("remaining work survives bounded yield "+failure,result.Outcome=="BudgetYield"&&persisted.BufferedWork.Length==(failure?2:1));
            check("progress requires a durable confirmed result "+failure,
                failure?persisted.LastProgressAt is null&&persisted.LastCompletedAt is null:persisted.LastProgressAt==now&&persisted.LastCompletedAt==now);
            check("historical STALLED is not hidden "+failure,HealthEvaluator.Evaluate(scope,persisted,profile,now).State==HealthState.STALLED);
        }
        // An ambiguous checkpoint can be reconciled, but never repeated blindly.
        budget=new OperationalBudget(profile,()=>now);budget.ReserveCheckpoint(8);
        var cheapMemory=new OperationalMemoryStore(new());var cheapDirectory=new Directory(scope,budget,now);
        var cheapJournal=new OperationalJournal(new MeteredStore(cheapMemory,budget),profile);
        var cheapResult=new OperationalWorker(cheapJournal,cheapDirectory,(entry,_,_)=>{
            for(var i=0;i<14;i++)budget.BeforeIo();
            cheapDirectory.Entries[entry.Id]=entry with{Status=OutboxStatus.Confirmed};
            return new(entry.Id,CompletionStatus.Recorded,"bounded dispatch double");
        },profile,()=>now,budget).Tick(scope,"two-dispatches",now);
        check("smaller independent dispatches share one unchanged budget",cheapResult.Confirmed==2&&cheapResult.Failures==0&&budget.Requests<=64&&cheapMemory.Read(scope)!.BufferedWork.IsEmpty);
        budget=new OperationalBudget(profile,()=>now);budget.ReserveCheckpoint(8);
        var memory=new OperationalMemoryStore(new());var metered=new MeteredStore(memory,budget);
        var j=new OperationalJournal(metered,profile);var lease=j.Start(scope,"cas",now,now,now)!;
        while(budget.Requests<56)budget.BeforeIo();budget.BeginCheckpoint();
        metered.Conflicts=2;metered.UnknownAfterCommit=true;
        check("reserved tail covers two CAS conflicts and uncertain write readback",
            j.Update(lease,now,s=>s with{LastCompletedAt=now},release:true)==OperationalWrite.Committed&&budget.Requests==63&&memory.Read(scope)!.Owner is null);
    }
    private sealed class MeteredStore(IOperationalStore inner,OperationalBudget budget):IOperationalStore {
        public int Conflicts;public bool UnknownAfterCommit;
        public OperationalRecord? Read(OperationalScope scope){budget.BeforeIo();return inner.Read(scope);}
        public OperationalWrite CompareExchange(OperationalRecord? old,OperationalRecord next) {
            budget.BeforeIo();if(Conflicts>0){Conflicts--;return OperationalWrite.Conflict;}
            var result=inner.CompareExchange(old,next);return UnknownAfterCommit&&result==OperationalWrite.Committed?OperationalWrite.Unknown:result;
        }
    }
    private sealed class Directory(OperationalScope scope,OperationalBudget budget,DateTimeOffset now):IOperationalWorkDirectory {
        public readonly Dictionary<string,OutboxEntry> Entries=Enumerable.Range(1,2).ToDictionary(i=>i.ToString(),i=>new OutboxEntry(2,i.ToString(),"aggregate",WorkKind.DomainEffect,
            new(i.ToString(),EffectKind.OpenIncident,"incident",1,new("policy"),null,null),"audit",false,false,1,OutboxStatus.Pending,now,0,0,null,null,null));
        public bool Owns(OperationalScope candidate)=>candidate==scope;
        public OperationalWorkPage Page(DateTimeOffset _,int maximum,string? cursor){budget.BeforeIo(true);return new(Entries.Values.Take(maximum).ToImmutableArray(),null);}
        public OutboxEntry? Read(string id){budget.BeforeIo();return Entries.GetValueOrDefault(id);}
    }
}
