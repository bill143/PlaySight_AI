"""Notification backends (CONTRACTS.md section 13).

Phase 1 ships :class:`LogNotifier` (structured log lines). Email and push are
Phase 2 stubs behind the same :class:`Notifier` protocol.
"""

from playsight.integrations.notifications.base import Notifier, notify
from playsight.integrations.notifications.email import EmailNotifier
from playsight.integrations.notifications.factory import get_notifier
from playsight.integrations.notifications.log import LogNotifier
from playsight.integrations.notifications.push import PushNotifier

__all__ = [
    "EmailNotifier",
    "LogNotifier",
    "Notifier",
    "PushNotifier",
    "get_notifier",
    "notify",
]
