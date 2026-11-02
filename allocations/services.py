"""Allocation business logic (SAD 3.1: every change to an allocation goes through here so history cannot be skipped)."""

import logging

from django.db import transaction
from django.utils import timezone

from .models import Allocation, AllocationHistory

logger = logging.getLogger(__name__)


class InvalidStateError(Exception):
    """The allocation is not in a state that allows the requested action (SAD 3.4)."""


def _lock(allocation):
    # Re-read the row under a lock so two admins clicking at once cannot both pass the state check.
    return Allocation.objects.select_for_update().get(pk=allocation.pk)


@transaction.atomic
def check_in(allocation, by):
    """HMS-F-015: record the check-in time of an ACTIVE allocation that is not yet checked in."""
    locked = _lock(allocation)
    if locked.status != Allocation.ACTIVE:
        raise InvalidStateError("Allocation is not active")
    if locked.checked_in_on is not None:
        raise InvalidStateError("Student is already checked in")
    locked.checked_in_on = timezone.now()
    locked.save(update_fields=["checked_in_on"])
    AllocationHistory.objects.create(
        allocation=locked, action=AllocationHistory.CHECKED_IN, performed_by=by
    )
    logger.info("Allocation %s checked in by user %s", locked.pk, by.pk)
    allocation.checked_in_on = locked.checked_in_on


@transaction.atomic
def check_out(allocation, by):
    """HMS-F-016: close a checked-in allocation as COMPLETED, which frees the bed (SAD Figure 6)."""
    locked = _lock(allocation)
    if locked.status != Allocation.ACTIVE:
        raise InvalidStateError("Allocation is not active")
    if locked.checked_in_on is None:
        raise InvalidStateError("Student is not checked in")
    locked.status = Allocation.COMPLETED
    locked.checked_out_on = timezone.now()
    locked.save(update_fields=["status", "checked_out_on"])
    AllocationHistory.objects.create(
        allocation=locked, action=AllocationHistory.CHECKED_OUT, performed_by=by
    )
    logger.info("Allocation %s checked out by user %s", locked.pk, by.pk)
    allocation.status = locked.status
    allocation.checked_out_on = locked.checked_out_on
