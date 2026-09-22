#!/usr/bin/env bash

# Validate the entire captured response before any filtering or normalization.
# Semantic checks remain with each caller; DescribeTasks retains its existing
# per-batch boundary and must not be validated only after aggregation.
validate_aws_response() {
  jq -se --arg endpoint "$1" '
    def objects: type == "array" and all(.[]; type == "object");
    def nonempty: type == "string" and length > 0;
    def optional_objects($key):
      (has($key) | not) or (.[$key] | objects);
    length == 1 and (.[0] |
      type == "object" and
      if $endpoint == "describe-listeners" then
        (.Listeners | objects and length == 1)
        and all(.Listeners[]; .DefaultActions | objects and length == 1)
      elif $endpoint == "describe-rules" then
        (.Rules | objects and length == 1)
        and all(.Rules[]; .Actions | objects and length == 1)
      elif $endpoint == "describe-task-definition" then
        (.taskDefinition | type == "object"
          and (.taskDefinitionArn | nonempty)
          and (.containerDefinitions | objects)
          and all(.containerDefinitions[];
            (.name | nonempty) and (.image | nonempty)
            and optional_objects("portMappings")
            and optional_objects("secrets")
            and optional_objects("environment"))
          and (.requiresCompatibilities | type == "array" and all(.[]; type == "string")))
      elif $endpoint == "describe-services" then
        (.failures | objects) and (.services | objects)
        and all(.services[];
          (.loadBalancers | objects) and (.deployments | objects))
      elif $endpoint == "list-tasks" then
        (.taskArns | type == "array" and all(.[]; nonempty))
      elif $endpoint == "describe-target-health" then
        (.TargetHealthDescriptions | objects)
        and all(.TargetHealthDescriptions[];
          (.Target | type == "object"
            and (.Id | nonempty)
            and (.Port | type == "number" and . == floor and . >= 1 and . <= 65535))
          and (.TargetHealth | type == "object" and (.State | nonempty)))
      else false end)
  ' >/dev/null
}
