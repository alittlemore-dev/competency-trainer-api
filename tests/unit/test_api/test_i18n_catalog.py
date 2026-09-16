from core.articles.enums import ArticleReactionKind, ArticleViewSourceCategory
from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum
from core.identity import RoleEnum
from entrypoints.litestar.api.i18n.catalog import get_i18n_messages


class TestI18nCatalog:
    def test_all_supported_languages_have_same_keys(self) -> None:
        russian_keys = set(get_i18n_messages(language=LanguageEnum.RU))
        english_keys = set(get_i18n_messages(language=LanguageEnum.EN))

        assert english_keys == russian_keys

    def test_all_translatable_enum_values_have_labels(self) -> None:
        for language in LanguageEnum:
            messages = get_i18n_messages(language=language)

            for status in PublishStatusEnum:
                assert f"enum.publishStatus.{status.value}" in messages
            for grade in GradeEnum:
                assert f"enum.grade.{grade.name.title().replace('_', '')}" in messages
            for frequency in InterviewFrequencyEnum:
                assert f"enum.interviewFrequency.{frequency.value}" in messages
            for role in RoleEnum:
                assert f"enum.role.{role.value}" in messages
            for reaction in ArticleReactionKind:
                assert f"enum.articleReaction.{reaction.value}" in messages
            for source in ArticleViewSourceCategory:
                assert f"enum.articleViewSource.{source.value}" in messages

    def test_date_picker_catalog_has_accessible_dialog_labels(self) -> None:
        russian_messages = get_i18n_messages(language=LanguageEnum.RU)
        english_messages = get_i18n_messages(language=LanguageEnum.EN)
        transactional_keys = {
            "shared.datePicker.cancel",
            "shared.datePicker.done",
            "shared.datePicker.today",
            "shared.datePicker.selectDate",
            "shared.datePicker.unavailableDate",
        }

        assert transactional_keys <= russian_messages.keys()
        assert transactional_keys <= english_messages.keys()

        assert russian_messages["shared.datePicker.dialog"] == "Выбор даты"
        assert russian_messages["shared.datePicker.change"] == "Изменить дату"
        assert russian_messages["shared.datePicker.openMonthYearPicker"] == "Выбрать месяц и год"
        assert russian_messages["shared.datePicker.previousYear"] == "Предыдущий год"
        assert russian_messages["shared.datePicker.nextYear"] == "Следующий год"
        assert russian_messages["shared.datePicker.clear"] == "Очистить"
        assert russian_messages["shared.datePicker.close"] == "Закрыть"
        assert russian_messages["shared.datePicker.formatHint"] == "Формат даты: ДД.ММ.ГГГГ"
        assert russian_messages["shared.datePicker.requiredDate"] == "Укажите дату."
        assert english_messages["shared.datePicker.dialog"] == "Choose date"
        assert english_messages["shared.datePicker.change"] == "Change date"
        assert english_messages["shared.datePicker.openMonthYearPicker"] == "Choose month and year"
        assert english_messages["shared.datePicker.previousYear"] == "Previous year"
        assert english_messages["shared.datePicker.nextYear"] == "Next year"
        assert english_messages["shared.datePicker.clear"] == "Clear"
        assert english_messages["shared.datePicker.close"] == "Close"
        assert english_messages["shared.datePicker.formatHint"] == "Date format: MM/DD/YYYY"
        assert english_messages["shared.datePicker.requiredDate"] == "Enter a date."

    def test_article_cover_file_picker_catalog_is_fully_localized(self) -> None:
        russian_messages = get_i18n_messages(language=LanguageEnum.RU)
        english_messages = get_i18n_messages(language=LanguageEnum.EN)

        assert russian_messages["articles.form.coverImageChooseFile"] == "Выбрать файл"
        assert russian_messages["articles.form.coverImageNoFileSelected"] == "Файл не выбран"
        assert english_messages["articles.form.coverImageChooseFile"] == "Choose file"
        assert english_messages["articles.form.coverImageNoFileSelected"] == "No file selected"

    def test_markdown_editor_catalog_is_fully_localized(self) -> None:
        russian_messages = get_i18n_messages(language=LanguageEnum.RU)
        english_messages = get_i18n_messages(language=LanguageEnum.EN)
        required_keys = {
            "markdownEditor.mode.aria",
            "markdownEditor.mode.edit",
            "markdownEditor.mode.source",
            "markdownEditor.mode.preview",
            "markdownEditor.fullscreen.enter",
            "markdownEditor.fullscreen.exit",
            "markdownEditor.toolbar.aria",
            "markdownEditor.preview.empty",
            "markdownEditor.preview.imageFailed",
            "markdownEditor.shortcuts.summary",
            "markdownEditor.shortcuts.tabEscape",
            "markdownEditor.shortcuts.modifierHintMac",
            "markdownEditor.shortcuts.modifierHintOther",
            "markdownEditor.shortcuts.group.view",
            "markdownEditor.shortcuts.group.headings",
            "markdownEditor.shortcuts.group.inline",
            "markdownEditor.shortcuts.group.blocks",
            "markdownEditor.shortcuts.group.media",
            "markdownEditor.upload.uploading",
            "markdownEditor.upload.failed",
            "markdownEditor.upload.unsupported",
            "markdownEditor.upload.retry",
            "markdownEditor.upload.dismiss",
            "markdownEditor.search.find",
            "markdownEditor.search.replace",
            "markdownEditor.search.next",
            "markdownEditor.search.previous",
            "markdownEditor.search.all",
            "markdownEditor.search.matchCase",
            "markdownEditor.search.regexp",
            "markdownEditor.search.byWord",
            "markdownEditor.search.replaceAll",
            "markdownEditor.search.close",
            "markdownEditor.search.goToLine",
            "markdownEditor.search.go",
            "markdownEditor.search.currentMatch",
            "markdownEditor.search.onLine",
            "markdownEditor.search.replacedMatches",
            "markdownEditor.search.replacedMatchOnLine",
            "markdownEditor.command.togglePreview",
            "markdownEditor.command.toggleSource",
            "markdownEditor.command.heading1",
            "markdownEditor.command.heading2",
            "markdownEditor.command.heading3",
            "markdownEditor.command.heading4",
            "markdownEditor.command.heading5",
            "markdownEditor.command.heading6",
            "markdownEditor.command.bold",
            "markdownEditor.command.italic",
            "markdownEditor.command.strikethrough",
            "markdownEditor.command.quote",
            "markdownEditor.command.unorderedList",
            "markdownEditor.command.orderedList",
            "markdownEditor.command.taskList",
            "markdownEditor.command.horizontalRule",
            "markdownEditor.command.link",
            "markdownEditor.command.image",
            "markdownEditor.command.inlineCode",
            "markdownEditor.command.codeBlock",
            "markdownEditor.command.table",
            "markdownEditor.command.search",
            "markdownEditor.table.table",
            "markdownEditor.table.row",
            "markdownEditor.table.column",
            "markdownEditor.table.range",
            "markdownEditor.table.menu",
            "markdownEditor.table.addRow",
            "markdownEditor.table.addColumn",
            "markdownEditor.table.moveRow",
            "markdownEditor.table.moveColumn",
            "markdownEditor.table.insertBefore",
            "markdownEditor.table.insertAfter",
            "markdownEditor.table.duplicate",
            "markdownEditor.table.clear",
            "markdownEditor.table.copy",
            "markdownEditor.table.cut",
            "markdownEditor.table.delete",
            "markdownEditor.table.moveBefore",
            "markdownEditor.table.moveAfter",
            "markdownEditor.table.sortAscending",
            "markdownEditor.table.sortDescending",
            "markdownEditor.table.alignLeft",
            "markdownEditor.table.alignCenter",
            "markdownEditor.table.alignRight",
            "markdownEditor.table.format",
            "markdownEditor.table.deleteTable",
            "markdownEditor.table.clipboardFailed",
        }

        assert required_keys <= russian_messages.keys()
        assert required_keys <= english_messages.keys()
        removed_table_keys = {
            "markdownEditor.table.selectRow",
            "markdownEditor.table.selectColumn",
            "markdownEditor.table.selectedRows",
            "markdownEditor.table.selectedColumns",
        }
        assert removed_table_keys.isdisjoint(russian_messages.keys())
        assert removed_table_keys.isdisjoint(english_messages.keys())
        assert "Escape" in russian_messages["markdownEditor.shortcuts.tabEscape"]
        assert "Tab" in english_messages["markdownEditor.shortcuts.tabEscape"]
        assert "⌘" in russian_messages["markdownEditor.shortcuts.modifierHintMac"]
        assert "⌘" in english_messages["markdownEditor.shortcuts.modifierHintMac"]
        assert "keyboard trap" not in russian_messages["markdownEditor.shortcuts.tabEscape"]
        assert (
            russian_messages["markdownEditor.shortcuts.modifierHintOther"]
            == "На Windows и Linux основная клавиша сочетаний — Ctrl."
        )

    def test_shell_catalog_keeps_footer_contact_without_about_navigation(self) -> None:
        russian_messages = get_i18n_messages(language=LanguageEnum.RU)
        english_messages = get_i18n_messages(language=LanguageEnum.EN)

        assert "shell.nav.about" not in russian_messages
        assert "shell.nav.about" not in english_messages
        assert not any(key.startswith("about.") for key in russian_messages)
        assert not any(key.startswith("about.") for key in english_messages)
        assert russian_messages["shell.footer.email"] == "Эл. почта"
        assert english_messages["shell.footer.email"] == "Email"

    def test_admin_panel_navigation_item_labels_omit_repeated_section_domain(self) -> None:
        russian_messages = get_i18n_messages(language=LanguageEnum.RU)
        english_messages = get_i18n_messages(language=LanguageEnum.EN)

        assert russian_messages["adminPanel.section.articleFolders"] == "Папки"
        assert russian_messages["adminPanel.section.articleTags"] == "Теги"
        assert russian_messages["adminPanel.section.matrixQuestions"] == "Вопросы"
        assert russian_messages["adminPanel.section.matrixStructure"] == "Структура"
        assert russian_messages["adminPanel.section.matrixQuestionQueue"] == "Очередь вопросов"
        assert english_messages["adminPanel.section.articleFolders"] == "Folders"
        assert english_messages["adminPanel.section.articleTags"] == "Tags"
        assert english_messages["adminPanel.section.matrixQuestions"] == "Questions"
        assert english_messages["adminPanel.section.matrixStructure"] == "Structure"
        assert english_messages["adminPanel.section.matrixQuestionQueue"] == "Question queue"

    def test_matrix_draft_blocker_summary_labels_fit_the_summary_card(self) -> None:
        russian_messages = get_i18n_messages(language=LanguageEnum.RU)
        english_messages = get_i18n_messages(language=LanguageEnum.EN)

        assert russian_messages["adminMatrixWorkspace.missingDraft"] == "Черновики с блокерами"
        assert english_messages["adminMatrixWorkspace.missingDraft"] == "Drafts with blockers"

    def test_matrix_interview_answer_explanation_labels_describe_an_explanation(self) -> None:
        russian_messages = get_i18n_messages(language=LanguageEnum.RU)
        english_messages = get_i18n_messages(language=LanguageEnum.EN)

        assert (
            russian_messages["matrix.readiness.field.interviewAnswerExplanationRu"]
            == "Объяснение ответа на собеседовании RU"
        )
        assert (
            russian_messages["matrix.readiness.field.interviewAnswerExplanationEn"]
            == "Объяснение ответа на собеседовании EN"
        )
        assert russian_messages["matrix.form.interviewAnswerExplanationRu"] == (
            "Объяснение ответа на собеседовании RU"
        )
        assert russian_messages["matrix.form.interviewAnswerExplanationEn"] == (
            "Объяснение ответа на собеседовании EN"
        )
        assert russian_messages["matrix.form.interviewAnswerExplanationHint"] == (
            "Объясните, зачем задают вопрос, какой ответ ожидается и почему, а также "
            "какие ошибки часто допускают кандидаты."
        )
        assert russian_messages["matrix.detail.interviewAnswerExplanation"] == (
            "Объяснение ответа на собеседовании:"
        )
        assert (
            english_messages["matrix.readiness.field.interviewAnswerExplanationRu"]
            == "Interview answer explanation RU"
        )
        assert (
            english_messages["matrix.readiness.field.interviewAnswerExplanationEn"]
            == "Interview answer explanation EN"
        )
        assert english_messages["matrix.form.interviewAnswerExplanationRu"] == (
            "Interview answer explanation RU"
        )
        assert english_messages["matrix.form.interviewAnswerExplanationEn"] == (
            "Interview answer explanation EN"
        )
        assert english_messages["matrix.form.interviewAnswerExplanationHint"] == (
            "Explain why the question is asked, what answer is expected and why, and which "
            "mistakes candidates commonly make."
        )
        assert english_messages["matrix.detail.interviewAnswerExplanation"] == (
            "Interview answer explanation:"
        )

    def test_site_build_case_study_catalog_describes_public_engineering_page(self) -> None:
        russian_messages = get_i18n_messages(language=LanguageEnum.RU)
        english_messages = get_i18n_messages(language=LanguageEnum.EN)
        russian_quality_body = russian_messages["siteBuild.quality.body"]
        english_quality_body = english_messages["siteBuild.quality.body"]

        assert russian_messages["shell.footer.siteBuild"] == "Как устроен сайт"
        assert english_messages["shell.footer.siteBuild"] == "How this site is built"
        assert "инженерный разбор" in russian_messages["siteBuild.hero.lead"].lower()
        assert "engineering case study" in english_messages["siteBuild.hero.lead"].lower()
        assert "портфолио" in russian_messages["siteBuild.hero.lead"].lower()
        assert "portfolio" in english_messages["siteBuild.hero.lead"].lower()
        assert "Litestar" in russian_messages["siteBuild.architecture.backendBody"]
        assert "Angular" in english_messages["siteBuild.architecture.frontendBody"]
        assert "самовосстанавливается" in russian_messages["siteBuild.architecture.infraBody"]
        assert "self-recovers" in english_messages["siteBuild.architecture.infraBody"]
        assert "семиднев" not in russian_messages["siteBuild.architecture.infraBody"]
        assert "seven-day" not in english_messages["siteBuild.architecture.infraBody"]
        russian_agent_body = russian_messages["siteBuild.architecture.agentBody"]
        english_agent_body = english_messages["siteBuild.architecture.agentBody"]
        assert "ограничен" in russian_agent_body.lower()
        assert "allowlist" in russian_agent_body.lower()
        assert "bounded" in english_agent_body.lower()
        assert "allowlist" in english_agent_body.lower()
        assert "семь" not in russian_agent_body.lower()
        assert "ровно пять" not in russian_agent_body.lower()
        assert "seven" not in english_agent_body.lower()
        assert "exactly five" not in english_agent_body.lower()
        for expected, text in (
            ("SSR", russian_quality_body),
            ("SSR", english_quality_body),
            ("производительность", russian_quality_body),
            ("performance", english_quality_body),
            ("security", english_quality_body),
            ("безопасность", russian_quality_body),
            ("SQL-планы", russian_quality_body),
            ("SQL plans", english_quality_body),
            ("blue/green", russian_quality_body),
            ("blue/green", english_quality_body),
        ):
            assert expected in text
        assert "наблюдаемостью" in russian_messages["siteBuild.next.body"]
        assert "observability" in english_messages["siteBuild.next.body"]
        assert "release process" in russian_messages["siteBuild.decision.deployManifest"]
        assert "controlled release process" in english_messages["siteBuild.decision.deployManifest"]
        assert "runtime-конфигурация" in russian_messages["siteBuild.decision.deployManifest"]
        assert "собирается из manifest" in russian_messages["siteBuild.decision.deployManifest"]
        assert "runtime configuration" in english_messages["siteBuild.decision.deployManifest"]
        assert "from a manifest" in english_messages["siteBuild.decision.deployManifest"]
        assert "ручное подтверждение" in russian_messages["siteBuild.decision.deployManifest"]
        assert "manual approval" in english_messages["siteBuild.decision.deployManifest"]
        assert "blue/green" in russian_messages["siteBuild.decision.deployManifest"]
        assert "blue/green" in english_messages["siteBuild.decision.deployManifest"]
        for stale_text, text in (
            ("static gates", english_quality_body),
            ("own side", english_quality_body),
            ("guardrails", english_quality_body),
            ("guardrails", russian_quality_body),
            ("production-facing", russian_quality_body),
            ("production-facing", english_quality_body),
            ("слепых зон", russian_quality_body),
            ("blind spots", english_quality_body),
            ("server-side session cookie", english_quality_body),
            ("raw user agents", english_quality_body),
            ("Dockerfile lint", english_quality_body),
            ("Trivy config scan", english_quality_body),
            ("per-image Docker build/image scans", english_quality_body),
            ("shared CI graph", english_quality_body),
            ("SSR/Lighthouse", english_quality_body),
            ("SSR/Lighthouse", russian_quality_body),
            ("performance budgets", english_quality_body),
        ):
            assert stale_text not in text
        assert "performance budgets" not in english_messages["siteBuild.next.body"]
        assert "changelog" not in english_messages["siteBuild.next.body"].lower()
        assert "changelog" not in russian_messages["siteBuild.next.body"].lower()

    def test_updates_catalog_describes_public_updates_page(self) -> None:
        russian_messages = get_i18n_messages(language=LanguageEnum.RU)
        english_messages = get_i18n_messages(language=LanguageEnum.EN)

        assert russian_messages["shell.footer.updates"] == "Обновления"
        assert english_messages["shell.footer.updates"] == "Updates"
        assert "публичный журнал" in russian_messages["updates.seo.description"].lower()
        assert "public changelog" in english_messages["updates.seo.description"].lower()
        assert "Major changes" in english_messages["updates.hero.lead"]
        assert "месяцам" in russian_messages["updates.hero.lead"]
        assert russian_messages["updates.tag.backend"] == "Backend"
        assert english_messages["updates.tag.backend"] == "Backend"
        assert russian_messages["updates.tag.delivery"] == "Доставка"
        assert english_messages["updates.tag.delivery"] == "Delivery"
        assert not any(key.startswith("updates.month.") for key in russian_messages)
        assert not any(key.startswith("updates.month.") for key in english_messages)
        assert not any(key.startswith("updates.entry.") for key in russian_messages)
        assert not any(key.startswith("updates.entry.") for key in english_messages)
        assert "выдум" not in russian_messages["updates.hero.lead"].lower()
        assert "точност" not in russian_messages["updates.hero.lead"].lower()
