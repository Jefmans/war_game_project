from django.utils import timezone

from matches.models import MatchParticipant, Turn


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


def get_participant_index(participants, participant_id):
    for index, participant in enumerate(participants):
        if participant.id == participant_id:
            return index
    return None


def next_turn_for_index(start_turn, index, count):
    if count <= 0:
        return None
    current_mod = (start_turn - 1) % count
    if current_mod <= index:
        delta = index - current_mod
    else:
        delta = count - (current_mod - index)
    return start_turn + delta


def get_active_participant(match, turn_number):
    participants = get_participants(match)
    if not participants:
        return None
    index = (turn_number - 1) % len(participants)
    return participants[index]


def ensure_turn(match, turn_number, active_participant=None):
    turn, created = Turn.objects.get_or_create(
        match=match,
        number=turn_number,
        defaults={"active_participant": active_participant},
    )
    if not created and active_participant and turn.active_participant is None:
        turn.active_participant = active_participant
        turn.save(update_fields=["active_participant"])
    return turn


def get_current_turn(match):
    turn_number = match.last_resolved_turn + 1
    active_participant = get_active_participant(match, turn_number)
    return ensure_turn(match, turn_number, active_participant)
