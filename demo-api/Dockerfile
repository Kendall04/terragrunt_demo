# ===========================
# Base image (runtime)
# ===========================
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS base
WORKDIR /app

EXPOSE 8080
ENV ASPNETCORE_URLS=http://+:8080

# ===========================
# Build image (SDK)
# ===========================
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
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

COPY --from=build /app/publish .

ENTRYPOINT ["dotnet", "terragrunt-demo.dll"]
