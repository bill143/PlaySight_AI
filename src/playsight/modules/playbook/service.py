"""Playbook service: play CRUD, version history, tag search, clip links."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from playsight.core.errors import NotFoundError
from playsight.db.models import MatchEvent, Player
from playsight.modules.playbook.models import Play, PlayAssignment, PlayClipLink
from playsight.modules.playbook.schemas import (
    AssignmentCreate,
    ClipLinkCreate,
    PlayCreate,
    PlayRevisionCreate,
)


class PlaybookService:
    """Club-scoped play management.

    Versioning: plays are immutable; ``revise_play`` creates a new row with
    ``version + 1`` and ``parent_play_id`` pointing at the revised row.
    Cross-club access surfaces as ``NotFoundError`` (HTTP 404).
    """

    def __init__(self, db: Session) -> None:
        """Bind the service to an open database session."""
        self.db = db

    # -- plays ---------------------------------------------------------------

    def create_play(self, club_id: str, payload: PlayCreate) -> Play:
        """Create version 1 of a new play."""
        play = Play(
            club_id=club_id,
            team_id=payload.team_id,
            category=payload.category.value,
            title=payload.title,
            notes=payload.notes,
            diagram_storage_key=payload.diagram_storage_key,
            version=1,
            parent_play_id=None,
            tags_json=[tag.strip() for tag in payload.tags_json if tag.strip()],
        )
        self.db.add(play)
        self.db.commit()
        self.db.refresh(play)
        return play

    def get_play(self, club_id: str, play_id: str) -> Play:
        """Return one play version, raising ``NotFoundError`` outside the club."""
        play = self.db.get(Play, play_id)
        if play is None or play.club_id != club_id:
            raise NotFoundError(f"Play {play_id} not found.")
        return play

    def list_plays(
        self,
        club_id: str,
        *,
        category: str | None = None,
        team_id: str | None = None,
        tag: str | None = None,
        latest_only: bool = True,
    ) -> list[Play]:
        """List plays with optional category/team/tag filters.

        ``latest_only`` (default) hides superseded versions, i.e. rows that
        another row references as ``parent_play_id``.

        Tag search matches case-insensitively against ``tags_json``.
        # TODO(phase2): replace the in-Python tag filter with an indexed JSON
        # containment query (Postgres GIN) once tag volume warrants it.
        """
        stmt = select(Play).where(Play.club_id == club_id)
        if category is not None:
            stmt = stmt.where(Play.category == category)
        if team_id is not None:
            stmt = stmt.where(Play.team_id == team_id)
        if latest_only:
            superseded = select(Play.parent_play_id).where(
                Play.club_id == club_id, Play.parent_play_id.is_not(None)
            )
            stmt = stmt.where(Play.id.not_in(superseded))
        stmt = stmt.order_by(Play.title, Play.version)
        plays = list(self.db.scalars(stmt))
        if tag is not None:
            needle = tag.strip().lower()
            plays = [
                play
                for play in plays
                if needle in {str(item).lower() for item in (play.tags_json or [])}
            ]
        return plays

    def revise_play(self, club_id: str, play_id: str, payload: PlayRevisionCreate) -> Play:
        """Create a new version of a play; unset fields inherit from the parent."""
        parent = self.get_play(club_id, play_id)
        data = payload.model_dump(exclude_unset=True)
        category = data.get("category")
        revision = Play(
            club_id=club_id,
            team_id=data.get("team_id", parent.team_id),
            category=category.value if category is not None else parent.category,
            title=data.get("title") or parent.title,
            notes=data.get("notes", parent.notes),
            diagram_storage_key=data.get("diagram_storage_key", parent.diagram_storage_key),
            version=parent.version + 1,
            parent_play_id=parent.id,
            tags_json=data.get("tags_json", list(parent.tags_json or [])),
        )
        self.db.add(revision)
        self.db.commit()
        self.db.refresh(revision)
        return revision

    def list_versions(self, club_id: str, play_id: str) -> list[Play]:
        """Return the full version history of a play, oldest first."""
        play = self.get_play(club_id, play_id)
        root = play
        while root.parent_play_id is not None:
            parent = self.db.get(Play, root.parent_play_id)
            if parent is None or parent.club_id != club_id:
                break
            root = parent
        versions: list[Play] = [root]
        frontier: list[str] = [root.id]
        while frontier:
            children = list(
                self.db.scalars(
                    select(Play).where(Play.club_id == club_id, Play.parent_play_id.in_(frontier))
                )
            )
            versions.extend(children)
            frontier = [child.id for child in children]
        return sorted(versions, key=lambda item: item.version)

    def delete_play(self, club_id: str, play_id: str) -> None:
        """Delete one play version with its assignments and clip links."""
        play = self.get_play(club_id, play_id)
        self.db.execute(delete(PlayAssignment).where(PlayAssignment.play_id == play.id))
        self.db.execute(delete(PlayClipLink).where(PlayClipLink.play_id == play.id))
        self.db.delete(play)
        self.db.commit()

    # -- assignments -----------------------------------------------------------

    def add_assignment(
        self, club_id: str, play_id: str, payload: AssignmentCreate
    ) -> PlayAssignment:
        """Attach a role/player responsibility to a play."""
        play = self.get_play(club_id, play_id)
        if payload.player_id is not None:
            player = self.db.get(Player, payload.player_id)
            if player is None or player.club_id != club_id:
                raise NotFoundError(f"Player {payload.player_id} not found.")
        assignment = PlayAssignment(
            club_id=club_id,
            play_id=play.id,
            player_id=payload.player_id,
            role=payload.role,
            instructions=payload.instructions,
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def list_assignments(self, club_id: str, play_id: str) -> list[PlayAssignment]:
        """List the assignments of a play."""
        play = self.get_play(club_id, play_id)
        stmt = (
            select(PlayAssignment)
            .where(PlayAssignment.club_id == club_id, PlayAssignment.play_id == play.id)
            .order_by(PlayAssignment.created_at)
        )
        return list(self.db.scalars(stmt))

    def remove_assignment(self, club_id: str, assignment_id: str) -> None:
        """Remove one assignment."""
        assignment = self.db.get(PlayAssignment, assignment_id)
        if assignment is None or assignment.club_id != club_id:
            raise NotFoundError(f"Play assignment {assignment_id} not found.")
        self.db.delete(assignment)
        self.db.commit()

    # -- clip links --------------------------------------------------------------

    def add_clip_link(self, club_id: str, play_id: str, payload: ClipLinkCreate) -> PlayClipLink:
        """Link a play to a detected match event (validated within the club)."""
        play = self.get_play(club_id, play_id)
        event = self.db.get(MatchEvent, payload.match_event_id)
        if event is None or event.club_id != club_id:
            raise NotFoundError(f"Match event {payload.match_event_id} not found.")
        link = PlayClipLink(
            club_id=club_id,
            play_id=play.id,
            match_event_id=event.id,
            note=payload.note,
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return link

    def list_clip_links(self, club_id: str, play_id: str) -> list[PlayClipLink]:
        """List the clip links of a play."""
        play = self.get_play(club_id, play_id)
        stmt = (
            select(PlayClipLink)
            .where(PlayClipLink.club_id == club_id, PlayClipLink.play_id == play.id)
            .order_by(PlayClipLink.created_at)
        )
        return list(self.db.scalars(stmt))

    def remove_clip_link(self, club_id: str, link_id: str) -> None:
        """Remove one clip link."""
        link = self.db.get(PlayClipLink, link_id)
        if link is None or link.club_id != club_id:
            raise NotFoundError(f"Play clip link {link_id} not found.")
        self.db.delete(link)
        self.db.commit()

    # -- Phase 2 stubs -------------------------------------------------------------

    def suggest_clips(self, club_id: str, play_id: str, *, limit: int = 5) -> list[dict]:
        """Suggest match events that could illustrate a play.

        # TODO(phase2): rank ``match_events`` by category affinity (e.g.
        # set_piece plays vs shot_attempt/scoring_event spans) and confidence,
        # then propose the top candidates as clip links.
        """
        raise NotImplementedError(
            "TODO(phase2): clip suggestions are not implemented yet (see docs/ROADMAP.md)."
        )
