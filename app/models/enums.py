from __future__ import annotations

import enum


class AccountType(str, enum.Enum):
    investment = "investment"
    retirement = "retirement"


class AnalysisTrigger(str, enum.Enum):
    scheduled = "scheduled"
    manual = "manual"


class AnalysisStatus(str, enum.Enum):
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
