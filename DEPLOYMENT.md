# Deploying to Azure (App Service + PostgreSQL, CI/CD)

This backend deploys to **Azure App Service (Linux, Python)** with a **PostgreSQL** database,
built and shipped automatically by the GitHub Actions workflow in
[.github/workflows/azure-deploy.yml](.github/workflows/azure-deploy.yml).

Every push to `main` runs the test suite and, if it passes, deploys.

> **Scaling note:** automations/energy schedulers run **in-process** and the WebSocket
> notification manager keeps state **in memory**. Run a **single instance with a single worker**.
> Do not scale out (multiple instances) or use multiple workers without first moving that state
> to a shared store — duplicate schedulers and missed WebSocket messages would result.

---

## One-time Azure setup

You can do this in the Portal or with the Azure CLI. CLI version below — run it once.
Pick your own names; keep `APP_NAME` globally unique.

```bash
# 0. Login and variables
az login
RG=smarthome-rg
LOCATION=westeurope
APP_NAME=smarthome-backend            # must match AZURE_WEBAPP_NAME in the workflow
PLAN=smarthome-plan
PG_NAME=smarthome-pg-$RANDOM          # must be globally unique
PG_ADMIN=pgadmin
PG_PASSWORD='ReplaceWith-Strong-Passw0rd!'
DB_NAME=smarthome

# 1. Resource group
az group create --name $RG --location $LOCATION

# 2. PostgreSQL flexible server + database
az postgres flexible-server create \
  --resource-group $RG --name $PG_NAME --location $LOCATION \
  --admin-user $PG_ADMIN --admin-password "$PG_PASSWORD" \
  --tier Burstable --sku-name Standard_B1ms --version 16 \
  --storage-size 32 --public-access 0.0.0.0   # allow Azure services; tighten later

az postgres flexible-server db create \
  --resource-group $RG --server-name $PG_NAME --database-name $DB_NAME

# 3. App Service plan (Linux) + web app on Python 3.12
az appservice plan create --resource-group $RG --name $PLAN --sku B1 --is-linux

az webapp create --resource-group $RG --plan $PLAN --name $APP_NAME \
  --runtime "PYTHON:3.12"

# 4. Startup command (single uvicorn worker via gunicorn)
az webapp config set --resource-group $RG --name $APP_NAME \
  --startup-file "gunicorn main:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 600"

# 5. Enable WebSockets (used by notifications) and build-on-deploy
az webapp config set --resource-group $RG --name $APP_NAME --web-sockets-enabled true
az webapp config appsettings set --resource-group $RG --name $APP_NAME --settings \
  SCM_DO_BUILD_DURING_DEPLOYMENT=true

# 6. Application settings (secrets + config). The DATABASE_URL points at the PG server.
az webapp config appsettings set --resource-group $RG --name $APP_NAME --settings \
  SECRET_KEY="$(openssl rand -hex 32)" \
  ALGORITHM="HS256" \
  ACCESS_TOKEN_EXPIRE_MINUTES="30" \
  GROQ_API_KEY="your-groq-api-key" \
  CORS_ORIGINS="https://your-frontend.example.com" \
  DATABASE_URL="postgresql://${PG_ADMIN}:${PG_PASSWORD}@${PG_NAME}.postgres.database.azure.com:5432/${DB_NAME}?sslmode=require"
```

> The app reads `DATABASE_URL` directly and rewrites `postgresql://` to the `psycopg` driver,
> so no code change is needed. Tables are created automatically on first startup
> (`Base.metadata.create_all`).

---

## Wire up CI/CD (GitHub Actions)

1. **Get the publish profile** for the web app:

   ```bash
   az webapp deployment list-publishing-profiles \
     --resource-group $RG --name $APP_NAME --xml
   ```

   Copy the entire XML output.

2. **Add it as a GitHub secret** in your repo:
   `Settings → Secrets and variables → Actions → New repository secret`
   - Name: `AZURE_WEBAPP_PUBLISH_PROFILE`
   - Value: the XML from step 1

3. **Confirm the app name** matches: `AZURE_WEBAPP_NAME` in
   [.github/workflows/azure-deploy.yml](.github/workflows/azure-deploy.yml) must equal `$APP_NAME`.

4. **Push to `main`.** The workflow installs deps, runs `pytest`, and on success deploys the code.
   Azure (Oryx) installs `requirements.txt` server-side because `SCM_DO_BUILD_DURING_DEPLOYMENT=true`.

---

## Verify

```bash
curl https://$APP_NAME.azurewebsites.net/        # -> "OK"
```

Logs while debugging:

```bash
az webapp log tail --resource-group $RG --name $APP_NAME
```

---

## Notes / hardening (later)

- Restrict PostgreSQL firewall instead of `0.0.0.0` allow-all; use a VNet or Private Endpoint.
- Store `GROQ_API_KEY` / `SECRET_KEY` in Azure Key Vault and reference them from App Settings.
- For multi-instance scaling, move scheduler state and the WebSocket manager to a shared
  backend (e.g. Redis) first — see the scaling note above.
- Consider switching the publish-profile auth to OIDC (`azure/login` with federated credentials)
  to avoid long-lived secrets.
