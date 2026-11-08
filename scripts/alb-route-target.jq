# One target receives all traffic for any positive supported weight. AWS can
# return the direct ARN and ForwardConfig together; they must agree.
def arn: type == "string" and length > 0;
(if $root == "listener" then .Listeners elif $root == "rule" then .Rules else null end)
| select(type == "array" and length == 1)
| (if $root == "listener" then .[0].DefaultActions else .[0].Actions end)
| select(type == "array" and length == 1)
| .[0]
| select(.Type == "forward")
| select((keys - ["Type", "Order", "TargetGroupArn", "ForwardConfig"]) | length == 0)
| select((has("Order") | not) or (.Order | type == "number" and . == floor and . >= 1 and . <= 50000))
| (if has("TargetGroupArn") then .TargetGroupArn | select(arn) else null end) as $direct
| (if has("ForwardConfig") then
     .ForwardConfig
     | select(type == "object")
     | select((keys - ["TargetGroups", "TargetGroupStickinessConfig"]) | length == 0)
     | select((has("TargetGroupStickinessConfig") | not) or
         (.TargetGroupStickinessConfig | type == "object"
          and ((keys - ["Enabled", "DurationSeconds"]) | length == 0)
          and (.Enabled | type == "boolean")
          and (if .Enabled or has("DurationSeconds") then
            (.DurationSeconds | type == "number" and . == floor and . >= 1 and . <= 604800)
            else true end)))
     | .TargetGroups
     | select(type == "array" and length == 1)
     | .[0]
     | select(type == "object" and ((keys - ["TargetGroupArn", "Weight"]) | length == 0))
     | select(.TargetGroupArn | arn)
     | select((has("Weight") | not) or
         (.Weight | type == "number" and . == floor and . > 0 and . <= 999))
     | .TargetGroupArn
   else null end) as $configured
| select($direct != null or $configured != null)
| select($direct == null or $configured == null or $direct == $configured)
| $direct // $configured
