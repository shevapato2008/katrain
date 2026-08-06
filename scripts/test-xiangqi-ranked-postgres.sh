#!/usr/bin/env bash
set -euo pipefail

compose_file="docker-compose.ranked-test.yml"
project_name="katrain-xiangqi-ranked-test-$$"
test_port="${XIANGQI_RANKED_PG_PORT:-55439}"
export XIANGQI_RANKED_PG_PORT="${test_port}"
export COMPOSE_PROJECT_NAME="${project_name}"

cleanup() {
  docker compose -f "${compose_file}" -p "${project_name}" down --volumes --remove-orphans
}
trap cleanup EXIT INT TERM

docker compose -f "${compose_file}" -p "${project_name}" up -d postgres

healthy=0
for _attempt in $(seq 1 60); do
  if docker compose -f "${compose_file}" -p "${project_name}" exec -T postgres \
    pg_isready -q -U xiangqi_ranked_test -d xiangqi_ranked_test; then
    healthy=1
    break
  fi
  sleep 1
done

if [[ "${healthy}" != "1" ]]; then
  docker compose -f "${compose_file}" -p "${project_name}" logs postgres
  exit 1
fi

export XIANGQI_RANKED_TEST_DATABASE_URL="postgresql+psycopg2://xiangqi_ranked_test:xiangqi_ranked_test_password@127.0.0.1:${test_port}/xiangqi_ranked_test"
uv run --no-sync pytest tests/web_ui/test_xiangqi_ranked_postgres.py -v
