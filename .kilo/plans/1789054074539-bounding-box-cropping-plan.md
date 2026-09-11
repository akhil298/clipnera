# Bounding Box + Smart Aspect-Ratio Cropping Plan

## Summary
Extend the existing pipeline to generate per-frame bounding boxes for important subjects, then produce normalized crop + tracking data for multiple output aspect ratios (9:16, 1:1, 4:5, 16:9). The system already has:
- `backend/content_intelligence/analyzer.py` (FrameAnalyzer using Gemini)
- `backend/content_intelligence/reframing.py` (crop_for_subject + build_crop_tracking)
- `backend/video_processor/ffmpeg_service.py` (FFmpegService)
- `backend/clip_generation/service.py` (ClipService)
- `backend/pipeline/service.py` (PipelineOrchestrator)

The missing piece is: vision model must return bounding boxes (not just text descriptions), and the pipeline must consume those boxes to render final clips per aspect ratio.

## Architecture

```
SOURCE VIDEO
    │
    ├─► AUDIO EXTRACTION (exists)
    ├─► TRANSCRIPTION (exists)
    ├─► TOPIC RESEARCH (exists - ContentIntelligenceService)
    ├─► VISUAL ANALYSIS (exists - FrameAnalyzer.analyze)
    │       └─► [NEW] BOUNDING BOX DETECTION (vision model returns boxes)
    │
    ├─► HIGHLIGHT DETECTION (exists)
    ├─► SCORING (exists)
    ├─► METADATA GENERATION (exists)
    │
    ├─► [NEW] BOUNDING BOX + TRACKING STEP
    │       └─► For each clip, extract frames at intervals
    │       └─► Vision model returns normalized bounding boxes
    │       └─► Generate crop_tracking per aspect ratio
    │
    ├─► CLIP GENERATION (exists)
    │       └─► [NEW] Render each clip in each requested aspect ratio
    │              using crop_tracking + FFmpeg
    │
    └─► FINAL JSON / DB
```

## Files to Modify

### 1. `backend/content_intelligence/analyzer.py`
- Add `detect_bounding_boxes(video_path, timestamps, content_category)` method
- For each frame, call Gemini vision with a prompt requesting bounding boxes in JSON
- Return list of `{timestamp, frame_width, frame_height, subjects: [{label, confidence, bounding_box: {x,y,width,height}}]}`
- Normalize coordinates to 0-1 range

### 2. `backend/content_intelligence/reframing.py`
- `build_crop_tracking` already exists - ensure it handles multiple subjects
- Add `build_output_formats(crop_tracking, source_width, source_height, aspect_ratios)` returning per-format crop + tracking data

### 3. `backend/video_processor/ffmpeg_service.py`
- Add `crop_with_tracking(input_path, output_path, crop_tracking, target_width, target_height)` method
- Uses FFmpeg `crop` filter with dynamic positions (or `sendcmd`/`zoompan` for tracking)
- Interpolate between tracking keyframes for smooth motion

### 4. `backend/clip_generation/service.py`
- Add `generate_clips_for_project` enhancement to:
  - Run bounding box detection on candidate clips
  - Generate crop_tracking per aspect ratio
  - Render each clip in each requested aspect ratio
  - Store output paths and tracking data

### 5. `backend/pipeline/service.py`
- Add new step type `BOUNDING_BOX_DETECTION` and `ASPECT_RATIO_RENDER`
- Wire into step_order after VISUAL_ANALYSIS and before CLIP_GENERATION

### 6. Database schema
- Add columns to `GeneratedClip` model:
  - `bounding_boxes` (JSON)
  - `crop_tracking` (JSON)
  - `output_formats` (JSON)
- Create Alembic migration

## Implementation Steps

1. **Extend FrameAnalyzer** with bounding box detection
2. **Enhance reframing module** with multi-format output generation
3. **Add FFmpeg crop_with_tracking** method
4. **Update ClipService** to run bounding box + rendering pipeline
5. **Add pipeline steps** for bounding box detection and aspect-ratio rendering
6. **Create Alembic migration** for new columns
7. **Add API endpoints** to retrieve bounding boxes and rendered clips

## Key Design Decisions

- **Vision model**: Use Gemini (already configured) for bounding box detection
- **Normalization**: All bounding boxes returned as 0-1 normalized coordinates
- **Tracking interpolation**: Linear interpolation between keyframes in FFmpeg layer
- **Aspect ratios**: 9:16, 1:1, 4:5, 16:9 (configurable per project)
- **Fallback**: If vision model fails, use center-crop heuristic

## Validation
- Run pipeline with test video
- Verify bounding boxes are accurate
- Verify cropped clips look correct in each aspect ratio
- Verify tracking follows subject movement