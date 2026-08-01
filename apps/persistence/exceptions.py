"""Persistence domain exceptions."""


class TenantNotFoundError(Exception):
    pass


class SceneNotFoundError(Exception):
    pass


class DestinationNotFoundError(Exception):
    pass


class ActiveSceneDeleteError(Exception):
    pass


class InvalidCountdownTargetError(Exception):
    pass
