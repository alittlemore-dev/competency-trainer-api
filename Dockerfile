FROM ghcr.io/astral-sh/uv:0.12.17-python3.14-trixie-slim AS builder

ENV APP_PATH=/project
ENV UV_VENV_PATH=/project/.venv

WORKDIR $APP_PATH

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential=12.12 \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache --no-default-groups --all-extras --no-install-project


FROM python:3.14-slim-trixie

ENV CUSTOM_USER=python-user
ENV APP_PATH=/project
ENV UV_CACHE_DIR=/project/.cache/uv
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=$APP_PATH/src
ENV PATH=$APP_PATH/.venv/bin:${PATH}

RUN apt-get update \
 && apt-get upgrade -y \
 && rm -rf /var/lib/apt/lists/* \
 && rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.14 \
 && rm -rf /usr/local/lib/python3.14/ensurepip /usr/local/lib/python3.14/site-packages/pip* \
 && groupadd --gid 10001 $CUSTOM_USER \
 && useradd --uid 10001 --gid 10001 $CUSTOM_USER \
 && mkdir -p $APP_PATH /project/.cache/uv \
 && chown -R $CUSTOM_USER:$CUSTOM_USER $APP_PATH /project/.cache

WORKDIR $APP_PATH

COPY --from=builder --chown=$CUSTOM_USER:$CUSTOM_USER /project/.venv /project/.venv
COPY --chown=$CUSTOM_USER:$CUSTOM_USER . ./
RUN chmod 755 start_application.sh

USER 10001:10001

EXPOSE 8080
CMD ["bash", "./start_application.sh", "run"]
