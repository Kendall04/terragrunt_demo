// Public source facts, not a live inventory or telemetry feed.
export const portfolioContract={mode:'demo',data:'synthetic-memory',liveConnected:false,provenance:'archify-3.1.0-with-hand-authored-inspector'};
export const topologies={
 original:{mode:'historical',flow:'API Gateway → VPC Link → ALB → API → SQL\nAPI ↔ KMS · dependencia de cifrado',label:'TOPOLOGÍA ORIGINAL V1',note:'La plataforma original fue desplegada y retirada. Blue/green son slots de una aplicación. Egreso mediante NAT Instances; esta vista no representa el ensayo az6.',nodes:[
 ['gateway','API Gateway','EDGE','Entrada HTTP pública hacia el VPC Link.','No se consulta su estado actual.','architecture'],
 ['link','VPC Link','EDGE','Conecta la entrada con el ALB interno.','No expone la aplicación ni SQL directamente.','architecture'],
 ['alb','ALB interno','GLOBAL','Encamina HTTP:8080 hacia el color activo.','El control de forwarding pertenece a delivery.','architecture'],
 ['ecs','API en Fargate','APPS / DELIVERY','Una API .NET; blue/green permiten promoción y rollback por digest.','PKI/mTLS y un segundo servicio quedan fuera de alcance de ECS.','architecture'],
 ['sql','SQL Server en EC2','DATA','SQL privado por TCP:1433. El texto se persiste cifrado.','No se ha ejecutado una consulta SQL desde esta UI.','architecture'],
 ['kms','AWS KMS','SECURITY','El backend usa el cliente KMS para cifrar y descifrar.','Esta demo no cifra ni usa claves. KMS no es PKI TLS.','architecture']
 ]},
 az6:{mode:'historical',flow:'Origen → S3/KMS → destino\nAPI local ↔ SQL restaurado · NAT solo para egreso',label:'ENSAYO CONTROLADO SQL/API · AZ6',note:'Dos EC2 privadas, S3 y un NAT Gateway temporal. No creó ECS ni ALB. El destino ya estaba preparado; hubo dos reparaciones y el entorno fue retirado.',nodes:[
 ['source','SQL origen · AZ A','EC2 PRIVADA','Produce el backup verificado y después confirma SQL inactivo.','Prueba controlada, no una pérdida real de toda la AZ.','recovery'],
 ['backup','Backup S3 + KMS','STORAGE RETENIDO','Manifiesto, checksum y versiones exactas vinculan el backup.','Retención existente 2+2 días; no prueba RPO horario.','recovery'],
 ['target','SQL destino · AZ B','EC2 PRIVADA','Restore a una base nueva, CHECKDB y marcadores recuperados.','Destino preparado; no mide aprovisionamiento frío.','recovery'],
 ['api','API co-localizada','PRUEBA SQL/API','Descifrado, lectura y escritura verificados durante el ensayo.','No fue un despliegue de ECS ni el flujo sin reparaciones.','recovery'],
 ['nat','NAT Gateway temporal','RED DEL ENSAYO','Salida para bootstrap/SSM. Se retiró antes del resto.','No confundir con las NAT Instances de V1.','recovery']
 ]}
};

// Fixed local qualification, not a current AWS inventory or successful live recovery.
export const portableEvidence=Object.freeze({
 classification:'LOCAL_WITH_DOUBLES',nativePortable:false,timersInstalled:false,
 cohostSource:'0359bafa1fbb3c48ebc53ce29836acf034381108',
 upstream:'b3d0b3b595a9257bb6d4d849c899bf4e8dbc2828',
 cohostSha256:'081b62f739cd309e84abf64b5c8e327bf6b7445214f37d85069fa070f0e2f24f',
 lambdaSha256:'4e89587b2760b5ec6d4a37a4bc6327ed6f770d0316d2e1f3fba32d4b1d54cca7',
 packageTests:44,publisherTests:33,installedFixtureChecks:42,handlerChecks:17,
 mockBackendAddresses:62,observerEc2:0,backupFreshnessHours:2,telemetryFreshnessMinutes:20,
 alarmNoticesEnabled:false,integratedDiagramDeferred:true,ssmResolved:false
});
