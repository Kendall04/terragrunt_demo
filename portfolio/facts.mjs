// Public source facts, not a live inventory or telemetry feed.
export const topologies={
 original:{flow:'API Gateway → VPC Link → ALB → API → SQL\nAPI ↔ KMS · dependencia de cifrado',label:'TOPOLOGÍA ORIGINAL V1',note:'La plataforma original fue desplegada y retirada. Blue/green son slots de una aplicación. Egreso mediante NAT Instances; esta vista no representa el ensayo az6.',nodes:[
 ['gateway','API Gateway','EDGE','Entrada HTTP pública hacia el VPC Link.','No se consulta su estado actual.','architecture'],
 ['link','VPC Link','EDGE','Conecta la entrada con el ALB interno.','No expone la aplicación ni SQL directamente.','architecture'],
 ['alb','ALB interno','GLOBAL','Encamina HTTP:8080 hacia el color activo.','El control de forwarding pertenece a delivery.','architecture'],
 ['ecs','API en Fargate','APPS / DELIVERY','Una API .NET; blue/green permiten promoción y rollback por digest.','PKI/mTLS y un segundo servicio no se declaran implementados.','architecture'],
 ['sql','SQL Server en EC2','DATA','SQL privado por TCP:1433. El texto se persiste cifrado.','No se ha ejecutado una consulta SQL desde esta UI.','architecture'],
 ['kms','AWS KMS','SECURITY','El backend usa el cliente KMS para cifrar y descifrar.','Esta demo no cifra ni usa claves. KMS no es PKI TLS.','architecture']
 ]},
 az6:{flow:'Origen → S3/KMS → destino\nAPI local ↔ SQL restaurado · NAT solo para egreso',label:'ENSAYO CONTROLADO SQL/API · AZ6',note:'Dos EC2 privadas, S3 y un NAT Gateway temporal. No creó ECS ni ALB. El destino ya estaba preparado; hubo dos reparaciones y el entorno fue retirado.',nodes:[
 ['source','SQL origen · AZ A','EC2 PRIVADA','Produce el backup verificado y después confirma SQL inactivo.','Prueba controlada, no una pérdida real de toda la AZ.','recovery'],
 ['backup','Backup S3 + KMS','STORAGE RETENIDO','Manifiesto, checksum y versiones exactas vinculan el backup.','Retención existente 2+2 días; no prueba RPO horario.','recovery'],
 ['target','SQL destino · AZ B','EC2 PRIVADA','Restore a una base nueva, CHECKDB y marcadores recuperados.','Destino preparado; no mide aprovisionamiento frío.','recovery'],
 ['api','API co-localizada','PRUEBA SQL/API','Descifrado, lectura y escritura verificados durante el ensayo.','No fue un despliegue de ECS ni el flujo sin reparaciones.','recovery'],
 ['nat','NAT Gateway temporal','RED DEL ENSAYO','Salida para bootstrap/SSM. Se retiró antes del resto.','No confundir con las NAT Instances de V1.','recovery']
 ]}
};
