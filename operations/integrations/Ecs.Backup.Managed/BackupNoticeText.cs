using System.Globalization;
using System.Text;

namespace Ecs.Backup.Managed;

// The same sanitized evidence stays structured in the SDK request and is
// reconstructable from the original durable audit/outbox; email is plain text.
public sealed record BackupNoticeEvidence(int SchemaVersion,string Source,string SenderLabel,string Service,string Scope,
 string IncidentId,long Epoch,string EffectId,string Kind,string BackupStatus,string Acceptance,bool SyntheticTrial);

public static class BackupNoticeText {
 public static (string Subject,string Message) Format(BackupNoticeEvidence evidence,string? code,DateTimeOffset observed,bool allowObserverCheck=false) {
  if((!evidence.SyntheticTrial && !allowObserverCheck) || (evidence.SyntheticTrial && allowObserverCheck) || evidence.SchemaVersion!=1 || evidence.Source!="Ecs.Backup.Sentinel")
   throw new ArgumentException("Explicit matching backup observation mode required.");
  var state=evidence.BackupStatus switch {
   "FAILED"=>"FALLO (FAILED)","MISSING"=>"AUSENTE (MISSING)","STALE"=>"ANTIGUO (STALE)",
   "UNKNOWN"=>"SIN DATOS SUFICIENTES (UNKNOWN)","HEALTHY"=>"SANO (HEALTHY)",
   _=>throw new ArgumentException("Unsupported backup status.")};
  var reason=(evidence.BackupStatus,code) switch {
   ("FAILED","LAST_ATTEMPT_FAILED")=>"El observador informó un intento fallido.",
   ("MISSING","NO_REMOTE_COMMIT")=>"El observador informó que no hay un commit remoto de backup.",
   ("STALE","REMOTE_BACKUP_TOO_OLD")=>"El observador informó que el backup remoto es demasiado antiguo.",
   ("UNKNOWN","OBSERVER_HEARTBEAT_EXPIRED")=>"No llegan observaciones dentro del plazo configurado; se desconoce la salud del backup.",
   ("UNKNOWN","REMOTE_STORAGE_NOT_CHECKED")=>"El almacenamiento remoto no fue comprobado; no confirma recuperación.",
   ("HEALTHY","RECENT_REMOTE_COMMIT")=>"El observador informó un commit remoto reciente.",
   _=>"No se recibió un código de motivo compatible; no se infiere una causa."};
  var expected=evidence.BackupStatus switch {"FAILED"=>"LAST_ATTEMPT_FAILED","MISSING"=>"NO_REMOTE_COMMIT",
   "STALE"=>"REMOTE_BACKUP_TOO_OLD","UNKNOWN"=>"REMOTE_STORAGE_NOT_CHECKED",_=>"RECENT_REMOTE_COMMIT"};
  var safeCode=code==expected?expected:evidence.BackupStatus=="UNKNOWN" && code=="OBSERVER_HEARTBEAT_EXPIRED"?code:"NO_DISPONIBLE";
  static string Line(string value)=>value.Replace('\r',' ').Replace('\n',' ').Replace('\t',' ');
  var title=evidence.Kind=="ResolveIncident"?"Backup recuperado":"Atencion de backup";
  var subject=(evidence.SyntheticTrial?"PRUEBA SINTETICA | ":"BACKUP | ")+Line(evidence.SenderLabel)+" | "+title;
  if(Encoding.UTF8.GetByteCount(subject)>100)throw new ArgumentException("Bounded SNS subject required.");
  var message=string.Join("\n",new[]{
   evidence.SyntheticTrial?"PRUEBA SINTÉTICA":"OBSERVACIÓN DE BACKUP",Line(evidence.SenderLabel)+" — "+title,"",
   "Estado: "+state,"Servicio: "+Line(evidence.Service),"Alcance: "+Line(evidence.Scope),
   "Motivo registrado: "+reason,"Código del recibo: "+safeCode,
   "Observado (UTC): "+observed.ToUniversalTime().ToString("O",CultureInfo.InvariantCulture),"",
   evidence.SyntheticTrial?"Se han reproducido recibos sintéticos. Esto no acredita un fallo real ni una restauración SQL.":"El estado procede del observador de backups. No acredita una restauración SQL.",
   "No se ha ejecutado reparación automática de infraestructura.","",
   "DATOS TÉCNICOS","Incidente: "+Line(evidence.IncidentId),"Episodio: "+evidence.Epoch.ToString(CultureInfo.InvariantCulture),
   "Efecto: "+Line(evidence.EffectId),"Tipo: "+Line(evidence.Kind),"Origen: "+Line(evidence.Source),"",
   "Entrega: la aceptación de SNS no acredita recepción en el buzón.","Acuse técnico: "+Line(evidence.Acceptance)});
  return(subject,message);
 }
}
