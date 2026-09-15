import pytest

from core.agent_access.schemas import (
    AgentAuditPolicy,
    AgentCertificatePolicy,
    MatrixAgentPolicy,
)


class TestAgentCertificatePolicy:
    @pytest.mark.parametrize(
        ("lifetime_seconds", "rotation_window_seconds", "normal_access_overlap_seconds"),
        [
            (0, 1, 1),
            (100, 100, 1),
            (100, 50, 50),
        ],
    )
    def test_rejects_non_positive_or_incoherent_windows(
        self,
        lifetime_seconds: int,
        rotation_window_seconds: int,
        normal_access_overlap_seconds: int,
    ) -> None:
        with pytest.raises(ValueError, match="certificate policy"):
            AgentCertificatePolicy(
                lifetime_seconds=lifetime_seconds,
                rotation_window_seconds=rotation_window_seconds,
                normal_access_overlap_seconds=normal_access_overlap_seconds,
            )


class TestAgentAuditPolicy:
    @pytest.mark.parametrize(
        ("page_size_max", "retention_seconds"),
        [(0, 1), (1, 0)],
    )
    def test_rejects_non_positive_limits(
        self,
        page_size_max: int,
        retention_seconds: int,
    ) -> None:
        with pytest.raises(ValueError, match="audit policy"):
            AgentAuditPolicy(
                page_size_max=page_size_max,
                retention_seconds=retention_seconds,
            )


class TestMatrixAgentPolicy:
    @pytest.mark.parametrize(
        ("claim_ttl_seconds", "minimum_resource_count", "maximum_resource_count"),
        [(0, 1, 3), (1, 0, 3), (1, 4, 3)],
    )
    def test_rejects_non_positive_or_incoherent_limits(
        self,
        claim_ttl_seconds: int,
        minimum_resource_count: int,
        maximum_resource_count: int,
    ) -> None:
        with pytest.raises(ValueError, match="matrix agent policy"):
            MatrixAgentPolicy(
                claim_ttl_seconds=claim_ttl_seconds,
                minimum_resource_count=minimum_resource_count,
                maximum_resource_count=maximum_resource_count,
            )
