# Backend

.PHONY: install-backend
install-backend:
	$(MAKE) -C backend install

.PHONY: migrate
migrate:
	$(MAKE) -C backend migrate

.PHONY: downgrade
downgrade:
	$(MAKE) -C backend downgrade

.PHONY: revision
revision:
	$(MAKE) -C backend revision

.PHONY: test-backend
test-backend:
	$(MAKE) -C backend test

.PHONY: test-backend-fast
test-backend-fast:
	$(MAKE) -C backend test-unit

.PHONY: test-backend-unit
test-backend-unit:
	$(MAKE) -C backend test-unit

.PHONY: test-backend-unit-fast
test-backend-unit-fast:
	$(MAKE) -C backend test-unit

.PHONY: test-backend-integration
test-backend-integration:
	$(MAKE) -C backend test-integration

.PHONY: test-backend-integration-fast
test-backend-integration-fast:
	$(MAKE) -C backend test-integration

.PHONY: taskiq-worker
taskiq-worker:
	$(MAKE) -C backend taskiq-worker

.PHONY: taskiq-scheduler
taskiq-scheduler:
	$(MAKE) -C backend taskiq-scheduler

.PHONY: tests-coverage
tests-coverage:
	$(MAKE) -C backend tests-coverage

.PHONY: quality-backend
quality-backend:
	$(MAKE) -C backend quality

.PHONY: security-backend
security-backend:
	$(MAKE) -C backend security

.PHONY: security
security: security-backend

# Combined

.PHONY: install
install: install-backend

.PHONY: tests
tests: test-backend

.PHONY: tests-fast
tests-fast: test-backend-fast

.PHONY: query-plans-realistic
query-plans-realistic:
	$(MAKE) -C backend query-plans-realistic

.PHONY: query-plans-stress
query-plans-stress:
	$(MAKE) -C backend query-plans-stress

.PHONY: query-plans-baseline-candidate
query-plans-baseline-candidate:
	$(MAKE) -C backend query-plans-baseline-candidate

.PHONY: clean
clean:
	$(MAKE) -C backend clean
