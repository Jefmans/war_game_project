from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from matches.models import Kingdom, Match, MatchParticipant
from units.models import Unit, UnitType


class Command(BaseCommand):
    help = "Seed a match with participants, kingdoms, unit types, and starter units."

    def add_arguments(self, parser):
        parser.add_argument("--match-id", type=int)
        parser.add_argument("--name", default="Test Match")
        parser.add_argument("--players", type=int, default=2)
        parser.add_argument("--max-players", type=int, default=10)
        parser.add_argument("--turn-length", type=int, default=10800)
        parser.add_argument("--username-prefix", default="player")
        parser.add_argument("--password", default="password123")
        parser.add_argument("--start-now", action="store_true")
        parser.add_argument("--unit-type", default="Infantry")
        parser.add_argument("--move-points", type=int, default=3)
        parser.add_argument("--chunk-q", type=int, default=0)
        parser.add_argument("--chunk-r", type=int, default=0)
        parser.add_argument("--no-chunk", action="store_true")

    def handle(self, *args, **options):
        players = options["players"]
        if players < 1:
            raise CommandError("--players must be at least 1.")

        match = self._get_or_create_match(options)
        if options["start_now"] and match.start_time is None:
            match.start_time = timezone.now()
            match.save(update_fields=["start_time"])

        unit_type = self._get_or_create_unit_type(options)
        participants = self._create_participants(match, options, players)

        self._spawn_units(match, participants, unit_type)

        if not options["no_chunk"]:
            call_command(
                "generate_world",
                match=match.id,
                chunk_q=options["chunk_q"],
                chunk_r=options["chunk_r"],
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded match {match.id} with {len(participants)} participants."
            )
        )

    def _get_or_create_match(self, options):
        match_id = options["match_id"]
        if match_id:
            match = Match.objects.filter(id=match_id).first()
            if not match:
                raise CommandError(f"Match {match_id} not found.")
            return match

        return Match.objects.create(
            name=options["name"],
            max_players=options["max_players"],
            turn_length_seconds=options["turn_length"],
        )

    def _get_or_create_unit_type(self, options):
        unit_type, _ = UnitType.objects.get_or_create(
            name=options["unit_type"],
            defaults={
                "max_hp": 10,
                "attack": 1,
                "defense": 1,
                "move_points": options["move_points"],
            },
        )
        if unit_type.move_points != options["move_points"]:
            unit_type.move_points = options["move_points"]
            unit_type.save(update_fields=["move_points"])
        return unit_type

    def _create_participants(self, match, options, players):
        user_model = get_user_model()
        prefix = options["username_prefix"]
        password = options["password"]
        existing = match.participants.count()
        participants = []

        with transaction.atomic():
            for i in range(players):
                seat_order = existing + i + 1
                username = f"{prefix}{seat_order}"
                user = user_model.objects.filter(username=username).first()
                if not user:
                    user = user_model.objects.create_user(
                        username=username,
                        email=f"{username}@example.com",
                        password=password,
                    )

                kingdom = Kingdom.objects.create(
                    match=match,
                    name=f"{username} Kingdom",
                )

                participant = MatchParticipant.objects.create(
                    match=match,
                    user=user,
                    seat_order=seat_order,
                    kingdom=kingdom,
                )
                participants.append(participant)

        return participants

    def _spawn_units(self, match, participants, unit_type):
        base_q = 5
        base_r = 5
        step = 3

        for index, participant in enumerate(participants):
            q = base_q + index * step
            r = base_r
            Unit.objects.create(
                match=match,
                owner_kingdom=participant.kingdom,
                unit_type=unit_type,
                q=q,
                r=r,
                hp=unit_type.max_hp,
            )
