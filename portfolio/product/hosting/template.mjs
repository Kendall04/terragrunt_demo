// Offline generator. This module never calls AWS or deploys resources.
import { mkdir, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { staticFiles } from "../build.mjs";
import { CSP_DEMO } from "../server.mjs";
import { diagramPolicy } from "../../archify.mjs";

export async function functions() {
  const paths = [...(await staticFiles()).keys(), "MANIFEST.json"];
  const allowed = Object.fromEntries(paths.map((p) => ["/" + p, true]));
  const routes = { "/": "/index.html" };
  for (const r of ["demo", "architecture", "resilience", "evidence"]) {
    routes["/" + r] = "/" + r + "/index.html";
    routes["/" + r + "/"] = routes["/" + r];
  }
  const common = `function security(h, diagram) {
    h['content-security-policy']={value:diagram?${JSON.stringify(diagramPolicy + "; frame-ancestors 'self'; sandbox allow-scripts")}:${JSON.stringify(CSP_DEMO)}};
    h['strict-transport-security']={value:'max-age=31536000'};
    h['x-content-type-options']={value:'nosniff'};
    h['referrer-policy']={value:'no-referrer'};
    h['permissions-policy']={value:'camera=(), microphone=(), geolocation=()'};
    h['cross-origin-resource-policy']={value:'same-origin'};
    return h;
  }`;
  const request = `${common}
var allowed=${JSON.stringify(allowed)};
var routes=${JSON.stringify(routes)};
function handler(event) {
  var r=event.request, u=r.uri;
  if(r.method!=='GET' && r.method!=='HEAD') return {statusCode:405,statusDescription:'Method Not Allowed',headers:security({'content-type':{value:'text/plain; charset=utf-8'},allow:{value:'GET, HEAD'}},false),body:'Method not allowed'};
  if(Object.prototype.hasOwnProperty.call(routes,u)) u=routes[u];
  if(!Object.prototype.hasOwnProperty.call(allowed,u)) return {statusCode:404,statusDescription:'Not Found',headers:security({'content-type':{value:'text/plain; charset=utf-8'},'cache-control':{value:'no-store'}},false),body:'Not found'};
  r.uri=u;
  return r;
}`;
  const response = `${common}
function handler(event) {
  var r=event.response, u=event.request.uri;
  r.headers=security(r.headers,u.indexOf('/diagrams/')===0 || u.indexOf('/reading/')===0);
  return r;
}`;
  for (const code of [request, response])
    if (Buffer.byteLength(code) > 10000)
      throw new Error("CloudFront Function exceeds 10KB");
  return { request, response };
}
export async function template() {
  const f = await functions();
  const ref = (x) => ({ Ref: x }),
    sub = (x) => ({ "Fn::Sub": x }),
    att = (r, a) => ({ "Fn::GetAtt": [r, a] });
  const tags = [
    { Key: "Project", Value: "ecs-v2-portfolio" },
    { Key: "Edition", Value: "DEMO" },
    { Key: "Owner", Value: "Kendall" },
    { Key: "Lifecycle", Value: "independent-static-hosting" },
  ];
  return {
    AWSTemplateFormatVersion: "2010-09-09",
    Description:
      "ECS portfolio DEMO only. Independent of ECS runtime and EKS. No API origin or IAM role.",
    Parameters: {
      Release: {
        Type: "String",
        AllowedPattern: "[a-f0-9]{64}",
        Description: "Verified static MANIFEST contentSHA256",
      },
      Enabled: {
        Type: "String",
        AllowedValues: ["true", "false"],
        Default: "false",
        Description:
          "Enable only after FREE subscription ACTIVE and object checksums verified",
      },
    },
    Conditions: { Published: { "Fn::Equals": [ref("Enabled"), "true"] } },
    Resources: {
      Assets: {
        Type: "AWS::S3::Bucket",
        DeletionPolicy: "Retain",
        UpdateReplacePolicy: "Retain",
        Properties: {
          BucketName: sub("ecs-v2-portfolio-${AWS::AccountId}-${AWS::Region}"),
          PublicAccessBlockConfiguration: {
            BlockPublicAcls: true,
            IgnorePublicAcls: true,
            BlockPublicPolicy: true,
            RestrictPublicBuckets: true,
          },
          OwnershipControls: {
            Rules: [{ ObjectOwnership: "BucketOwnerEnforced" }],
          },
          BucketEncryption: {
            ServerSideEncryptionConfiguration: [
              { ServerSideEncryptionByDefault: { SSEAlgorithm: "AES256" } },
            ],
          },
          VersioningConfiguration: { Status: "Enabled" },
          Tags: tags,
        },
      },
      OriginAccess: {
        Type: "AWS::CloudFront::OriginAccessControl",
        Properties: {
          OriginAccessControlConfig: {
            Name: "ecs-v2-portfolio-oac",
            OriginAccessControlOriginType: "s3",
            SigningBehavior: "always",
            SigningProtocol: "sigv4",
          },
        },
      },
      Routes: {
        Type: "AWS::CloudFront::Function",
        Properties: {
          Name: "ecs-v2-portfolio-routes",
          AutoPublish: true,
          FunctionConfig: {
            Comment: "Exact static allowlist. No API, proxy or SPA catch-all.",
            Runtime: "cloudfront-js-2.0",
          },
          FunctionCode: f.request,
        },
      },
      Headers: {
        Type: "AWS::CloudFront::Function",
        Properties: {
          Name: "ecs-v2-portfolio-headers",
          AutoPublish: true,
          FunctionConfig: {
            Comment:
              "DEMO and opaque Archify CSP. No custom response headers policy.",
            Runtime: "cloudfront-js-2.0",
          },
          FunctionCode: f.response,
        },
      },
      WebACL: {
        Type: "AWS::WAFv2::WebACL",
        Properties: {
          Name: "ecs-v2-portfolio-free",
          Scope: "CLOUDFRONT",
          DefaultAction: { Allow: {} },
          VisibilityConfig: {
            SampledRequestsEnabled: false,
            CloudWatchMetricsEnabled: false,
            MetricName: "ecsPortfolio",
          },
          Rules: [
            {
              Name: "PerIPRateLimit",
              Priority: 0,
              Action: { Block: {} },
              Statement: {
                RateBasedStatement: {
                  Limit: 1000,
                  AggregateKeyType: "IP",
                  EvaluationWindowSec: 300,
                },
              },
              VisibilityConfig: {
                SampledRequestsEnabled: false,
                CloudWatchMetricsEnabled: false,
                MetricName: "ecsPortfolioRate",
              },
            },
          ],
          Tags: tags,
        },
      },
      Distribution: {
        Type: "AWS::CloudFront::Distribution",
        Properties: {
          Tags: tags,
          DistributionConfig: {
            Comment: "ECS V2 Cloud Resilience Laboratory - static DEMO only",
            Enabled: { "Fn::If": ["Published", true, false] },
            IPV6Enabled: true,
            HttpVersion: "http2and3",
            PriceClass: "PriceClass_100",
            ViewerCertificate: { CloudFrontDefaultCertificate: true },
            WebACLId: att("WebACL", "Arn"),
            Origins: [
              {
                Id: "PrivateAssets",
                DomainName: att("Assets", "RegionalDomainName"),
                OriginPath: sub("/releases/${Release}"),
                OriginAccessControlId: ref("OriginAccess"),
                S3OriginConfig: { OriginAccessIdentity: "" },
              },
            ],
            DefaultCacheBehavior: {
              TargetOriginId: "PrivateAssets",
              ViewerProtocolPolicy: "redirect-to-https",
              AllowedMethods: ["GET", "HEAD"],
              CachedMethods: ["GET", "HEAD"],
              Compress: true,
              CachePolicyId: "658327ea-f89d-4fab-a63d-7e88639e58f6",
              FunctionAssociations: [
                {
                  EventType: "viewer-request",
                  FunctionARN: att("Routes", "FunctionMetadata.FunctionARN"),
                },
                {
                  EventType: "viewer-response",
                  FunctionARN: att("Headers", "FunctionMetadata.FunctionARN"),
                },
              ],
            },
          },
        },
      },
      BucketPolicy: {
        Type: "AWS::S3::BucketPolicy",
        Properties: {
          Bucket: ref("Assets"),
          PolicyDocument: {
            Version: "2012-10-17",
            Statement: [
              {
                Sid: "OnlyThisDistribution",
                Effect: "Allow",
                Principal: { Service: "cloudfront.amazonaws.com" },
                Action: "s3:GetObject",
                Resource: sub("${Assets.Arn}/releases/*"),
                Condition: {
                  StringEquals: {
                    "AWS:SourceArn": sub(
                      "arn:${AWS::Partition}:cloudfront::${AWS::AccountId}:distribution/${Distribution}",
                    ),
                  },
                },
              },
              {
                Sid: "TLSOnly",
                Effect: "Deny",
                Principal: "*",
                Action: "s3:*",
                Resource: [att("Assets", "Arn"), sub("${Assets.Arn}/*")],
                Condition: { Bool: { "aws:SecureTransport": "false" } },
              },
            ],
          },
        },
      },
      FreeSubscription: {
        Type: "AWS::PricingPlanManager::Subscription",
        Properties: {
          PlanFamily: "CloudFront",
          PlanTier: "FREE",
          UsageLevel: "DEFAULT",
          ResourceArns: [
            sub(
              "arn:${AWS::Partition}:cloudfront::${AWS::AccountId}:distribution/${Distribution}",
            ),
            att("WebACL", "Arn"),
          ],
        },
      },
    },
    Outputs: {
      URL: { Value: sub("https://${Distribution.DomainName}") },
      DistributionId: { Value: ref("Distribution") },
      Bucket: { Value: ref("Assets") },
      Subscription: { Value: ref("FreeSubscription") },
      Release: { Value: ref("Release") },
    },
  };
}
if (
  process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  if (process.argv.length !== 3)
    throw new Error("Usage: node template.mjs <output-directory>");
  const directory = path.resolve(process.argv[2]);
  await mkdir(directory, { recursive: true });
  const bytes = JSON.stringify(await template(), null, 2) + "\n";
  await writeFile(path.join(directory, "template.json"), bytes, { flag: "wx" });
  console.log(
    JSON.stringify({
      file: path.join(directory, "template.json"),
      sha256: createHash("sha256").update(bytes).digest("hex"),
      bytes: Buffer.byteLength(bytes),
    }),
  );
}
