from dataclasses import dataclass
from typing import Any

from httpx import Response
from litestar.testing import TestClient


@dataclass(kw_only=True, frozen=True, slots=True)
class APIHelper:
    client: TestClient

    @staticmethod
    def _entity_id(value: int | str) -> str:
        if isinstance(value, str):
            return value
        return f"{value:032x}"

    @staticmethod
    def _headers_with_cookies(
        *,
        headers: dict[str, str],
        cookies: dict[str, str] | None,
    ) -> dict[str, str]:
        if cookies is None:
            return headers
        return {
            **headers,
            "Cookie": "; ".join(f"{name}={value}" for name, value in cookies.items()),
        }

    def get_health(self) -> Response:
        return self.client.get("/api/healthcheck")

    def get_health_ready(self) -> Response:
        return self.client.get("/api/healthcheck/ready")

    def get_i18n_languages(self) -> Response:
        return self.client.get("/api/i18n/languages")

    def get_i18n_bundle(self, language: str) -> Response:
        return self.client.get(f"/api/i18n/bundles/{language}")

    def get_admin_agent_clients(self) -> Response:
        return self.client.get("/api/admin/agent-clients")

    def get_admin_tools_auth_sessions(self) -> Response:
        return self.client.get("/api/admin/tools/auth-sessions")

    def post_admin_tools_auth_sessions_prune(self) -> Response:
        return self.client.post("/api/admin/tools/auth-sessions/prune")

    def get_admin_tools_cache(self) -> Response:
        return self.client.get("/api/admin/tools/cache")

    def post_admin_tools_cache_clear(self) -> Response:
        return self.client.post("/api/admin/tools/cache/clear")

    def post_admin_tools_cache_warm(self) -> Response:
        return self.client.post("/api/admin/tools/cache/warm")

    def get_admin_tools_cache_warm_operation(self, *, operation_id: str) -> Response:
        return self.client.get(f"/api/admin/tools/cache/warm/{operation_id}")

    def post_admin_agent_client(self, *, data: dict[str, Any]) -> Response:
        return self.client.post("/api/admin/agent-clients", json=data)

    def post_revoke_admin_agent_client(self, *, client_id: str) -> Response:
        return self.client.post(f"/api/admin/agent-clients/{client_id}/revoke")

    def get_admin_agent_client_audit(
        self,
        *,
        client_id: str,
        page_size: int | None,
        cursor_created_at: str | None = None,
        cursor_event_id: str | None = None,
    ) -> Response:
        params: dict[str, str | int] = {
            key: value
            for key, value in (
                ("pageSize", page_size),
                ("cursorCreatedAt", cursor_created_at),
                ("cursorEventId", cursor_event_id),
            )
            if value is not None
        }
        return self.client.get(
            f"/api/admin/agent-clients/{client_id}/audit",
            params=params,
        )

    def get_sitemap_xml(self) -> Response:
        return self.client.get("/sitemap.xml")

    def get_robots_txt(self) -> Response:
        return self.client.get("/robots.txt")

    def get_search_competency_matrix_resources(
        self,
        search_name: str,
        limit: int | None = 10,
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str | int] = {"searchName": search_name}
        if language is not None:
            params["language"] = language
        if limit is not None:
            params["limit"] = limit
        return self.client.get(
            "/api/admin/competency-matrix/resources/search",
            params=params,
        )

    def get_competency_matrix_sheets(self, language: str | None = "ru") -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.get("/api/competency-matrix/sheets", params=params)

    def get_wiki_link_targets(self, language: str | None = "ru") -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.get("/api/admin/wiki-links/targets", params=params)

    def get_competency_matrix_items(
        self,
        sheet_key: str = "",
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str] = {"sheetKey": sheet_key}
        if language is not None:
            params["language"] = language
        return self.client.get(
            "/api/competency-matrix/items",
            params=params,
        )

    def get_admin_competency_matrix_items(
        self,
        sheet_key: str = "",
        only_published: bool | None = True,
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str | bool] = {"sheetKey": sheet_key}
        if language is not None:
            params["language"] = language
        if only_published is not None:
            params["onlyPublished"] = only_published
        return self.client.get(
            "/api/admin/competency-matrix/items",
            params=params,
        )

    def get_admin_competency_matrix_workspace_items(
        self,
        page: int | None = 1,
        page_size: int | None = 20,
        language: str | None = "ru",
        sort: str | None = "newest",
        search_query: str | None = None,
        sheet_keys: list[str] | None = None,
        grades: list[str] | None = None,
        section_ids: list[str] | None = None,
        subsection_ids: list[str] | None = None,
        sections: list[str] | None = None,
        subsections: list[str] | None = None,
        publish_statuses: list[str] | None = None,
        interview_frequencies: list[str] | None = None,
        published_from: str | None = None,
        published_to: str | None = None,
        has_missing_fields: bool | None = None,
    ) -> Response:
        params: dict[str, str | int | bool | list[str]] = {
            key: value
            for key, value in (
                ("page", page),
                ("pageSize", page_size),
                ("language", language),
                ("sort", sort),
                ("searchQuery", search_query),
                ("sheetKeys", sheet_keys),
                ("grades", grades),
                ("sectionIds", section_ids),
                ("subsectionIds", subsection_ids),
                ("sections", sections),
                ("subsections", subsections),
                ("publishStatuses", publish_statuses),
                ("interviewFrequencies", interview_frequencies),
                ("publishedFrom", published_from),
                ("publishedTo", published_to),
                ("hasMissingFields", has_missing_fields),
            )
            if value is not None
        }
        return self.client.get(
            "/api/admin/competency-matrix/items/workspace",
            params=params,
        )

    def get_admin_competency_matrix_workspace_filter_options(
        self,
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.get(
            "/api/admin/competency-matrix/items/filter-options",
            params=params,
        )

    def get_admin_competency_matrix_item(
        self,
        pk: int | str,
        only_published: bool | None = True,
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str | bool] = {}
        if language is not None:
            params["language"] = language
        if only_published is not None:
            params["onlyPublished"] = only_published
        return self.client.get(
            f"/api/admin/competency-matrix/items/detail/{self._entity_id(pk)}",
            params=params,
        )

    def get_public_competency_matrix_item(
        self,
        slug: str,
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.get(
            f"/api/competency-matrix/items/public/{slug}",
            params=params,
        )

    def post_create_item(self, data: dict[str, Any], language: str | None = "ru") -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.post("/api/admin/competency-matrix/items", params=params, json=data)

    def post_question_suggestion(
        self,
        question: str,
        sheet: str = "python",
        headers: dict[str, str] | None = None,
    ) -> Response:
        return self.client.post(
            "/api/competency-matrix/question-suggestions",
            headers=headers,
            json={"question": question, "sheet": sheet},
        )

    def get_queued_matrix_questions(self) -> Response:
        return self.client.get("/api/admin/competency-matrix/queued-questions")

    def post_create_queued_matrix_question(
        self,
        question: str,
        sheet: str | None = None,
    ) -> Response:
        return self.client.post(
            "/api/admin/competency-matrix/queued-questions",
            json={"question": question, "sheet": sheet},
        )

    def post_import_queued_matrix_questions(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str,
        selected_row_numbers: list[int],
    ) -> Response:
        return self.client.post(
            "/api/admin/competency-matrix/queued-questions/import",
            files={"file": (filename, content, content_type)},
            data={
                "selectedRowNumbers": [str(row_number) for row_number in selected_row_numbers],
            },
        )

    def post_preview_queued_matrix_questions(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> Response:
        return self.client.post(
            "/api/admin/competency-matrix/queued-questions/import/preview",
            files={"file": (filename, content, content_type)},
        )

    def delete_queued_matrix_question(self, question_id: int | str) -> Response:
        return self.client.delete(
            f"/api/admin/competency-matrix/queued-questions/{self._entity_id(question_id)}",
        )

    def post_release_queued_matrix_question_claim(self, question_id: int | str) -> Response:
        return self.client.post(
            "/api/admin/competency-matrix/queued-questions/"
            f"{self._entity_id(question_id)}/release-agent-claim",
        )

    def post_create_item_from_queue(
        self,
        question_id: int | str,
        data: dict[str, Any],
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.post(
            "/api/admin/competency-matrix/queued-questions/"
            f"{self._entity_id(question_id)}/create-item",
            params=params,
            json=data,
        )

    def put_update_matrix_sheet_priorities(self, ordered_ids: list[int | str]) -> Response:
        return self.client.put(
            "/api/admin/competency-matrix/sheets/priorities",
            json={"orderedIds": [self._entity_id(item_id) for item_id in ordered_ids]},
        )

    def put_update_matrix_section_priorities(
        self,
        *,
        sheet_id: int | str,
        ordered_ids: list[int | str],
    ) -> Response:
        return self.client.put(
            f"/api/admin/competency-matrix/sheets/{self._entity_id(sheet_id)}/sections/priorities",
            json={"orderedIds": [self._entity_id(item_id) for item_id in ordered_ids]},
        )

    def put_update_matrix_subsection_priorities(
        self,
        *,
        section_id: int | str,
        ordered_ids: list[int | str],
    ) -> Response:
        return self.client.put(
            f"/api/admin/competency-matrix/sections/{self._entity_id(section_id)}"
            "/subsections/priorities",
            json={"orderedIds": [self._entity_id(item_id) for item_id in ordered_ids]},
        )

    def put_update_item(
        self,
        pk: int | str,
        data: dict[str, Any],
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.put(
            f"/api/admin/competency-matrix/items/detail/{self._entity_id(pk)}",
            params=params,
            json=data,
        )

    def delete_item(self, pk: int | str) -> Response:
        return self.client.delete(
            f"/api/admin/competency-matrix/items/detail/{self._entity_id(pk)}",
        )

    def post_set_draft_status_to_item(self, pk: int | str) -> Response:
        return self.client.post(
            f"/api/admin/competency-matrix/items/detail/{self._entity_id(pk)}/set-draft",
        )

    def post_set_published_status_to_item(self, pk: int | str) -> Response:
        return self.client.post(
            f"/api/admin/competency-matrix/items/detail/{self._entity_id(pk)}/set-published",
        )

    def get_articles(
        self,
        page: int | None = 1,
        page_size: int | None = 10,
        language: str | None = "ru",
        tag_slug: str | None = None,
        published_from: str | None = None,
        published_to: str | None = None,
        search_query: str | None = None,
    ) -> Response:
        params: dict[str, str | int] = {}
        if language is not None:
            params["language"] = language
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        if tag_slug is not None:
            params["tagSlug"] = tag_slug
        if published_from is not None:
            params["publishedFrom"] = published_from
        if published_to is not None:
            params["publishedTo"] = published_to
        if search_query is not None:
            params["searchQuery"] = search_query
        return self.client.get("/api/articles", params=params)

    def get_admin_articles(
        self,
        page: int | None = 1,
        page_size: int | None = 10,
        publish_status: str | None = None,
        language: str | None = "ru",
        tag_slug: str | None = None,
        published_from: str | None = None,
        published_to: str | None = None,
        search_query: str | None = None,
    ) -> Response:
        params: dict[str, str | int] = {}
        if language is not None:
            params["language"] = language
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        if publish_status is not None:
            params["publishStatus"] = publish_status
        if tag_slug is not None:
            params["tagSlug"] = tag_slug
        if published_from is not None:
            params["publishedFrom"] = published_from
        if published_to is not None:
            params["publishedTo"] = published_to
        if search_query is not None:
            params["searchQuery"] = search_query
        return self.client.get("/api/admin/articles", params=params)

    def get_article(
        self,
        slug: str,
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.get(f"/api/articles/detail/{slug}", params=params)

    def get_admin_article(
        self,
        slug: str,
        only_published: bool | None = True,
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str | bool] = {}
        if language is not None:
            params["language"] = language
        if only_published is not None:
            params["onlyPublished"] = only_published
        return self.client.get(f"/api/admin/articles/detail/{slug}", params=params)

    def get_article_public_stats(self, article_ids: list[str] | None) -> Response:
        params: dict[str, list[str]] = {}
        if article_ids is not None:
            params["articleIds"] = article_ids
        return self.client.get("/api/articles/public-stats", params=params)

    def post_article_view(self, slug: str, language: str | None = "ru") -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.post(
            f"/api/articles/detail/{slug}/analytics/view",
            params=params,
        )

    def post_article_engaged_view(self, slug: str, language: str | None = "ru") -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.post(
            f"/api/articles/detail/{slug}/analytics/engaged-view",
            params=params,
        )

    def post_article_reaction(
        self,
        slug: str,
        data: dict[str, Any],
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.post(f"/api/articles/detail/{slug}/reaction", params=params, json=data)

    def get_article_stats(
        self,
        date_from: str | None,
        date_to: str | None,
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        if date_from is not None:
            params["dateFrom"] = date_from
        if date_to is not None:
            params["dateTo"] = date_to
        return self.client.get("/api/admin/articles/stats", params=params)

    def get_articles_tree(self, language: str | None = "ru") -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.get("/api/articles/tree", params=params)

    def get_admin_articles_tree(self, language: str | None = "ru") -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.get("/api/admin/articles/tree", params=params)

    def get_admin_article_folders(self, language: str | None = "ru") -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.get("/api/admin/articles/folders", params=params)

    def post_create_article_folder(
        self,
        data: dict[str, Any],
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.post("/api/admin/articles/folders", params=params, json=data)

    def put_update_article_folder_priorities(self, ordered_ids: list[int | str]) -> Response:
        return self.client.put(
            "/api/admin/articles/folders/priorities",
            json={"orderedIds": [self._entity_id(ordered_id) for ordered_id in ordered_ids]},
        )

    def post_create_article(self, data: dict[str, Any], language: str | None = "ru") -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.post("/api/admin/articles", params=params, json=data)

    def get_admin_accounts(self, page: int | None = 1, page_size: int | None = 20) -> Response:
        params: dict[str, int] = {
            key: value
            for key, value in (("page", page), ("pageSize", page_size))
            if value is not None
        }
        return self.client.get("/api/admin/accounts", params=params)

    def post_create_admin_account(self, data: dict[str, Any]) -> Response:
        return self.client.post("/api/admin/accounts", json=data)

    def get_admin_account(self, username: str) -> Response:
        return self.client.get(f"/api/admin/accounts/{username}")

    def put_admin_account_role(self, username: str, data: dict[str, Any]) -> Response:
        return self.client.put(f"/api/admin/accounts/{username}/role", json=data)

    def put_admin_account_password(self, username: str, data: dict[str, Any]) -> Response:
        return self.client.put(f"/api/admin/accounts/{username}/password", json=data)

    def post_activate_admin_account(self, username: str) -> Response:
        return self.client.post(f"/api/admin/accounts/{username}/activate")

    def post_deactivate_admin_account(self, username: str) -> Response:
        return self.client.post(f"/api/admin/accounts/{username}/deactivate")

    def delete_admin_account(self, username: str) -> Response:
        return self.client.delete(f"/api/admin/accounts/{username}")

    def get_admin_account_sessions(self, username: str) -> Response:
        return self.client.get(f"/api/admin/accounts/{username}/sessions")

    def post_revoke_admin_account_session(self, username: str, session_id: str) -> Response:
        return self.client.post(f"/api/admin/accounts/{username}/sessions/{session_id}/revoke")

    def post_revoke_all_admin_account_sessions(self, username: str) -> Response:
        return self.client.post(f"/api/admin/accounts/{username}/sessions/revoke-all")

    def post_revoke_other_admin_account_sessions(self, username: str) -> Response:
        return self.client.post(f"/api/admin/accounts/{username}/sessions/revoke-others")

    def put_update_article(
        self,
        slug: str,
        data: dict[str, Any],
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.put(f"/api/admin/articles/detail/{slug}", params=params, json=data)

    def delete_article(self, slug: str) -> Response:
        return self.client.delete(f"/api/admin/articles/detail/{slug}")

    def post_set_draft_status_to_article(self, slug: str) -> Response:
        return self.client.post(f"/api/admin/articles/detail/{slug}/set-draft")

    def post_set_published_status_to_article(self, slug: str) -> Response:
        return self.client.post(f"/api/admin/articles/detail/{slug}/set-published")

    def get_tags(
        self,
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.get("/api/articles/tags", params=params)

    def get_admin_tags(
        self,
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.get("/api/admin/articles/tags", params=params)

    def get_search_tags(
        self,
        search_name: str,
        limit: int | None = 10,
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str | int] = {"searchName": search_name}
        if language is not None:
            params["language"] = language
        if limit is not None:
            params["limit"] = limit
        return self.client.get("/api/admin/articles/tags/search", params=params)

    def post_create_tag(self, data: dict[str, Any], language: str | None = "ru") -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.post("/api/admin/articles/tags", params=params, json=data)

    def put_update_tag(
        self,
        tag_id: str,
        data: dict[str, Any],
        language: str | None = "ru",
    ) -> Response:
        params: dict[str, str] = {}
        if language is not None:
            params["language"] = language
        return self.client.put(f"/api/admin/articles/tags/{tag_id}", params=params, json=data)

    def delete_tag(self, tag_id: str) -> Response:
        return self.client.delete(f"/api/admin/articles/tags/{tag_id}")

    def post_create_contact_me_request(self, data: dict[str, Any]) -> Response:
        return self.client.post("/api/contacts", json=data)

    def post_admin_file(
        self,
        *,
        purpose: str,
        name: str,
        filename: str,
        content: bytes,
        content_type: str,
    ) -> Response:
        return self.client.post(
            "/api/admin/files",
            data={"purpose": purpose, "name": name},
            files={"file": (filename, content, content_type)},
        )

    def get_admin_files(self, *, purpose: str) -> Response:
        return self.client.get(
            "/api/admin/files",
            params={"purpose": purpose},
        )

    def get_admin_file(self, *, file_id: str) -> Response:
        return self.client.get(f"/api/admin/files/{file_id}")

    def put_admin_file(self, *, file_id: str, name: str) -> Response:
        return self.client.put(
            f"/api/admin/files/{file_id}",
            json={"name": name},
        )

    def delete_admin_file(self, *, file_id: str) -> Response:
        return self.client.delete(f"/api/admin/files/{file_id}")

    def post_login(
        self,
        data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> Response:
        return self.client.post("/api/auth/login", json=data, headers=headers)

    def post_refresh(
        self,
        *,
        cookies: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        csrf_guard: bool = True,
    ) -> Response:
        request_headers = dict(headers or {})
        if csrf_guard:
            request_headers["X-CSRF-Guard"] = "1"
        return self.client.post(
            "/api/auth/refresh",
            headers=self._headers_with_cookies(headers=request_headers, cookies=cookies),
        )

    def post_logout(
        self,
        *,
        cookies: dict[str, str] | None = None,
        csrf_guard: bool = True,
    ) -> Response:
        headers: dict[str, str] = {}
        if csrf_guard:
            headers["X-CSRF-Guard"] = "1"
        return self.client.post(
            "/api/auth/logout",
            headers=self._headers_with_cookies(headers=headers, cookies=cookies),
        )

    def get_get_base_current_user_account(self) -> Response:
        return self.client.get("/api/account/base")
