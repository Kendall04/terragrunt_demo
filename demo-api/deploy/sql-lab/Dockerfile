# Opt-in laboratory variant. Select -f deploy/sql-lab/Dockerfile explicitly; default Dockerfile is unchanged.
# ===========================
# Base image (runtime)
# ===========================
# Verified linux/amd64 manifests; update procedure: ../terraform/docs/e14-container-hardening.md
FROM mcr.microsoft.com/dotnet/aspnet:10.0.13@sha256:e4b445f93a5deeb6bd7de300febceb8dd7e481ac65ccf1b474eddc3642a3010f AS base
WORKDIR /app

EXPOSE 8080
ENV ASPNETCORE_URLS=http://+:8080
# Vendor security fixes for the pinned Noble base (USN-8974-1, USN-8996-1,
# USN-8954-1, USN-8944-1, USN-8945-1). Exact versions fail closed if unavailable.
USER root
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
       apt=2.8.4ubuntu0.1 libapt-pkg6.0t64=2.8.4ubuntu0.1 \
       libpcre2-8-0=10.42-4ubuntu2.2 zlib1g=1:1.3.dfsg-3.1ubuntu2.3 \
       ca-certificates=20260816ubuntu0.24.04.2 liblzma5=5.6.1+really5.4.5-1ubuntu0.4 \
    && rm -rf /var/lib/apt/lists/*
# Explicit lab-only public trust; no private certificate material.
COPY --chown=0:0 --chmod=0644 deploy/trust/sql.demo.internal.crt /usr/local/share/ca-certificates/ecs-sql-lab.crt
RUN test "$(openssl x509 -in /usr/local/share/ca-certificates/ecs-sql-lab.crt -outform DER | sha256sum | cut -d' ' -f1)" = "206095fa0ba9e17a84c80eff5021db93d05e2dc377e982a64d517696ed21a1e7" \
    && openssl verify -CAfile /usr/local/share/ca-certificates/ecs-sql-lab.crt -purpose sslserver -verify_hostname sql.demo.internal /usr/local/share/ca-certificates/ecs-sql-lab.crt \
    && update-ca-certificates
USER $APP_UID

# ===========================
# Build image (SDK)
# ===========================
FROM mcr.microsoft.com/dotnet/sdk:10.0.402@sha256:3a48280a9a7c6276c3eeaba1efa6a08820f18c84fb9e6274c187719ecfaf9fbc AS build
ARG BUILD_CONFIGURATION=Release
WORKDIR /src

# Copy only solution and project files first (cache-friendly)
COPY terragrunt-demo/terragrunt-demo.csproj terragrunt-demo/packages.lock.json terragrunt-demo/
# If you had more projects, list each with its own COPY

RUN dotnet restore terragrunt-demo/terragrunt-demo.csproj --locked-mode

# Copy the remaining source
COPY terragrunt-demo/ terragrunt-demo/

# Build
RUN dotnet publish terragrunt-demo/terragrunt-demo.csproj \
    -c $BUILD_CONFIGURATION \
    --no-restore \
    -o /app/publish \
    /p:UseAppHost=false \
    && chmod -R a+rX /app/publish

# ===========================
# Final image
# ===========================
FROM base AS final
WORKDIR /app

# Keep published files root-owned and readable; runtime does not modify /app.
COPY --from=build /app/publish .
USER $APP_UID

ENTRYPOINT ["dotnet", "terragrunt-demo.dll"]
