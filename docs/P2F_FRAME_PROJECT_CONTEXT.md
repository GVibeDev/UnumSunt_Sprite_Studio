# P2-F — Frame & Project Context

Status: implementation candidate pending Windows/manual validation.

## Purpose

P2-F connects the persistent CREATE shell to the actual decoded frame context instead of leaving current frame, production selection and onion presentation fragmented across legacy workspaces.

The milestone does **not** change the project document schema and does not make the shared canvas an edit owner.

## Runtime ownership

- `VideoSource` remains owner of source metadata, decoding and frame cache.
- `ProjectStore` remains the only persisted project authority.
- `ProjectSession.project_state` owns transient source/current-frame/selected-frame identity.
- `CreateFrameContext` is an immutable presentation snapshot combining runtime frame identity with `VideoSource` timing/count metadata for the CREATE UI.
- `CreateFrameStrip` is a persistent UI control; it does not decode frames or persist project data.

## Frame strip

CREATE now exposes one persistent frame strip below the central workspace. It remains present while routes change.

The strip provides:

- previous / next frame navigation;
- direct frame index navigation;
- a virtualized horizontal frame list;
- current-frame marker;
- production-selection marker;
- explicit add/remove-current selection actions;
- Ctrl-click selection toggle;
- Shift-click range addition;
- source/frame/selection/time orientation;
- explicit onion mode: Off / Previous / Next.

Normal frame clicks change the current frame without silently replacing the production selection.

## Project/context synchronization

Opening a decoded video or imported frame sequence now publishes a `SourceRef` into `ProjectSession`. Every current-frame change and production-selection change is mirrored into `ProjectState` and reflected by the CREATE breadcrumb/frame strip.

The breadcrumb can now include the active source filename and current frame when no more specific asset id is available:

`CHARACTER → ANIMATION → DIRECTION → SPRITE / FRAME`

No source pixel data or duplicated project JSON is stored in `ProjectState`.

## Onion skin

P2-F freezes a deliberately explicit single-neighbour policy because the P2-E renderer currently exposes one onion layer:

- Off
- Previous
- Next

The onion frame uses the same existing RGBA override path when available and otherwise the same chroma-key implementation as the current pipeline. It is presentation-only and does not create an onion-specific project state or edit buffer.

Boundary behaviour is deterministic: Previous at frame 0 and Next at the final frame display no onion layer.

## Performance boundary

The frame strip is list-model based and does not eagerly decode thumbnails for every frame. Thumbnail timeline rendering remains a later UI enhancement if it proves useful. This keeps P2-F independent of source length and avoids doing image work simply to navigate the frame list.

## Compatibility

P2-F preserves the legacy extraction timeline and selection controls while making CREATE the shared context surface. Existing cleanup, alignment, smart-selection and export code continues to receive the same selected-frame list.

No changes are made to `ProjectStore` schema/version fields.

## Acceptance

P2-F is valid when all of the following hold on Windows:

1. opening video or an imported sequence populates the CREATE frame strip;
2. changing frame from the strip changes the legacy pipeline/current canvas frame and vice versa;
3. normal strip clicks move current frame without erasing the production selection;
4. Ctrl-click / Shift-click and +/- Select update the same selection used by Cleanup/Alignment/Smart Selection/Export;
5. breadcrumb shows the real Subject/Animation/Direction context plus current source/frame when available;
6. Onion Off / Previous / Next shows the correct adjacent processed frame without mutating project content;
7. source/group changes clear stale frame/selection/onion context;
8. route and macro-environment changes preserve the persistent frame context when the source remains valid;
9. all regression tests pass;
10. no project-schema migration is generated.
