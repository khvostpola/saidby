# SPDX-FileCopyrightText: 2026 the saidby authors
# SPDX-License-Identifier: Apache-2.0


class SaidbyError(Exception):
    exit_code = 1


class UsageError(SaidbyError):
    exit_code = 2


class InputError(SaidbyError):
    exit_code = 3


class ModelUnavailableError(SaidbyError):
    exit_code = 4


class ConsentMissingError(SaidbyError):
    exit_code = 5


class StageError(SaidbyError):
    exit_code = 6


class LlmUnavailableError(SaidbyError):
    exit_code = 7


class NetworkAttemptError(SaidbyError):
    exit_code = 8
