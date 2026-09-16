# IKOMA BAS Results and Inference Settings

Last updated: 16 September 2026

**Subject: IKOMA BAS results and inference settings**

Hi Martin and 根木さん,

I would like to share the current Ball Action Spotting (BAS) results for the IKOMA video.

## Results

- Video segment: 566.5 seconds from kickoff
- Detected candidates: 58 in total (`Pass`: 34, `Drive`: 24)
- Visualization video: **[Google Drive URL]**
- Predicted labels (`CSV` / `JSON`): **[Google Drive URL]**

## Model

- Public 2023 SoccerNet Ball Action Spotting winning solution: [lRomul/ball-action-spotting](https://github.com/lRomul/ball-action-spotting)
- Pretrained experiment: `ball_finetune_long_004`
- Classes: `Pass` and `Drive`
- Ensemble: seven official folds with horizontal-flip test-time augmentation

## Inference and post-processing

- The original 30 FPS video was converted to 25 FPS without cropping or resizing.
- Frames were converted to grayscale and padded from 1280×720 to 1280×736.
- The model uses 33 frames with a frame step of 2, covering about 2.56 seconds.
- Scores from the seven folds were averaged for each class.
- Event candidates were extracted independently per class using Gaussian smoothing (`sigma=3`), a peak threshold of `0.2`, and a minimum peak distance of 15 frames (0.6 seconds).

The video currently has no ground-truth annotations, and manual review of the 58 candidates is still in progress. Therefore, these counts are model predictions rather than accuracy results, and the displayed confidence values should not be interpreted as calibrated probabilities.

Best regards,

Yao
