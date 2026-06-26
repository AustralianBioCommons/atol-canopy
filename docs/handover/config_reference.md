# Config Reference

## Verified

### Application and entrypoint settings

| Name | Source | Required | Verified behavior |
| --- | --- | --- | --- |
| `PROJECT_NAME` | `app/core/settings.py` | no | FastAPI title; default `atol-canopy` |
| `API_V1_STR` | `app/core/settings.py` | no | API prefix and docs prefix; default `/api/v1` |
| `DEBUG` | `app/core/settings.py` | no | Present in settings model; no direct behavior found outside settings object |
| `ENVIRONMENT` | `app/core/settings.py`, `app/main.py`, `scripts/entrypoint.sh` | effectively yes for predictable behavior | `dev` enables debug logging and `uvicorn --reload`; non-`prod` with no explicit CORS origins defaults to `["*"]` |
| `APP_VERSION` | `app/core/settings.py`, `Dockerfile`, `app/main.py` | no | Returned by `GET /version`; default `dev`; Docker build can inject a release value |
| `PORT` | `scripts/entrypoint.sh`, `Dockerfile` | no | Runtime listen port for the entrypoint; default `8000` |
| `APP_MODE` | `scripts/entrypoint.sh` | no | `serve` starts API; `migrate` runs migrations then exits |

### Database settings

| Name | Source | Required | Verified behavior |
| --- | --- | --- | --- |
| `DATABASE_URI` | `app/core/settings.py`, `scripts/entrypoint.sh`, `alembic/env.py` | yes for entrypoint; yes or derivable for app import | Used by SQLAlchemy engine and Alembic; entrypoint exits if it is unset |
| `POSTGRES_SERVER` | `app/core/settings.py` | required if deriving `DATABASE_URI` | Used only to derive `DATABASE_URI` inside settings |
| `POSTGRES_USER` | `app/core/settings.py` | required if deriving `DATABASE_URI` | Used only to derive `DATABASE_URI` inside settings |
| `POSTGRES_PASSWORD` | `app/core/settings.py` | required if deriving `DATABASE_URI` | Used only to derive `DATABASE_URI` inside settings |
| `POSTGRES_DB` | `app/core/settings.py` | required if deriving `DATABASE_URI` | Used only to derive `DATABASE_URI` inside settings |
| `POSTGRES_PORT` | `app/core/settings.py` | required if deriving `DATABASE_URI` | Used only to derive `DATABASE_URI` inside settings |

### Auth and token settings

| Name | Source | Required | Verified behavior |
| --- | --- | --- | --- |
| `JWT_SECRET_KEY` | `app/core/settings.py`, `app/core/security.py`, `app/core/dependencies.py` | yes | Required at startup; used to sign and verify access tokens |
| `JWT_ALGORITHM` | `app/core/settings.py`, `app/core/security.py`, `app/core/dependencies.py` | yes | Required at startup; used for JWT encode/decode |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `app/core/settings.py`, `app/api/v1/endpoints/auth.py` | no | Access-token lifetime in minutes; default `150` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `app/core/settings.py`, `app/api/v1/endpoints/auth.py` | no | Refresh-token lifetime in days; default `7` |

### CORS settings

| Name | Source | Required | Verified behavior |
| --- | --- | --- | --- |
| `BACKEND_CORS_ORIGINS` | `app/core/settings.py`, `app/main.py` | no | If set, FastAPI installs CORS middleware with those origins; if unset and `ENVIRONMENT != "prod"`, settings default it to `["*"]`; `["*"]` is rejected when `ENVIRONMENT == "prod"` |

### Repo automation secrets and workflow vars

These are not application settings, but they are verified in GitHub workflow files:

| Name | Source | Verified behavior |
| --- | --- | --- |
| `AWS_ROLE_ECR_PUSH` | `.github/workflows/build-and-deploy-dev.yml`, `build-publish.yml` | GitHub Actions assumes this AWS role before pushing images |
| `GITHUB_TOKEN` | `.github/workflows/release-please.yml` | Used by release-please |
| `AWS_REGION` | workflow env | Set to `ap-southeast-2` in the repo workflows |
| `IMAGE_REPO` | workflow env | ECR repository used by build jobs |
| `DEPLOY_FUNCTION_NAME` | workflow env | Lambda function invoked by the dev deployment workflow |

## Inferences

- `BACKEND_CORS_ORIGINS` is expected to be supplied in a Pydantic-compatible list form such as a JSON array string, because it is typed as `List[str]` in `Settings`.

## Unknown From This Repo

- The real production values for any of these settings.
- Whether there are additional deployment-time environment variables injected outside the repository.
