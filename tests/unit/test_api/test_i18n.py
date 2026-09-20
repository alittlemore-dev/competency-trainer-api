from string import Formatter

from httpx import codes

from tests.test_cases import ApiTestCase

ACCOUNT_MESSAGE_KEYS = {
    "shell.account.profile",
    "shared.unsavedChanges.confirmDiscard",
    "account.title",
    "account.navigation",
    "account.profile.title",
    "account.profile.edit",
    "account.profile.fullName",
    "account.profile.firstName",
    "account.profile.lastName",
    "account.profile.middleName",
    "account.profile.gender",
    "account.profile.gender.male",
    "account.profile.gender.female",
    "account.profile.username",
    "account.profile.changeAvatar",
    "account.profile.removeAvatar",
    "account.profile.avatarAlt",
    "account.profile.loading",
    "account.profile.loadFailed",
    "account.profile.retry",
    "account.profile.saveSuccess",
    "account.profile.avatarSaveSuccess",
    "account.profile.saveFailed",
    "account.profile.avatarFailed",
    "account.profile.invalidAvatarType",
    "account.profile.avatarTooLarge",
}


class TestI18nApi(ApiTestCase):
    def test_account_messages_exist_and_match_across_languages(self) -> None:
        russian = self.api.get_i18n_bundle(language="ru").json()["messages"]
        english = self.api.get_i18n_bundle(language="en").json()["messages"]

        assert russian.keys() >= ACCOUNT_MESSAGE_KEYS
        assert english.keys() >= ACCOUNT_MESSAGE_KEYS
        for key in ACCOUNT_MESSAGE_KEYS:
            assert self._placeholders(russian[key]) == self._placeholders(english[key])

        assert russian["shell.account.profile"] == "Профиль"
        assert english["shell.account.profile"] == "Profile"
        assert russian["shared.notSet"] == "Не задано"
        assert english["shared.notSet"] == "Not set"
        assert russian["shared.unsavedChanges.confirmDiscard"] == (
            "Есть несохранённые изменения. Если продолжить, они будут потеряны. Продолжить?"
        )
        assert english["shared.unsavedChanges.confirmDiscard"] == (
            "You have unsaved changes. If you continue, they will be lost. Continue?"
        )

    def test_list_languages(self) -> None:
        response = self.api.get_i18n_languages()

        assert response.status_code == codes.OK, response.content
        assert response.json() == {
            "defaultLanguage": "ru",
            "languages": [
                {"code": "ru", "label": "Русский"},
                {"code": "en", "label": "English"},
            ],
        }

    def test_get_russian_bundle(self) -> None:
        response = self.api.get_i18n_bundle(language="ru")

        assert response.status_code == codes.OK, response.content
        body = response.json()
        assert body["language"] == "ru"
        assert "shell.nav.about" not in body["messages"]
        assert body["messages"]["shell.footer.email"] == "Эл. почта"
        assert body["messages"]["shell.nav.adminPanel"] == "Админ-панель"
        assert body["messages"]["adminPanel.title"] == "Админ-панель"
        assert body["messages"]["enum.publishStatus.Draft"] == "Черновик"
        assert body["messages"]["enum.grade.JuniorPlus"] == "Junior+"
        assert body["messages"]["auth.login.restrictedAccessWarning.title"] == (
            "Пока только для владельца, администраторов и модераторов"
        )

    def test_get_english_bundle(self) -> None:
        response = self.api.get_i18n_bundle(language="en")

        assert response.status_code == codes.OK, response.content
        body = response.json()
        assert body["language"] == "en"
        assert "shell.nav.about" not in body["messages"]
        assert body["messages"]["shell.footer.email"] == "Email"
        assert body["messages"]["shell.nav.adminPanel"] == "Admin panel"
        assert body["messages"]["adminPanel.title"] == "Admin panel"
        assert body["messages"]["enum.publishStatus.Draft"] == "Draft"
        assert body["messages"]["enum.grade.JuniorPlus"] == "Junior+"
        assert (
            body["messages"]["auth.login.restrictedAccessWarning.title"]
            == "Owner, admins, and moderators only for now"
        )

    def test_unknown_bundle_language_is_rejected(self) -> None:
        response = self.api.get_i18n_bundle(language="de")

        assert response.status_code == codes.BAD_REQUEST

    @staticmethod
    def _placeholders(message: str) -> set[str]:
        return {name for _, name, _, _ in Formatter().parse(message) if name is not None}
