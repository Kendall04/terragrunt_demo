# ===========================
# Base image (runtime)
# ===========================
# Verified linux/amd64 manifests; update procedure: ../terraform/docs/e14-container-hardening.md
FROM mcr.microsoft.com/dotnet/aspnet:8.0@sha256:9a432d3500734557e5fecea0336bf274c85de15aa55505a2dafe06e44f0cd024 AS base
WORKDIR /app

EXPOSE 8080
ENV ASPNETCORE_URLS=http://+:8080
USER $APP_UID

# ===========================
# Build image (SDK)
# ===========================
FROM mcr.microsoft.com/dotnet/sdk:8.0@sha256:e1d5584f7c7f45439449054292acadf4f71730034507186497bab3d539a5a9b7 AS build
ARG BUILD_CONFIGURATION=Release
WORKDIR /src

# Copy only solution and project files first (cache-friendly)
COPY terragrunt-demo/terragrunt-demo.csproj terragrunt-demo/
# If you had more projects, list each with its own COPY

RUN dotnet restore terragrunt-demo/terragrunt-demo.csproj

# Copy the remaining source
COPY terragrunt-demo/ terragrunt-demo/

# Build
RUN dotnet publish terragrunt-demo/terragrunt-demo.csproj \
    -c $BUILD_CONFIGURATION \
    -o /app/publish \
    /p:UseAppHost=false

# ===========================
# Final image
# ===========================
FROM base AS final
WORKDIR /app

# Keep published files root-owned and readable; runtime does not modify /app.
COPY --from=build /app/publish .
USER $APP_UID

ENTRYPOINT ["dotnet", "terragrunt-demo.dll"]
