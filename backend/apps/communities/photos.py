"""Photo desk: blurs every face in a community photo while it is being uploaded.

The original never reaches storage. The photo is decoded in memory, faces are found with OpenCV's
YuNet detector (model file in ./assets, MIT licence) and blurred with a margin, and the result is
re-encoded as a new JPEG, which also drops all metadata (phone GPS location, camera, time).
A moderator then checks the blurred photo before anyone else sees it (posts.Post.image_status).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from django.core.files.base import ContentFile

MODEL = Path(__file__).resolve().parent / "assets" / "face_detection_yunet_2023mar.onnx"
MAX_SIDE = 1600           # photos are shrunk to this before detection and storage
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
SCORE_THRESHOLD = 0.5     # lower than the usual 0.6: missing a face is worse than blurring a patch
MARGIN = 0.3              # blur this much around each face box (hair, ears, side of the face)
SMALL_FACE = 24           # faces smaller than this (px) are hard to detect reliably: tell the moderator


class PhotoError(ValueError):
    pass


def blur_faces(upload) -> dict:
    """Read an uploaded image, blur every detected face, return the safe version.

    Returns {"file": ContentFile (JPEG), "faces": n, "notes": [things the moderator should check]}.
    """
    import cv2
    import numpy as np

    if upload.size > MAX_UPLOAD_BYTES:
        raise PhotoError("The photo is too large (max 10 MB).")
    data = np.frombuffer(upload.read(), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)  # applies the phone's rotation; metadata is not kept
    if img is None:
        raise PhotoError("That file isn't a photo we can read (use JPEG or PNG).")

    h, w = img.shape[:2]
    scale = min(1.0, MAX_SIDE / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]

    detector = cv2.FaceDetectorYN.create(str(MODEL), "", (w, h), SCORE_THRESHOLD, 0.3, 5000)
    _, found = detector.detect(img)
    faces = [] if found is None else found
    notes = []
    for f in faces:
        x, y, fw, fh = (int(v) for v in f[:4])
        pad_w, pad_h = int(fw * MARGIN), int(fh * MARGIN)
        x0, y0 = max(0, x - pad_w), max(0, y - pad_h)
        x1, y1 = min(w, x + fw + pad_w), min(h, y + fh + pad_h)
        if x1 <= x0 or y1 <= y0:
            continue
        region = img[y0:y1, x0:x1]
        # Pixelate, then blur: nothing of the face survives, even when zoomed in.
        small = cv2.resize(region, (max(1, (x1 - x0) // 12), max(1, (y1 - y0) // 12)), interpolation=cv2.INTER_LINEAR)
        region = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)
        k = max(31, ((x1 - x0) // 3) * 2 + 1)
        img[y0:y1, x0:x1] = cv2.GaussianBlur(region, (k, k), 0)
        if min(fw, fh) < SMALL_FACE:
            notes.append("Some faces are very small. Check that none were missed.")
    if len(faces) >= 8:
        notes.append(f"Many faces ({len(faces)}). Check the crowd for faces that were missed.")

    ok, jpeg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise PhotoError("Couldn't process the photo.")
    return {"file": ContentFile(jpeg.tobytes(), name=f"{uuid.uuid4().hex}.jpg"), "faces": len(faces),
            "notes": sorted(set(notes))}
