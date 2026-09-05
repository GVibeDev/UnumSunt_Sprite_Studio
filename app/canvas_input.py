from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot
from typing import Protocol, runtime_checkable


class PointerButton(str, Enum):
    NONE = 'none'
    LEFT = 'left'
    RIGHT = 'right'
    MIDDLE = 'middle'
    OTHER = 'other'


class PointerPhase(str, Enum):
    PRESS = 'press'
    MOVE = 'move'
    RELEASE = 'release'
    CANCEL = 'cancel'


class ToolPointerDisposition(str, Enum):
    """Explicit result returned by a tool for one pointer event.

    ``IGNORED`` intentionally does not fall back to neutral canvas behavior.
    ``DELEGATE_NEUTRAL`` is the only way a tool can explicitly hand a newly
    pressed interaction back to the neutral canvas contract.
    """

    HANDLED = 'handled'
    IGNORED = 'ignored'
    DELEGATE_NEUTRAL = 'delegate_neutral'


@dataclass(frozen=True, slots=True)
class CanvasPointerEvent:
    phase: PointerPhase
    x: float
    y: float
    button: PointerButton = PointerButton.NONE
    buttons: frozenset[PointerButton] = frozenset()


@runtime_checkable
class ToolInputTarget(Protocol):
    def handle_pointer_event(self, event: CanvasPointerEvent) -> ToolPointerDisposition:
        ...

    def cancel_pointer_interaction(self) -> None:
        ...


@dataclass(frozen=True, slots=True)
class CanvasInputResult:
    consumed: bool = False
    pan_dx: float = 0.0
    pan_dy: float = 0.0
    request_general_context_menu: bool = False
    tool_disposition: ToolPointerDisposition | None = None
    interaction_started: bool = False
    interaction_ended: bool = False


@dataclass(slots=True)
class _InteractionSession:
    owner: str
    button: PointerButton
    press_x: float
    press_y: float
    last_x: float
    last_y: float
    dragged: bool = False
    tool_id: str | None = None
    tool_target: ToolInputTarget | None = None


class CanvasInputController:
    """Central dispatcher for the CREATE canvas pointer contract.

    P2-C freezes only pointer ownership and the neutral LMB/RMB behavior. Wheel
    semantics, keyboard shortcuts and persistence of tool selection remain open.
    The controller is Qt-independent so the routing contract can be unit-tested
    without a GUI runtime.
    """

    CANVAS_NEUTRAL = 'CANVAS_NEUTRAL'
    TOOL_ACTIVE = 'TOOL_ACTIVE'

    def __init__(self, *, drag_threshold: float = 3.0) -> None:
        threshold = float(drag_threshold)
        if threshold < 0:
            raise ValueError('Drag threshold cannot be negative.')
        self.drag_threshold = threshold
        self._active_tool_id: str | None = None
        self._active_tool_target: ToolInputTarget | None = None
        self._session: _InteractionSession | None = None

    @property
    def mode(self) -> str:
        return self.TOOL_ACTIVE if self._active_tool_target is not None else self.CANVAS_NEUTRAL

    @property
    def active_tool_id(self) -> str | None:
        return self._active_tool_id

    @property
    def has_interaction(self) -> bool:
        return self._session is not None

    def activate_tool(self, tool_id: str, target: ToolInputTarget) -> None:
        normalized = str(tool_id).strip()
        if not normalized:
            raise ValueError('Tool id cannot be empty.')
        if not isinstance(target, ToolInputTarget):
            raise TypeError('Active canvas tool does not implement ToolInputTarget.')
        if self._active_tool_id == normalized and self._active_tool_target is target:
            return
        self.cancel_interaction()
        self._active_tool_id = normalized
        self._active_tool_target = target

    def deactivate_tool(self) -> None:
        self.cancel_interaction()
        self._active_tool_id = None
        self._active_tool_target = None

    def cancel_interaction(self) -> None:
        session = self._session
        self._session = None
        if session is not None and session.owner == 'tool' and session.tool_target is not None:
            session.tool_target.cancel_pointer_interaction()

    def dispatch(self, event: CanvasPointerEvent) -> CanvasInputResult:
        if event.phase == PointerPhase.CANCEL:
            had_session = self._session is not None
            self.cancel_interaction()
            return CanvasInputResult(consumed=had_session, interaction_ended=had_session)

        if event.phase == PointerPhase.PRESS:
            if self._session is not None:
                self.cancel_interaction()
            if self._active_tool_target is not None:
                return self._tool_press(event)
            return self._neutral_press(event)

        session = self._session
        if session is not None:
            if session.owner == 'tool':
                return self._tool_session_event(session, event)
            return self._neutral_session_event(session, event)

        # Tool hover/move events still belong to the active tool. Orphan release
        # events after a cancelled session are intentionally ignored so a tool
        # never receives a release that did not belong to its press session.
        if self._active_tool_target is not None and event.phase == PointerPhase.MOVE:
            disposition = self._active_tool_target.handle_pointer_event(event)
            self._require_disposition(disposition)
            return CanvasInputResult(
                consumed=disposition == ToolPointerDisposition.HANDLED,
                tool_disposition=disposition,
            )

        return CanvasInputResult()

    def _tool_press(self, event: CanvasPointerEvent) -> CanvasInputResult:
        target = self._active_tool_target
        tool_id = self._active_tool_id
        assert target is not None and tool_id is not None
        disposition = target.handle_pointer_event(event)
        self._require_disposition(disposition)
        if disposition == ToolPointerDisposition.DELEGATE_NEUTRAL:
            return self._neutral_press(event)
        self._session = _InteractionSession(
            owner='tool',
            button=event.button,
            press_x=event.x,
            press_y=event.y,
            last_x=event.x,
            last_y=event.y,
            tool_id=tool_id,
            tool_target=target,
        )
        return CanvasInputResult(
            consumed=disposition == ToolPointerDisposition.HANDLED,
            tool_disposition=disposition,
            interaction_started=True,
        )

    def _tool_session_event(
        self,
        session: _InteractionSession,
        event: CanvasPointerEvent,
    ) -> CanvasInputResult:
        target = session.tool_target
        if target is None:
            self._session = None
            return CanvasInputResult(interaction_ended=True)
        disposition = target.handle_pointer_event(event)
        self._require_disposition(disposition)
        ended = event.phase == PointerPhase.RELEASE
        if ended:
            self._session = None
        return CanvasInputResult(
            consumed=disposition == ToolPointerDisposition.HANDLED,
            tool_disposition=disposition,
            interaction_ended=ended,
        )

    def _neutral_press(self, event: CanvasPointerEvent) -> CanvasInputResult:
        if event.button not in {PointerButton.LEFT, PointerButton.RIGHT}:
            return CanvasInputResult()
        self._session = _InteractionSession(
            owner='neutral',
            button=event.button,
            press_x=event.x,
            press_y=event.y,
            last_x=event.x,
            last_y=event.y,
        )
        return CanvasInputResult(consumed=True, interaction_started=True)

    def _neutral_session_event(
        self,
        session: _InteractionSession,
        event: CanvasPointerEvent,
    ) -> CanvasInputResult:
        if event.phase == PointerPhase.MOVE:
            distance = hypot(event.x - session.press_x, event.y - session.press_y)
            if not session.dragged and distance < self.drag_threshold:
                return CanvasInputResult(consumed=True)
            if not session.dragged:
                session.dragged = True
                dx = event.x - session.press_x
                dy = event.y - session.press_y
            else:
                dx = event.x - session.last_x
                dy = event.y - session.last_y
            session.last_x = event.x
            session.last_y = event.y
            if session.button == PointerButton.LEFT:
                return CanvasInputResult(consumed=True, pan_dx=dx, pan_dy=dy)
            return CanvasInputResult(consumed=True)

        if event.phase == PointerPhase.RELEASE:
            self._session = None
            same_button = event.button in {PointerButton.NONE, session.button}
            request_menu = (
                same_button
                and session.button == PointerButton.RIGHT
                and not session.dragged
            )
            return CanvasInputResult(
                consumed=session.button in {PointerButton.LEFT, PointerButton.RIGHT},
                request_general_context_menu=request_menu,
                interaction_ended=True,
            )

        return CanvasInputResult(consumed=True)

    @staticmethod
    def _require_disposition(value: ToolPointerDisposition) -> None:
        if not isinstance(value, ToolPointerDisposition):
            raise TypeError('ToolInputTarget must return ToolPointerDisposition explicitly.')
