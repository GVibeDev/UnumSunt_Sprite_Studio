from __future__ import annotations

from dataclasses import dataclass, field

from app.canvas_layers import CanvasOverlayState, CanvasVisualState


@dataclass(slots=True)
class CreateViewState:
    """Transient visual state for the persistent CREATE workspace."""

    pan_x: float = 0.0
    pan_y: float = 0.0
    zoom: float = 1.0
    left_panel_width: int | None = None
    right_panel_width: int | None = None
    left_panel_collapsed: bool = False
    right_panel_collapsed: bool = False
    left_panel_section: str | None = None
    right_panel_section: str | None = None
    production_section: str = 'Current Workspace'

    def set_view_transform(self, *, pan_x: float, pan_y: float, zoom: float) -> None:
        normalized_zoom = float(zoom)
        if normalized_zoom <= 0:
            raise ValueError('Canvas zoom must be greater than zero.')
        self.pan_x = float(pan_x)
        self.pan_y = float(pan_y)
        self.zoom = normalized_zoom

    def set_panel_widths(self, *, left: int | None = None, right: int | None = None) -> None:
        if left is not None and int(left) <= 0:
            raise ValueError('Left panel width must be positive.')
        if right is not None and int(right) <= 0:
            raise ValueError('Right panel width must be positive.')
        if left is not None:
            self.left_panel_width = int(left)
        if right is not None:
            self.right_panel_width = int(right)


@dataclass(slots=True)
class ToolState:
    """Transient tool selection state. Tool persistence is intentionally open."""

    active_tool_id: str | None = None

    @property
    def has_active_tool(self) -> bool:
        return self.active_tool_id is not None

    def activate(self, tool_id: str) -> None:
        normalized = str(tool_id).strip()
        if not normalized:
            raise ValueError('Tool id cannot be empty.')
        self.active_tool_id = normalized

    def deactivate(self) -> None:
        self.active_tool_id = None


@dataclass(slots=True)
class CreateWorkspaceState:
    """UI-only state container owned by the shared CREATE workspace.

    ``visual`` is the canonical P2-E scene-metadata owner. ``overlays`` remains
    as a compatibility property for the P2-E connectivity/P2-F UI code; it does
    not introduce a second overlay state.
    """

    view: CreateViewState = field(default_factory=CreateViewState)
    tool: ToolState = field(default_factory=ToolState)
    visual: CanvasVisualState = field(default_factory=CanvasVisualState)

    @property
    def overlays(self) -> CanvasOverlayState:
        return self.visual.overlays
