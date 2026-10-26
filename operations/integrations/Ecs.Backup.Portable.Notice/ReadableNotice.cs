using Sentinel.Core;
using Sentinel.Portable;
using Sentinel.Portable.Aws;
namespace Ecs.Backup.Portable;
public static class ReadableNotice {
 public static (string Subject,string Message) Render(IncidentNotice notice,Installation config,bool syntheticTrial) {
  var monitor=config.Monitors.SingleOrDefault(m=>m.Id==notice.Monitor);
  if(notice.SchemaVersion!=2 || notice.Deployment!=config.Deployment || notice.Consumer!=config.Consumer || monitor is null ||
   notice.Resource!=monitor.Resource || notice.Generation!=monitor.Generation || notice.RequiredAssurance!=monitor.RequiredAssurance ||
   notice.Revision<1 || notice.Epoch<1 || notice.EvaluatedAt.Offset!=TimeSpan.Zero ||
   notice.ConfirmedServiceImpact!=(notice.Condition==NoticeCondition.ConfirmedImpact) ||
   notice.Event is not ("EscalateIncident" or "ResolveIncident") ||
   (notice.Event=="ResolveIncident")!=(notice.Condition==NoticeCondition.ExpectationSatisfied))
    throw new ArgumentException("Notice scope/condition/version mismatch; no formatting or delivery.");
  string Safe(string? value,int max=512){value??="(sin dato)";if(value.Length>max || value.Any(c=>char.IsControl(c)))throw new ArgumentException("Unsafe notice field.");return value;}
  var state=notice.Condition switch {
   NoticeCondition.HealthUnverifiable=>"SALUD NO VERIFICABLE",
   NoticeCondition.ObservedFailure=>"FALLO OBSERVADO",
   NoticeCondition.ExpectationUnmet=>"EXPECTATIVA INCUMPLIDA",
   NoticeCondition.ConfirmedImpact=>"IMPACTO CONFIRMADO",
   NoticeCondition.ExpectationSatisfied=>"RECUPERACIÓN VERIFICADA PARA ESTA EXPECTATIVA",
   _=>throw new ArgumentException("Unknown notice condition.")};
  var mark=syntheticTrial?"PRUEBA SINTÉTICA | ":"";
  var message=$"{mark}ECS · Observabilidad de backups\n\nEstado: {state}\nMonitor: {Safe(notice.Monitor)}\nRecurso: {Safe(notice.Resource)}\nMotivo: {Safe(notice.Summary)}\nGarantía exigida: {notice.RequiredAssurance}\nEvaluación UTC: {notice.EvaluatedAt:O}\nRevisión: {notice.Revision}\n";
  foreach(var reason in notice.Reasons.Take(8))message+=$"- {Safe(reason)}\n";
  message+=$"\nAlcance: {Safe(notice.Deployment)} / {Safe(notice.Consumer)}\nResponsable: {Safe(notice.Owner)}\n";
  message+="No implica una restauración SQL ni salud de la aplicación salvo evidencia explícita del contrato.\nAceptar el aviso en SNS no acredita recepción en inbox. SNS puede duplicar o reordenar avisos.\n";
  message+=$"\nDatos técnicos\nSchemaVersion: 2\nEvent: {Safe(notice.Event)}\nCondition: {notice.Condition}\nAssessment: {Safe(notice.Assessment)}\nState: {Safe(notice.State)}\nConfirmedServiceImpact: {notice.ConfirmedServiceImpact}\nCritical: {notice.Critical}\nGeneration: {Safe(notice.Generation)}\nIncidentId: {Safe(notice.IncidentId,128)}\nEpoch: {notice.Epoch}\nDeliveryId: {Safe(notice.DeliveryId,128)}\nAuditId: {Safe(notice.AuditId,128)}\nAcceptance: SNS_PUBLISH_ONLY_NOT_INBOX_RECEIPT\n";
  var subject=mark+"ECS: "+(notice.Event=="ResolveIncident"?"expectativa recuperada":"revisar "+Safe(notice.Monitor));
  if(message.Length>8192)throw new ArgumentException("Notice too large.");return(subject,message);
 }
}
