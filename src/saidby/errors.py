# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0


class SaidbyError(Exception):
    exit_code = 1
    error_id = "error"


class UsageError(SaidbyError):
    exit_code = 2
    error_id = "usage"


class InputError(SaidbyError):
    exit_code = 3
    error_id = "input"


class ModelUnavailableError(SaidbyError):
    exit_code = 4
    error_id = "model_unavailable"


class ConsentMissingError(SaidbyError):
    exit_code = 5
    error_id = "consent_missing"


class StageError(SaidbyError):
    exit_code = 6
    error_id = "stage_failed"


class LlmUnavailableError(SaidbyError):
    exit_code = 7
    error_id = "llm_unavailable"


class NetworkAttemptError(SaidbyError):
    exit_code = 8
    error_id = "network_attempt"
