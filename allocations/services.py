"""Allocation business logic (SAD 3.1: every change to an allocation goes through here so history cannot be skipped)."""

import logging

from django.db import transaction
from django.utils import timezone

from django.contrib.auth import get_user_model

from rooms.models import Room

from .models import Allocation, AllocationHistory

logger = logging.getLogger(__name__)


class InvalidStateError(Exception):
    """The allocation is not in a state that allows the requested action (SAD 3.4)."""


class RoomFullError(Exception):
    """The room has no free bed (HMS-F-011, SAD 3.4)."""


class AlreadyAllocatedError(Exception):
    """The student already holds an ACTIVE allocation (SAD 3.1)."""


def _lock_room_with_free_bed(room):
    # Lock the room row, then count ACTIVE allocations, so two requests for the last bed cannot both pass.
    locked = Room.objects.select_for_update().get(pk=room.pk)
    if locked.allocations.filter(status=Allocation.ACTIVE).count() >= locked.capacity:
        raise RoomFullError("Room has reached its capacity")
    return locked


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


@transaction.atomic
def allocate_room(student, room, by):
    """HMS-F-010 / F-011: give `student` (a User) a bed in `room`. Capacity check and insert are one transaction."""
    # Lock the student's user row too, so two admins cannot give the same student two rooms at once.
    get_user_model().objects.select_for_update().get(pk=student.pk)
    if Allocation.objects.filter(student=student, status=Allocation.ACTIVE).exists():
        raise AlreadyAllocatedError("Student already has an active allocation")
    locked_room = _lock_room_with_free_bed(room)
    allocation = Allocation.objects.create(student=student, room=locked_room)
    AllocationHistory.objects.create(
        allocation=allocation,
        action=AllocationHistory.CREATED,
        performed_by=by,
        new_room=locked_room,
    )
    logger.info(
        "Allocation %s created in room %s for user %s by user %s",
        allocation.pk, locked_room.pk, student.pk, by.pk,
    )
    return allocation


@transaction.atomic
def modify_allocation(allocation, new_room, by):
    """HMS-F-013: move an ACTIVE allocation to another room that has a free bed. Status stays ACTIVE."""
    locked = _lock(allocation)
    if locked.status != Allocation.ACTIVE:
        raise InvalidStateError("Allocation is not active")
    if locked.room_id == new_room.pk:
        raise InvalidStateError("Student is already in this room")
    target = _lock_room_with_free_bed(new_room)
    old_room_id = locked.room_id
    locked.room = target
    locked.save(update_fields=["room"])
    AllocationHistory.objects.create(
        allocation=locked,
        action=AllocationHistory.MODIFIED,
        performed_by=by,
        old_room_id=old_room_id,
        new_room=target,
    )
    logger.info(
        "Allocation %s moved from room %s to room %s by user %s", locked.pk, old_room_id, target.pk, by.pk
    )
    allocation.room = target
    return allocation


@transaction.atomic
def cancel_allocation(allocation, by):
    """HMS-F-014: cancel an ACTIVE allocation. The row is kept (ADR-06); the bed is freed by the status change."""
    locked = _lock(allocation)
    if locked.status != Allocation.ACTIVE:
        raise InvalidStateError("Allocation is not active")
    locked.status = Allocation.CANCELLED
    locked.save(update_fields=["status"])
    AllocationHistory.objects.create(
        allocation=locked,
        action=AllocationHistory.CANCELLED,
        performed_by=by,
        old_room_id=locked.room_id,
    )
    logger.info("Allocation %s cancelled by user %s", locked.pk, by.pk)
    allocation.status = locked.status
