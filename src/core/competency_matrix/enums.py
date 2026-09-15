from enum import StrEnum


class CompetencyMatrixWorkspaceSortEnum(StrEnum):
    GRADE = "grade"
    INTERVIEW_FREQUENCY = "interviewFrequency"
    SECTION = "section"
    SUBSECTION = "subsection"
    NEWEST = "newest"
    OLDEST = "oldest"
    MISSING_FIELDS = "missingFields"
    DANGEROUS_PUBLISHED = "dangerousPublished"


class GradeEnum(StrEnum):
    JUNIOR = "Junior"
    JUNIOR_PLUS = "Junior+"
    MIDDLE = "Middle"
    MIDDLE_PLUS = "Middle+"
    SENIOR = "Senior"


class InterviewFrequencyEnum(StrEnum):
    CONSTANTLY = "constantly"
    OFTEN = "often"
    RARELY = "rarely"
    NEVER_SEEN = "neverSeen"


class QuestionQueueImportIssueCodeEnum(StrEnum):
    QUESTION_NOT_TEXT = "questionNotText"
    QUESTION_BLANK = "questionBlank"
    QUESTION_TOO_LONG = "questionTooLong"
    SHEET_NOT_TEXT = "sheetNotText"
    GRADE_NOT_TEXT = "gradeNotText"
    GRADE_INVALID = "gradeInvalid"
    DUPLICATE_IN_FILE = "duplicateInFile"
    DUPLICATE_IN_QUEUE = "duplicateInQueue"


class QuestionQueueImportIssueSeverityEnum(StrEnum):
    ERROR = "error"
    WARNING = "warning"
