#!/usr/bin/env bash
set -euo pipefail

printf '%-28s %s\n' \
    'install' 'Install Python dependencies.' \
    'tests / tests-fast' 'Run all tests / unit tests.' \
    'test-integration' 'Run PostgreSQL and migration tests.' \
    'tests-coverage' 'Run tests with coverage.' \
    'query-plans-realistic' 'Run the required realistic query-plan gate.' \
    'query-plans-stress' 'Run the manual large-data query-plan profile.' \
    'lint-check / types' 'Check formatting, lint and types.' \
    'security' 'Run Bandit and dependency audit.' \
    'build' 'Build the service image without starting it.' \
    'revision message="..."' 'Generate a migration against the configured database.' \
    'migrate / downgrade' 'Apply / roll back migrations against the configured database.' \
    'Runtime' 'Managed only by the sibling infra repository.'
