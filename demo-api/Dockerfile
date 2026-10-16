# ===========================
# Base image (runtime)
# ===========================
# Verified linux/amd64 manifests; update procedure: ../terraform/docs/e14-container-hardening.md
FROM mcr.microsoft.com/dotnet/aspnet:10.0.13@sha256:e4b445f93a5deeb6bd7de300febceb8dd7e481ac65ccf1b474eddc3642a3010f AS base
WORKDIR /app

EXPOSE 8080
ENV ASPNETCORE_URLS=http://+:8080
USER $APP_UID

# ===========================
# Build image (SDK)
# ===========================
FROM mcr.microsoft.com/dotnet/sdk:10.0.402@sha256:3a48280a9a7c6276c3eeaba1efa6a08820f18c84fb9e6274c187719ecfaf9fbc AS build
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
