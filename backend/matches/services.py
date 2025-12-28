from django.utils import timezone

from matches.models import Turn


def get_max_turn(match, now=None, persist=False):
    now = now or timezone.now()
    if match.start_time is None:
        if persist:
            match.start_time = now
            match.save(update_fields=["start_time"])
        base_max = 1
        return _apply_max_turn_override(match, base_max)

    elapsed = (now - match.start_time).total_seconds()
    if elapsed < 0:
        base_max = 1
        return _apply_max_turn_override(match, base_max)

    base_max = int(elapsed // match.turn_length_seconds) + 1
    return _apply_max_turn_override(match, base_max)


def _apply_max_turn_override(match, base_max):
    if match.max_turn_override is None:
        return base_max
    return max(base_max, match.max_turn_override)


def get_participants(match):
    return list(match.participants.order_by("seat_order"))


def get_participant_max_turn(match, participant, now=None, persist=False):
    match_max = get_max_turn(match, now=now, persist=persist)
    if participant.max_turn_override is None:
        return match_max
    return min(match_max, participant.max_turn_override)


def ensure_turn(match, participant, turn_number):
    turn, _ = Turn.objects.get_or_create(
        match=match,
        participant=participant,
        number=turn_number,
    )
    return turn
