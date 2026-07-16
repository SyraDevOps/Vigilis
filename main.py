"""
SkyMonitor — Interface Tkinter completa para monitoramento de céu.
Suporta: RTSP/IP cam, câmera local, arquivo de vídeo, pasta de imagens.
Pronto para compilar com PyInstaller.
"""

import os
import sys
import time
import math
import threading
import queue
import json
import shutil
from pathlib import Path
from datetime import datetime
from itertools import combinations

os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;5000000"

# --------------- Tkinter ---------------
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# --------------- NumPy / OpenCV ---------------
try:
    import numpy as np
except ImportError:
    messagebox.showerror("Erro", "numpy não instalado. Execute: pip install numpy")
    sys.exit(1)

try:
    import cv2
except ImportError:
    messagebox.showerror("Erro", "opencv-python não instalado.")
    sys.exit(1)

# --------------- PIL para exibir frames no Tkinter ---------------
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# --------------- SciPy ---------------
try:
    from scipy.spatial import KDTree
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

# ==========================================================
# CONFIGURAÇÕES PADRÃO
# ==========================================================
CFG = {
    "TOP_CROP_PX":            80,
    "BOTTOM_CROP_PX":         40,
    "TILE_SIZE":              128,
    "TOP_HAT_KERNEL_SIZE":    15,
    "PATCH_SIZE":             21,
    "MAX_STARS":              60,
    "SIGMA_FACTOR":           3.5,
    "MAX_STAR_AREA":          150,
    "MIN_ISOLATION_PX":       8,
    "CONFIDENCE_THRESHOLD":   25,
    "LOST_LIMIT_UNCONFIRMED": 3,
    "LOST_LIMIT_CONFIRMED":   300,
    "METEOR_MIN_LEN":         25,
    "METEOR_MIN_ASPECT":      3.0,
    "METEOR_MAX_LINE_DEV":    1.3,
    "METEOR_MIN_INTENSITY":   18.0,
    "CLOUD_BLUR_KERNEL":      61,
    "CLOUD_PERCENTILE":       68,
    "CLOUD_MORPH_CLOSE":      55,
    "CLOUD_MORPH_DILATE":     30,
    "CLOUD_MIN_AREA":         5000,
    "CLOUD_SOLIDITY_MIN":     0.15,
    "CLOUD_CONFIRM_FRAMES":   4,
    "CLOUD_LOST_LIMIT":       20,
    "CLOUD_MERGE_DIST":       250,
    "CLOUD_ALPHA":            0.15,
    "CONST_NEIGHBORS":        5,
    "CONST_MAX_EDGE":         220,
    "CONST_PERSIST_MIN":      3,
}


# ==========================================================
# LÓGICA DE DETECÇÃO (preservada do original)
# ==========================================================
class CelestialTracker:
    def __init__(self, cfg):
        self.cfg = cfg
        self.dist_threshold = 8
        self.tracked_stars  = []
        self.next_id        = 1

    def update(self, detected_coords, frame_idx):
        c = self.cfg
        updated_stars = []
        novel_stars   = []

        for star in self.tracked_stars:
            matched_coord = None
            min_dist      = float('inf')
            for coord in detected_coords:
                cx, cy, w, h = coord
                dist = math.hypot(cx - star['cx'], cy - star['cy'])
                if dist < self.dist_threshold and dist < min_dist:
                    min_dist      = dist
                    matched_coord = coord

            if matched_coord:
                cx, cy, w, h    = matched_coord
                star['cx']      = cx
                star['cy']      = cy
                star['w']       = w
                star['h']       = h
                star['frames_seen'] += 1
                star['last_seen']    = frame_idx
                star['history'].append((cx, cy))
                if len(star['history']) > c["CONFIDENCE_THRESHOLD"]:
                    star['history'].pop(0)

                xs = [p[0] for p in star['history']]
                ys = [p[1] for p in star['history']]
                if (max(xs) - min(xs)) > 3.0 or (max(ys) - min(ys)) > 3.0:
                    star['is_static'] = False

                if (star['frames_seen'] == c["CONFIDENCE_THRESHOLD"]
                        and star['is_static'] and not star['saved']):
                    star['id']    = self.next_id
                    self.next_id += 1
                    star['saved'] = True
                    novel_stars.append(star)

                detected_coords.remove(matched_coord)
                updated_stars.append(star)
            else:
                frames_lost = frame_idx - star['last_seen']
                if star['saved'] and star['is_static']:
                    if frames_lost <= c["LOST_LIMIT_CONFIRMED"]:
                        updated_stars.append(star)
                else:
                    if frames_lost <= c["LOST_LIMIT_UNCONFIRMED"]:
                        updated_stars.append(star)

        for coord in detected_coords:
            cx, cy, w, h = coord
            updated_stars.append({
                'id': None, 'cx': cx, 'cy': cy, 'w': w, 'h': h,
                'frames_seen': 1, 'last_seen': frame_idx,
                'saved': False, 'is_static': True, 'history': [(cx, cy)]
            })

        self.tracked_stars = updated_stars
        return novel_stars

    def get_confirmed_positions(self):
        return [
            (s['id'], s['cx'], s['cy'], s['w'], s['h'])
            for s in self.tracked_stars
            if s['saved'] and s['is_static']
        ]


class CloudTracker:
    def __init__(self, cfg):
        self.cfg = cfg
        self.tracked_clouds = []
        self.next_id        = 1

    def _overlaps(self, box1, box2, margin=120):
        x1, y1, w1, h1 = box1
        x2, y2, w2, h2 = box2
        return (
            max(x1 - margin, x2 - margin) < min(x1 + w1 + margin, x2 + w2 + margin) and
            max(y1 - margin, y2 - margin) < min(y1 + h1 + margin, y2 + h2 + margin)
        )

    def update(self, detected_clouds, frame_idx):
        c = self.cfg
        updated     = []
        matched_det = set()

        for tc in self.tracked_clouds:
            best = None
            for i, dc in enumerate(detected_clouds):
                if i in matched_det:
                    continue
                if self._overlaps(tc['box'], dc['box']):
                    best = i
                    break

            if best is not None:
                dc = detected_clouds[best]
                matched_det.add(best)
                ob = tc['box']
                nb = dc['box']
                tc['box'] = (
                    int(ob[0]*0.35 + nb[0]*0.65),
                    int(ob[1]*0.35 + nb[1]*0.65),
                    int(ob[2]*0.35 + nb[2]*0.65),
                    int(ob[3]*0.35 + nb[3]*0.65),
                )
                tc['cx']          = dc['cx']
                tc['cy']          = dc['cy']
                tc['area']        = dc['area']
                tc['contour']     = dc['contour']
                tc['is_cluster']  = dc['is_cluster']
                tc['cloud_count'] = dc['cloud_count']
                tc['frames_seen'] += 1
                tc['last_seen']   = frame_idx
                updated.append(tc)
            else:
                if frame_idx - tc['last_seen'] <= c["CLOUD_LOST_LIMIT"]:
                    updated.append(tc)

        for i, dc in enumerate(detected_clouds):
            if i not in matched_det:
                dc['id']          = self.next_id
                dc['frames_seen'] = 1
                dc['last_seen']   = frame_idx
                self.next_id     += 1
                updated.append(dc)

        self.tracked_clouds = updated
        return [cl for cl in self.tracked_clouds
                if cl['frames_seen'] >= c["CLOUD_CONFIRM_FRAMES"]]


class ConstellationMapper:
    def __init__(self, cfg):
        self.cfg    = cfg
        self.memory: dict = {}

    @staticmethod
    def _fingerprint(pa, pb, pc):
        d1 = math.dist(pa, pb)
        d2 = math.dist(pa, pc)
        d3 = math.dist(pb, pc)
        sides = sorted([d1, d2, d3])
        if sides[2] < 1e-3:
            return None
        r1 = sides[0] / sides[2]
        r2 = sides[1] / sides[2]
        s  = sum(sides) / 2
        sq = s * (s - sides[0]) * (s - sides[1]) * (s - sides[2])
        if sq <= 0:
            return None
        area = math.sqrt(sq)
        return (round(r1, 2), round(r2, 2), round(area / 100.0, 1))

    def update(self, star_positions):
        c = self.cfg
        if not HAS_SCIPY or len(star_positions) < 3:
            return [], []

        pts  = np.array([[s[1], s[2]] for s in star_positions], dtype=np.float32)
        k    = min(c["CONST_NEIGHBORS"] + 1, len(pts))
        tree = KDTree(pts)

        triangles  = []
        edges_set  = set()

        for idx in range(len(pts)):
            p       = pts[idx]
            _, inds = tree.query(p, k=k)
            neighbors = inds[1:]

            for i2, i3 in combinations(neighbors, 2):
                pa = tuple(pts[idx])
                pb = tuple(pts[i2])
                pc = tuple(pts[i3])

                if (math.dist(pa, pb) > c["CONST_MAX_EDGE"] or
                        math.dist(pa, pc) > c["CONST_MAX_EDGE"] or
                        math.dist(pb, pc) > c["CONST_MAX_EDGE"]):
                    continue

                fp = self._fingerprint(pa, pb, pc)
                if fp is None:
                    continue

                triangles.append((fp, (pa, pb, pc)))
                edges_set.add(tuple(sorted([pa, pb])))
                edges_set.add(tuple(sorted([pa, pc])))
                edges_set.add(tuple(sorted([pb, pc])))

        current_fps = {fp for fp, _ in triangles}
        for fp in current_fps:
            self.memory[fp] = self.memory.get(fp, 0) + 1

        to_remove = [k for k in self.memory if k not in current_fps]
        for k in to_remove:
            self.memory[k] -= 1
            if self.memory[k] <= 0:
                del self.memory[k]

        stable = [(fp, tri) for fp, tri in triangles
                  if self.memory.get(fp, 0) >= c["CONST_PERSIST_MIN"]]

        return stable, list(edges_set)

    def draw_on(self, img, stable_triangles, edges):
        for fp, (pa, pb, pc) in stable_triangles:
            persistence = self.memory.get(fp, 1)
            strength    = int(np.clip(persistence * 30, 50, 240))
            color       = (strength, 0, 255)
            for p1, p2 in [(pa, pb), (pa, pc), (pb, pc)]:
                cv2.line(img, (int(p1[0]), int(p1[1])),
                              (int(p2[0]), int(p2[1])),
                         color, 1, lineType=cv2.LINE_AA)

        node_deg: dict = {}
        for e in edges:
            a, b = e
            node_deg[a] = node_deg.get(a, 0) + 1
            node_deg[b] = node_deg.get(b, 0) + 1

        for node, deg in node_deg.items():
            if deg >= 5:
                cv2.circle(img, (int(node[0]), int(node[1])), 9,
                           (0, 255, 255), 1, lineType=cv2.LINE_AA)


# ==========================================================
# FUNÇÕES DE PROCESSAMENTO
# ==========================================================
def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def apply_tophat_filter(gray_frame, kernel_size):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    return cv2.morphologyEx(gray_frame, cv2.MORPH_TOPHAT, kernel)


def apply_tiled_threshold(tophat_img, sigma_factor, tile_size):
    h, w       = tophat_img.shape
    thresh_img = np.zeros_like(tophat_img)
    blurred    = cv2.GaussianBlur(tophat_img, (3, 3), 0)
    for y in range(0, h, tile_size):
        for x in range(0, w, tile_size):
            tile           = blurred[y:y+tile_size, x:x+tile_size]
            mean, std      = cv2.meanStdDev(tile)
            local_thr      = float(mean[0][0] + sigma_factor * std[0][0])
            local_thr      = max(10.0, min(local_thr, 254.0))
            _, tile_thresh = cv2.threshold(tile, int(local_thr), 255, cv2.THRESH_BINARY)
            thresh_img[y:y+tile_size, x:x+tile_size] = tile_thresh
    return thresh_img


def validate_star_patch_on_tophat(patch):
    h, w = patch.shape[:2]
    if h < 5 or w < 5:
        return False
    _, max_val, _, max_loc = cv2.minMaxLoc(patch)
    if max_val < 15:
        return False
    cx, cy = w // 2, h // 2
    if math.hypot(max_loc[0] - cx, max_loc[1] - cy) > w / 3.5:
        return False
    border_mask             = np.ones((h, w), dtype=bool)
    border_mask[2:-2, 2:-2] = False
    if np.mean(patch[border_mask]) > 6.5:
        return False
    if max_val / (np.mean(patch) + 1e-5) < 1.45:
        return False
    return True


def detect_stars_from_tophat(tophat_img, cfg):
    thresh = apply_tiled_threshold(tophat_img, cfg["SIGMA_FACTOR"], cfg["TILE_SIZE"])
    ck     = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2, 2))
    clean  = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, ck, iterations=1)
    contours, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area       = w * h
        if area > cfg["MAX_STAR_AREA"] or area < 2:
            continue
        asp = w / h if h > 0 else 0
        if asp < 0.25 or asp > 4.0:
            continue
        cx, cy   = x + w // 2, y + h // 2
        mask_roi = np.zeros(tophat_img.shape, dtype=np.uint8)
        cv2.drawContours(mask_roi, [cnt], -1, 255, -1)
        _, peak, _, _ = cv2.minMaxLoc(tophat_img, mask=mask_roi)
        candidates.append((x, y, w, h, cx, cy, peak))

    candidates.sort(key=lambda c: c[6], reverse=True)

    kept = []
    for cand in candidates:
        cx, cy    = cand[4], cand[5]
        too_close = any(
            abs(cx - k[4]) < cfg["MIN_ISOLATION_PX"] or abs(cy - k[5]) < cfg["MIN_ISOLATION_PX"]
            for k in kept
        )
        if not too_close:
            kept.append(cand)

    validated = []
    half      = cfg["PATCH_SIZE"] // 2
    ih, iw    = tophat_img.shape[:2]
    for cand in kept:
        x, y, w, h, cx, cy, _ = cand
        patch = tophat_img[max(0, cy-half):min(ih, cy+half+1),
                           max(0, cx-half):min(iw, cx+half+1)]
        if validate_star_patch_on_tophat(patch):
            validated.append((cx, cy, w, h))
        if len(validated) >= cfg["MAX_STARS"]:
            break
    return validated


def detect_meteors(tophat_img, bin_img, confirmed_star_positions, cfg):
    contours, _ = cv2.findContours(bin_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    detected    = []
    for c in contours:
        if len(c) < 5:
            continue
        rect              = cv2.minAreaRect(c)
        (cx, cy), (wr, hr), _ = rect
        length  = max(wr, hr)
        width   = min(wr, hr)
        aspect  = length / (width + 1e-5)
        if length < cfg["METEOR_MIN_LEN"] or aspect < cfg["METEOR_MIN_ASPECT"]:
            continue
        pts = c.reshape(-1, 2).astype(np.float32)
        [vx, vy, x0, y0] = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01)
        dx, dy, x0, y0   = vx[0], vy[0], x0[0], y0[0]
        if np.mean(np.abs(dy * (pts[:, 0]-x0) - dx * (pts[:, 1]-y0))) > cfg["METEOR_MAX_LINE_DEV"]:
            continue
        mask = np.zeros(tophat_img.shape, dtype=np.uint8)
        cv2.drawContours(mask, [c], -1, 255, -1)
        if cv2.mean(tophat_img, mask=mask)[0] < cfg["METEOR_MIN_INTENSITY"]:
            continue
        if any(math.hypot(cx-sx, cy-sy) < 18 for _, sx, sy, _, _ in confirmed_star_positions):
            continue
        x, y, w, h = cv2.boundingRect(c)
        detected.append((x, y, w, h, (dx, dy, x0, y0)))
    return detected


def detect_clouds(frame_bgr, cfg):
    top_crop    = cfg["TOP_CROP_PX"]
    bottom_crop = cfg["BOTTOM_CROP_PX"]
    h_full, w_full = frame_bgr.shape[:2]
    roi = frame_bgr[top_crop: h_full - bottom_crop, :]

    gray = (
        0.2126 * roi[:, :, 2].astype(np.float32) +
        0.7152 * roi[:, :, 1].astype(np.float32) +
        0.0722 * roi[:, :, 0].astype(np.float32)
    ).astype(np.uint8)

    bk   = cfg["CLOUD_BLUR_KERNEL"]
    blur = cfg["CLOUD_BLUR_KERNEL"] if bk % 2 == 1 else bk + 1
    blurred = cv2.GaussianBlur(gray, (blur, blur), 0)

    thr_val  = np.percentile(blurred, cfg["CLOUD_PERCENTILE"])
    thr_val  = max(thr_val, 8.0)
    _, binary = cv2.threshold(blurred, thr_val, 255, cv2.THRESH_BINARY)

    mc = cfg["CLOUD_MORPH_CLOSE"]
    md = cfg["CLOUD_MORPH_DILATE"]
    k_close  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (mc, mc))
    k_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (md, md))
    closed   = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k_close, iterations=3)
    dilated  = cv2.dilate(closed, k_dilate, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    raw = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < cfg["CLOUD_MIN_AREA"]:
            continue
        hull      = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        solidity  = area / (hull_area + 1e-5)
        if solidity < cfg["CLOUD_SOLIDITY_MIN"]:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        raw.append({'box': (x, y, w, h), 'cx': x + w//2, 'cy': y + h//2,
                    'area': area, 'contour': cnt,
                    'is_cluster': False, 'cloud_count': 1})

    if not raw:
        return []

    n      = len(raw)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        parent[find(i)] = find(j)

    for i in range(n):
        for j in range(i + 1, n):
            d = math.hypot(raw[i]['cx'] - raw[j]['cx'], raw[i]['cy'] - raw[j]['cy'])
            if d < cfg["CLOUD_MERGE_DIST"]:
                union(i, j)

    groups: dict = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    merged = []
    for root, members in groups.items():
        if len(members) == 1:
            c = raw[members[0]]
            c['is_cluster']  = False
            c['cloud_count'] = 1
            merged.append(c)
        else:
            xs = [raw[m]['box'][0] for m in members]
            ys = [raw[m]['box'][1] for m in members]
            xe = [raw[m]['box'][0] + raw[m]['box'][2] for m in members]
            ye = [raw[m]['box'][1] + raw[m]['box'][3] for m in members]
            gx, gy   = min(xs), min(ys)
            gw, gh   = max(xe) - gx, max(ye) - gy
            total_area = sum(raw[m]['area'] for m in members)
            combined   = np.concatenate([raw[m]['contour'] for m in members])
            merged.append({
                'box': (gx, gy, gw, gh), 'cx': gx + gw//2, 'cy': gy + gh//2,
                'area': total_area, 'contour': combined,
                'is_cluster': True, 'cloud_count': len(members),
            })

    return merged


# ==========================================================
# FUNÇÕES DE DESENHO HUD
# ==========================================================
def draw_star_hud(img, star_id, center_coords, size_box):
    cx, cy  = center_coords
    w, h    = size_box
    radius  = max(w, h) // 2 + 5
    color   = (0, 230, 115)
    cv2.circle(img, (cx, cy), radius, color, 1, lineType=cv2.LINE_AA)
    cv2.circle(img, (cx, cy), 1, color, -1, lineType=cv2.LINE_AA)
    text = f"STAR #{star_id}"
    font, fs = cv2.FONT_HERSHEY_SIMPLEX, 0.3
    (tw, th), _ = cv2.getTextSize(text, font, fs, 1)
    cv2.line(img, (cx+radius, cy), (cx+radius+6, cy), color, 1, lineType=cv2.LINE_AA)
    tx, ty = cx+radius+7, cy-th//2-2
    cv2.rectangle(img, (tx, ty), (tx+tw+4, ty+th+4), (12, 12, 12), -1)
    cv2.rectangle(img, (tx, ty), (tx+tw+4, ty+th+4), color, 1, lineType=cv2.LINE_AA)
    cv2.putText(img, text, (tx+2, ty+th+1), font, fs, color, 1, lineType=cv2.LINE_AA)


def draw_meteor_hud(img, box, vector_data=None):
    x, y, w, h = box
    color = (0, 140, 255)
    lc    = max(4, min(12, min(w, h) // 4))
    for (px, py, dx, dy) in [(x, y, 1, 1), (x+w, y, -1, 1),
                              (x, y+h, 1, -1), (x+w, y+h, -1, -1)]:
        cv2.line(img, (px, py), (px+dx*lc, py), color, 1, lineType=cv2.LINE_AA)
        cv2.line(img, (px, py), (px, py+dy*lc), color, 1, lineType=cv2.LINE_AA)
    text = "METEOR"
    if vector_data:
        dx, dy, _, _ = vector_data
        text += f" [{abs(math.degrees(math.atan2(dy, dx))):.1f}°]"
    font, fs = cv2.FONT_HERSHEY_SIMPLEX, 0.35
    (tw, th), _ = cv2.getTextSize(text, font, fs, 1)
    ly = max(y-th-6, 10)
    cv2.rectangle(img, (x, ly), (x+tw+6, ly+th+4), (12, 12, 12), -1)
    cv2.rectangle(img, (x, ly), (x+tw+6, ly+th+4), color, 1, lineType=cv2.LINE_AA)
    cv2.putText(img, text, (x+3, ly+th+1), font, fs, color, 1, lineType=cv2.LINE_AA)


def draw_cloud_hud(img, cloud, top_crop, alpha):
    CLOUD_COLOR   = (200, 80,  230)
    CLUSTER_COLOR = (130, 50,  255)
    FILL_COLOR    = (210, 130, 245)
    color = CLUSTER_COLOR if cloud['is_cluster'] else CLOUD_COLOR

    x, y, w, h = cloud['box']
    y_full      = y + top_crop

    cnt_shifted = cloud['contour'].copy()
    cnt_shifted[:, :, 1] += top_crop

    overlay = img.copy()
    cv2.drawContours(overlay, [cnt_shifted], -1, FILL_COLOR, -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)

    border_ov = img.copy()
    cv2.drawContours(border_ov, [cnt_shifted], -1, color, 4, lineType=cv2.LINE_AA)
    cv2.addWeighted(border_ov, 0.6, img, 0.4, 0, img)
    cv2.drawContours(img, [cnt_shifted], -1, color, 1, lineType=cv2.LINE_AA)

    lc  = max(8, min(22, min(w, h) // 5))
    bx, by   = x, y_full
    bx2, by2 = x + w, y_full + h
    for (px, py, dx, dy) in [(bx, by, 1, 1), (bx2, by, -1, 1),
                              (bx, by2, 1, -1), (bx2, by2, -1, -1)]:
        cv2.line(img, (px, py), (px + dx * lc, py), color, 1, lineType=cv2.LINE_AA)
        cv2.line(img, (px, py), (px, py + dy * lc), color, 1, lineType=cv2.LINE_AA)

    roi_area = (img.shape[0] - top_crop - 40) * img.shape[1]
    cov_pct  = min(99.9, cloud['area'] / (roi_area + 1e-5) * 100)
    label    = (f"CLOUD CLUSTER [{cloud['cloud_count']}]  {cov_pct:.1f}% COV"
                if cloud['is_cluster'] else f"CLOUD  {cov_pct:.1f}% COV")
    font, fs = cv2.FONT_HERSHEY_SIMPLEX, 0.38
    (tw, th), _ = cv2.getTextSize(label, font, fs, 1)
    lx = max(0, min(bx, img.shape[1] - tw - 8))
    ly = max(th + 6, by - 5)
    cv2.rectangle(img, (lx, ly - th - 3), (lx + tw + 6, ly + 3), (10, 10, 20), -1)
    cv2.rectangle(img, (lx, ly - th - 3), (lx + tw + 6, ly + 3), color, 1, lineType=cv2.LINE_AA)
    cv2.putText(img, label, (lx + 3, ly), font, fs, color, 1, lineType=cv2.LINE_AA)


def extract_patch(img, cx, cy, size):
    half = size // 2
    return img[max(0, cy-half):min(img.shape[0], cy+half+1),
               max(0, cx-half):min(img.shape[1], cx+half+1)].copy()


def save_patch_grid(patch_buffer, folder, prefix, grid_counter, patch_size):
    grid = np.zeros((patch_size*3, patch_size*3, 3), dtype=np.uint8)
    for idx, patch in enumerate(patch_buffer[:9]):
        r, c = idx // 3, idx % 3
        if len(patch.shape) == 2:
            patch = cv2.cvtColor(patch, cv2.COLOR_GRAY2BGR)
        p = cv2.resize(patch, (patch_size, patch_size))
        cv2.rectangle(p, (0, 0), (patch_size-1, patch_size-1), (100, 100, 100), 1)
        grid[r*patch_size:(r+1)*patch_size, c*patch_size:(c+1)*patch_size] = p
    cv2.imwrite(str(folder / f"{prefix}_grid_{grid_counter:04d}.png"), grid)


# ==========================================================
# THREAD DE PROCESSAMENTO
# ==========================================================
class ProcessingThread(threading.Thread):
    def __init__(self, source_type, source_value, output_dir, cfg,
                 frame_queue, log_queue, stats_queue, stop_event,
                 show_stars, show_meteors, show_clouds, show_triangles):
        super().__init__(daemon=True)
        self.source_type   = source_type    # rtsp | device | video | images
        self.source_value  = source_value
        self.output_dir    = Path(output_dir)
        self.cfg           = cfg
        self.frame_queue   = frame_queue    # frames para exibir
        self.log_queue     = log_queue      # mensagens de log
        self.stats_queue   = stats_queue    # dicionário de stats
        self.stop_event    = stop_event
        self.show_stars    = show_stars
        self.show_meteors  = show_meteors
        self.show_clouds   = show_clouds
        self.show_triangles = show_triangles

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{ts}] {msg}")

    def _setup_dirs(self):
        d = self.output_dir
        dirs = {
            "stars_id":     d / "stars" / "identified",
            "stars_grids":  d / "stars" / "grids",
            "sky_maps":     d / "sky_maps",
            "meteors_f":    d / "meteors" / "frames",
            "meteors_t":    d / "meteors" / "trajectories",
            "meteors_p":    d / "meteors" / "patches",
            "meteors_g":    d / "meteors" / "grids",
            "clouds":       d / "clouds",
            "constellations": d / "constellations",
            "filtered":     d / "filtered",
        }
        for path in dirs.values():
            ensure_dir(path)
        return dirs

    def _open_source(self):
        st = self.source_type
        sv = self.source_value
        if st == "rtsp":
            self.log(f"Conectando RTSP: {sv}")
            for attempt in range(1, 6):
                self.log(f"Tentativa {attempt}/5...")
                cap = cv2.VideoCapture(sv, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        self.log(f"Conectado! {frame.shape[1]}x{frame.shape[0]}")
                        return cap, [frame], False
                    cap.release()
                if self.stop_event.is_set():
                    return None, [], False
                time.sleep(3)
            self.log("[ERRO] Sem conexão RTSP.")
            return None, [], False

        elif st == "device":
            idx = int(sv) if str(sv).isdigit() else 0
            self.log(f"Abrindo câmera do dispositivo (índice {idx})...")
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    self.log(f"Câmera aberta! {frame.shape[1]}x{frame.shape[0]}")
                    return cap, [frame], False
            self.log("[ERRO] Não foi possível abrir a câmera.")
            return None, [], False

        elif st == "video":
            self.log(f"Abrindo vídeo: {sv}")
            cap = cv2.VideoCapture(str(sv))
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    self.log(f"Vídeo aberto! {frame.shape[1]}x{frame.shape[0]}")
                    return cap, [frame], False
            self.log("[ERRO] Não foi possível abrir o vídeo.")
            return None, [], False

        elif st == "images":
            folder = Path(sv)
            exts   = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
            files  = sorted([f for f in folder.iterdir() if f.suffix.lower() in exts])
            if not files:
                self.log("[ERRO] Nenhuma imagem encontrada na pasta.")
                return None, [], True
            self.log(f"{len(files)} imagens encontradas.")
            return None, files, True

        return None, [], False

    def run(self):
        cfg  = self.cfg
        dirs = self._setup_dirs()

        cap, source, is_images = self._open_source()
        if not source and not is_images:
            self.log("[ERRO] Fonte inválida ou inacessível.")
            return

        star_tracker   = CelestialTracker(cfg)
        cloud_tracker  = CloudTracker(cfg)
        const_mapper   = ConstellationMapper(cfg)

        frame_idx          = 0
        star_patches_buf   = []
        meteor_patches_buf = []
        star_grid_count    = 1
        meteor_grid_count  = 1
        last_skymap_time   = time.time()
        last_cloud_save_t  = 0
        total_stars_saved  = 0
        total_meteors      = 0
        total_clouds       = 0

        image_index = 0
        image_delay = 0.1   # segundos entre imagens ao processar pasta

        def get_next_frame():
            nonlocal image_index, cap
            if is_images:
                if image_index >= len(source):
                    return False, None
                img = cv2.imread(str(source[image_index]))
                image_index += 1
                time.sleep(image_delay)
                return (img is not None), img
            else:
                ret, frame = cap.read()
                if not ret or frame is None:
                    if self.source_type == "rtsp":
                        self.log("Sinal perdido. Reconectando...")
                        cap.release()
                        cap2, frames2, _ = self._open_source()
                        if cap2 is None:
                            return False, None
                        cap = cap2  # noqa (reassigning nonlocal via closure)
                        return True, frames2[0]
                    return False, None
                return True, frame

        frame = source[0] if (not is_images and source) else None
        if is_images and source:
            frame = cv2.imread(str(source[0]))
            image_index = 1

        if frame is None:
            self.log("[ERRO] Primeiro frame inválido.")
            return

        self.log("Processamento iniciado.")

        while not self.stop_event.is_set():
            frame_idx += 1

            # ---- Pipeline de análise ----
            top    = cfg["TOP_CROP_PX"]
            bot    = cfg["BOTTOM_CROP_PX"]
            h_f    = frame.shape[0]
            bottom = h_f - bot if h_f > top + bot else h_f
            cropped      = frame[top:bottom, :]
            gray_cropped = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
            tophat_c     = apply_tophat_filter(gray_cropped, cfg["TOP_HAT_KERNEL_SIZE"])
            bin_img      = apply_tiled_threshold(tophat_c, cfg["SIGMA_FACTOR"], cfg["TILE_SIZE"])

            star_coords      = detect_stars_from_tophat(tophat_c, cfg)
            novel_stars      = star_tracker.update(star_coords, frame_idx)
            confirmed_pos    = star_tracker.get_confirmed_positions()
            meteors          = detect_meteors(tophat_c, bin_img, confirmed_pos, cfg)
            raw_clouds       = detect_clouds(frame, cfg)
            confirmed_clouds = cloud_tracker.update(raw_clouds, frame_idx)

            conf_full = [(sid, cx, cy + top, w, h) for sid, cx, cy, w, h in confirmed_pos]
            stable_triangles, edges = const_mapper.update(conf_full)

            current_time = time.time()

            # ---- Salva estrelas novas ----
            for s in novel_stars:
                patch = extract_patch(gray_cropped, s['cx'], s['cy'], cfg["PATCH_SIZE"])
                if patch.size > 0:
                    ts     = int(time.time() * 1000)
                    marked = cv2.cvtColor(patch, cv2.COLOR_GRAY2BGR)
                    ph, pw = marked.shape[:2]
                    pcx, pcy = pw//2, ph//2
                    cv2.circle(marked, (pcx, pcy), max(s['w'], s['h'])//2+3,
                               (0, 230, 115), 1, lineType=cv2.LINE_AA)
                    cv2.putText(marked, f"ID {s['id']}", (2, ph-3),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.25, (0, 230, 115), 1,
                                lineType=cv2.LINE_AA)
                    cv2.imwrite(str(dirs["stars_id"] / f"star_ID_{s['id']}_{ts}.png"), marked)
                    star_patches_buf.append(patch)
                    total_stars_saved += 1

            # ---- Salva meteoros ----
            if meteors:
                total_meteors += len(meteors)
                ts = int(current_time * 1000)
                f_save = frame.copy()
                for sid, cx, cy, w, h in confirmed_pos:
                    draw_star_hud(f_save, sid, (cx, cy+top), (w, h))
                for cloud in confirmed_clouds:
                    draw_cloud_hud(f_save, cloud, top, cfg["CLOUD_ALPHA"])
                for mx, my, mw, mh, vec in meteors:
                    draw_meteor_hud(f_save, (mx, my+top, mw, mh), vec)
                cv2.imwrite(str(dirs["meteors_f"] / f"meteor_frame_{ts}.jpg"), f_save)

                f_traj = frame.copy()
                for mx, my, mw, mh, vec in meteors:
                    dx, dy, x0, y0 = vec
                    cv2.line(f_traj,
                             (int(x0-dx*1000), int(y0-dy*1000+top)),
                             (int(x0+dx*1000), int(y0+dy*1000+top)),
                             (255, 60, 120), 1, lineType=cv2.LINE_AA)
                    draw_meteor_hud(f_traj, (mx, my+top, mw, mh), vec)
                cv2.imwrite(str(dirs["meteors_t"] / f"trajectory_{ts}.jpg"), f_traj)

            # ---- Salva nuvens ----
            if confirmed_clouds and (current_time - last_cloud_save_t >= 60.0):
                last_cloud_save_t = current_time
                ts = int(current_time * 1000)
                cf = frame.copy()
                for cloud in confirmed_clouds:
                    draw_cloud_hud(cf, cloud, top, cfg["CLOUD_ALPHA"])
                n_cl = len(confirmed_clouds)
                n_clu = sum(1 for c in confirmed_clouds if c['is_cluster'])
                cv2.imwrite(str(dirs["clouds"] / f"cloud_event_{ts}_n{n_cl}.jpg"), cf)
                total_clouds += n_cl
                self.log(f"[NUVEM] {n_cl} nuvem(ns), {n_clu} cluster(s) — salvo.")

            # ---- Skymap a cada 30s ----
            if current_time - last_skymap_time >= 30.0:
                last_skymap_time = current_time
                ts         = int(current_time * 1000)
                subfolder  = dirs["sky_maps"] / f"{ts}_session"
                ensure_dir(subfolder)

                cv2.imwrite(str(subfolder / "original.jpg"), frame)

                f_ann = frame.copy()
                for sid, cx, cy, w, h in confirmed_pos:
                    draw_star_hud(f_ann, sid, (cx, cy+top), (w, h))
                for cloud in confirmed_clouds:
                    draw_cloud_hud(f_ann, cloud, top, cfg["CLOUD_ALPHA"])
                for mx, my, mw, mh, vec in meteors:
                    draw_meteor_hud(f_ann, (mx, my+top, mw, mh), vec)
                cv2.imwrite(str(subfolder / "anotado.jpg"), f_ann)

                skymap = np.zeros((frame.shape[0], frame.shape[1], 3), dtype=np.uint8)
                for sid, cx, cy, w, h in confirmed_pos:
                    cy_f = cy + top
                    cv2.circle(skymap, (cx, cy_f), 2, (255, 255, 255), -1, lineType=cv2.LINE_AA)
                    cv2.putText(skymap, f"ID:{sid}", (cx+5, cy_f+3),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.25, (180, 180, 180), 1,
                                lineType=cv2.LINE_AA)
                cv2.imwrite(str(subfolder / "skymap.png"), skymap)

                const_subfolder = dirs["constellations"] / f"{ts}_session"
                ensure_dir(const_subfolder)
                cv2.imwrite(str(const_subfolder / "skymap.png"), skymap)

                const_canvas = np.zeros((frame.shape[0], frame.shape[1], 3), dtype=np.uint8)
                const_mapper.draw_on(const_canvas, stable_triangles, edges)
                cv2.putText(const_canvas, f"GEOMETRIC TRIANGULATION",
                            (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 80, 220), 1,
                            lineType=cv2.LINE_AA)
                cv2.putText(const_canvas, f"Stable triangles: {len(stable_triangles)}",
                            (12, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (100, 100, 200), 1,
                            lineType=cv2.LINE_AA)
                for sid, cx, cy, w, h in conf_full:
                    b = max(2, min(6, (w + h) // 2))
                    cv2.circle(const_canvas, (cx, cy), b, (255, 255, 255), -1, lineType=cv2.LINE_AA)
                cv2.imwrite(str(const_subfolder / "triangulation.png"), const_canvas)
                self.log(f"[SKYMAP] Lote salvo. Triângulos estáveis: {len(stable_triangles)}")

            # ---- Grids ----
            while len(star_patches_buf) >= 9:
                save_patch_grid(star_patches_buf[:9], dirs["stars_grids"],
                                "stars", star_grid_count, cfg["PATCH_SIZE"])
                star_grid_count += 1
                star_patches_buf = star_patches_buf[9:]

            while len(meteor_patches_buf) >= 9:
                save_patch_grid(meteor_patches_buf[:9], dirs["meteors_g"],
                                "meteors", meteor_grid_count, cfg["PATCH_SIZE"])
                meteor_grid_count += 1
                meteor_patches_buf = meteor_patches_buf[9:]

            # ---- Monta display com filtros opcionais ----
            display = frame.copy()
            cv2.rectangle(display, (0, 0), (frame.shape[1], top), (15, 15, 15), -1)
            bot_y = frame.shape[0] - bot
            if bot_y > 0:
                cv2.rectangle(display, (0, bot_y),
                              (frame.shape[1], frame.shape[0]), (15, 15, 15), -1)

            if self.show_triangles.get():
                const_mapper.draw_on(display, stable_triangles, edges)

            if self.show_stars.get():
                for sid, cx, cy, w, h in confirmed_pos:
                    draw_star_hud(display, sid, (cx, cy+top), (w, h))

            if self.show_clouds.get():
                for cloud in confirmed_clouds:
                    draw_cloud_hud(display, cloud, top, cfg["CLOUD_ALPHA"])

            if self.show_meteors.get():
                for mx, my, mw, mh, vec in meteors:
                    draw_meteor_hud(display, (mx, my+top, mw, mh), vec)

            n_cl  = len(confirmed_clouds)
            n_clu = sum(1 for c in confirmed_clouds if c['is_cluster'])
            status = (f"Stars: {len(confirmed_pos)} | "
                      f"Meteors: {len(meteors)} | "
                      f"Clouds: {n_cl} ({n_clu} clusters) | "
                      f"Tri: {len(stable_triangles)}")
            cv2.putText(display, "SKY MONITOR — ATIVO",
                        (10, top-30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.35, (100, 100, 100), 1, lineType=cv2.LINE_AA)
            cv2.putText(display, status,
                        (10, top-10), cv2.FONT_HERSHEY_SIMPLEX,
                        0.4, (240, 240, 240), 1, lineType=cv2.LINE_AA)

            # Salva frame filtrado em pasta filtered a cada 5s
            if frame_idx % 150 == 0:
                ts_f = int(current_time * 1000)
                cv2.imwrite(str(dirs["filtered"] / f"filtered_{ts_f}.jpg"), display)

            # ---- Envia para a fila de exibição ----
            try:
                self.frame_queue.put_nowait(display.copy())
            except queue.Full:
                pass

            # ---- Atualiza stats ----
            stats = {
                "stars":    len(confirmed_pos),
                "meteors":  len(meteors),
                "clouds":   n_cl,
                "triangles": len(stable_triangles),
                "total_stars":   total_stars_saved,
                "total_meteors": total_meteors,
                "total_clouds":  total_clouds,
                "frame":    frame_idx,
            }
            try:
                self.stats_queue.put_nowait(stats)
            except queue.Full:
                pass

            # ---- Próximo frame ----
            ret, frame = get_next_frame()
            if not ret or frame is None:
                if is_images:
                    self.log("Todas as imagens processadas.")
                else:
                    self.log("Transmissão encerrada.")
                break

        # Flush
        if star_patches_buf:
            save_patch_grid(star_patches_buf, dirs["stars_grids"],
                            "stars_final", star_grid_count, cfg["PATCH_SIZE"])
        if meteor_patches_buf:
            save_patch_grid(meteor_patches_buf, dirs["meteors_g"],
                            "meteors_final", meteor_grid_count, cfg["PATCH_SIZE"])

        if cap:
            cap.release()
        self.log("Processamento finalizado.")


# ==========================================================
# INTERFACE TKINTER
# ==========================================================
class SkyMonitorApp:
    DARK_BG    = "#0d0d1a"
    PANEL_BG   = "#12121f"
    ACCENT     = "#5e35b1"
    ACCENT2    = "#00e676"
    TEXT_COLOR = "#e0e0ff"
    WARN_COLOR = "#ff6d00"
    FPS_TARGET = 25

    def __init__(self, root):
        self.root = root
        self.root.title("SkyMonitor v2.0 — Monitoramento Astronômico")
        self.root.configure(bg=self.DARK_BG)
        self.root.minsize(1100, 700)

        self.cfg = dict(CFG)

        self.frame_queue = queue.Queue(maxsize=2)
        self.log_queue   = queue.Queue()
        self.stats_queue = queue.Queue(maxsize=2)

        self.stop_event     = threading.Event()
        self.proc_thread    = None
        self.running        = False
        self.current_imgtk  = None

        # toggles de exibição
        self.show_stars     = tk.BooleanVar(value=True)
        self.show_meteors   = tk.BooleanVar(value=True)
        self.show_clouds    = tk.BooleanVar(value=True)
        self.show_triangles = tk.BooleanVar(value=True)

        self._build_ui()
        self._poll_frames()
        self._poll_logs()
        self._poll_stats()

    # ----------------------------------------------------------
    # CONSTRUÇÃO DA UI
    # ----------------------------------------------------------
    def _build_ui(self):
        # ---- Menu ----
        menubar = tk.Menu(self.root, bg=self.PANEL_BG, fg=self.TEXT_COLOR,
                          activebackground=self.ACCENT, activeforeground="white",
                          tearoff=0)
        file_menu = tk.Menu(menubar, tearoff=0, bg=self.PANEL_BG, fg=self.TEXT_COLOR)
        file_menu.add_command(label="Abrir pasta de saída", command=self._open_output_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self._on_close)
        menubar.add_cascade(label="Arquivo", menu=file_menu)

        cfg_menu = tk.Menu(menubar, tearoff=0, bg=self.PANEL_BG, fg=self.TEXT_COLOR)
        cfg_menu.add_command(label="Configurações avançadas", command=self._open_settings)
        menubar.add_cascade(label="Configurações", menu=cfg_menu)

        self.root.config(menu=menubar)

        # ---- Layout principal ----
        self.paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL,
                                    bg=self.DARK_BG, sashwidth=4,
                                    sashrelief=tk.RAISED)
        self.paned.pack(fill=tk.BOTH, expand=True)

        # Painel esquerdo: controles
        left = tk.Frame(self.paned, bg=self.PANEL_BG, width=300)
        self.paned.add(left, minsize=260)

        # Painel central: vídeo
        center = tk.Frame(self.paned, bg=self.DARK_BG)
        self.paned.add(center, minsize=500)

        # Painel direito: log + stats
        right = tk.Frame(self.paned, bg=self.PANEL_BG, width=270)
        self.paned.add(right, minsize=220)

        self._build_left(left)
        self._build_center(center)
        self._build_right(right)

    def _lbl(self, parent, text, size=9, bold=False, color=None):
        color = color or self.TEXT_COLOR
        weight = "bold" if bold else "normal"
        return tk.Label(parent, text=text, bg=self.PANEL_BG, fg=color,
                        font=("Consolas", size, weight))

    def _build_left(self, parent):
        pad = dict(padx=10, pady=4)

        # Logo
        logo = tk.Label(parent, text="◉ SKY MONITOR", bg=self.PANEL_BG,
                        fg=self.ACCENT2, font=("Consolas", 13, "bold"))
        logo.pack(pady=(14, 2))
        tk.Label(parent, text="v2.0 — Monitoramento Astronômico",
                 bg=self.PANEL_BG, fg="#7070a0",
                 font=("Consolas", 8)).pack(pady=(0, 10))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=8, pady=4)

        # --- Fonte de entrada ---
        self._lbl(parent, "FONTE DE ENTRADA", bold=True, color=self.ACCENT2).pack(**pad, anchor="w")

        self.source_type = tk.StringVar(value="rtsp")
        sources = [
            ("Câmera RTSP / IP", "rtsp"),
            ("Câmera do dispositivo", "device"),
            ("Arquivo de vídeo", "video"),
            ("Pasta de imagens", "images"),
        ]
        for text, val in sources:
            rb = tk.Radiobutton(parent, text=text, variable=self.source_type,
                                value=val, command=self._on_source_change,
                                bg=self.PANEL_BG, fg=self.TEXT_COLOR,
                                selectcolor=self.DARK_BG, activebackground=self.PANEL_BG,
                                font=("Consolas", 9))
            rb.pack(anchor="w", padx=16, pady=1)

        # URL / caminho
        self._lbl(parent, "URL / Caminho / Índice:").pack(**pad, anchor="w")
        url_frame = tk.Frame(parent, bg=self.PANEL_BG)
        url_frame.pack(fill="x", padx=10, pady=2)
        self.source_entry = tk.Entry(url_frame, bg=self.DARK_BG, fg=self.TEXT_COLOR,
                                     insertbackground=self.TEXT_COLOR,
                                     font=("Consolas", 9), relief="flat",
                                     highlightthickness=1,
                                     highlightcolor=self.ACCENT,
                                     highlightbackground="#333355")
        self.source_entry.insert(0, "rtsp://admin:123456@200.18.144.232:554")
        self.source_entry.pack(side="left", fill="x", expand=True, ipady=4)

        self.browse_btn = tk.Button(url_frame, text="📂", command=self._browse_source,
                                    bg=self.ACCENT, fg="white", relief="flat",
                                    font=("Consolas", 10), cursor="hand2")
        self.browse_btn.pack(side="left", padx=(4, 0))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=8, pady=8)

        # --- Pasta de saída ---
        self._lbl(parent, "PASTA DE SAÍDA", bold=True, color=self.ACCENT2).pack(**pad, anchor="w")
        out_frame = tk.Frame(parent, bg=self.PANEL_BG)
        out_frame.pack(fill="x", padx=10, pady=2)
        self.output_entry = tk.Entry(out_frame, bg=self.DARK_BG, fg=self.TEXT_COLOR,
                                     insertbackground=self.TEXT_COLOR,
                                     font=("Consolas", 9), relief="flat",
                                     highlightthickness=1,
                                     highlightcolor=self.ACCENT,
                                     highlightbackground="#333355")
        self.output_entry.insert(0, "dataset_sky_monitor")
        self.output_entry.pack(side="left", fill="x", expand=True, ipady=4)
        tk.Button(out_frame, text="📂", command=self._browse_output,
                  bg=self.ACCENT, fg="white", relief="flat",
                  font=("Consolas", 10), cursor="hand2").pack(side="left", padx=(4, 0))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=8, pady=8)

        # --- Filtros de exibição ---
        self._lbl(parent, "FILTROS DE EXIBIÇÃO", bold=True, color=self.ACCENT2).pack(**pad, anchor="w")
        for text, var in [
            ("🌟  Estrelas",        self.show_stars),
            ("☄️   Meteoros",       self.show_meteors),
            ("☁️   Nuvens",         self.show_clouds),
            ("🔺  Triangulações",   self.show_triangles),
        ]:
            cb = tk.Checkbutton(parent, text=text, variable=var,
                                bg=self.PANEL_BG, fg=self.TEXT_COLOR,
                                selectcolor=self.DARK_BG, activebackground=self.PANEL_BG,
                                font=("Consolas", 9))
            cb.pack(anchor="w", padx=16, pady=1)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=8, pady=8)

        # --- Controles ---
        self._lbl(parent, "CONTROLE", bold=True, color=self.ACCENT2).pack(**pad, anchor="w")

        self.start_btn = tk.Button(parent, text="▶  INICIAR", command=self._start,
                                   bg="#1b5e20", fg="white", relief="flat",
                                   font=("Consolas", 11, "bold"), cursor="hand2",
                                   activebackground="#2e7d32", activeforeground="white",
                                   pady=8)
        self.start_btn.pack(fill="x", padx=10, pady=4)

        self.stop_btn = tk.Button(parent, text="⏹  PARAR", command=self._stop,
                                  bg="#b71c1c", fg="white", relief="flat",
                                  font=("Consolas", 11, "bold"), cursor="hand2",
                                  activebackground="#c62828", activeforeground="white",
                                  pady=8, state="disabled")
        self.stop_btn.pack(fill="x", padx=10, pady=4)

        tk.Button(parent, text="📁  Abrir saída", command=self._open_output_folder,
                  bg=self.ACCENT, fg="white", relief="flat",
                  font=("Consolas", 9), cursor="hand2", pady=6).pack(
            fill="x", padx=10, pady=4)

        # status indicator
        self.status_var = tk.StringVar(value="● AGUARDANDO")
        self.status_lbl = tk.Label(parent, textvariable=self.status_var,
                                   bg=self.PANEL_BG, fg="#7070a0",
                                   font=("Consolas", 9, "bold"))
        self.status_lbl.pack(pady=10)

    def _build_center(self, parent):
        # Canvas de vídeo
        self.canvas = tk.Canvas(parent, bg="#000011", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas_w = 640
        self._canvas_h = 480

        # Texto de placeholder
        self._placeholder = self.canvas.create_text(
            320, 240, text="SKY MONITOR\n\nSelecione a fonte e clique em INICIAR",
            fill="#2a2a4a", font=("Consolas", 16, "bold"), justify="center")

    def _build_right(self, parent):
        # Stats
        stats_frame = tk.LabelFrame(parent, text=" ESTATÍSTICAS ",
                                    bg=self.PANEL_BG, fg=self.ACCENT2,
                                    font=("Consolas", 9, "bold"), relief="flat",
                                    highlightthickness=1,
                                    highlightbackground=self.ACCENT)
        stats_frame.pack(fill="x", padx=8, pady=8)

        self.stat_vars = {}
        stat_items = [
            ("frame",         "Frame"),
            ("stars",         "Estrelas"),
            ("meteors",       "Meteoros"),
            ("clouds",        "Nuvens"),
            ("triangles",     "Triângulos"),
            ("total_stars",   "Stars salvas"),
            ("total_meteors", "Meteoros det."),
            ("total_clouds",  "Nuvens det."),
        ]
        for key, label in stat_items:
            row = tk.Frame(stats_frame, bg=self.PANEL_BG)
            row.pack(fill="x", padx=6, pady=1)
            tk.Label(row, text=f"{label}:", bg=self.PANEL_BG, fg="#8080b0",
                     font=("Consolas", 8), width=14, anchor="w").pack(side="left")
            var = tk.StringVar(value="—")
            self.stat_vars[key] = var
            tk.Label(row, textvariable=var, bg=self.PANEL_BG, fg=self.ACCENT2,
                     font=("Consolas", 9, "bold")).pack(side="left")

        # Log
        log_frame = tk.LabelFrame(parent, text=" LOG ",
                                  bg=self.PANEL_BG, fg=self.ACCENT2,
                                  font=("Consolas", 9, "bold"), relief="flat",
                                  highlightthickness=1,
                                  highlightbackground=self.ACCENT)
        log_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, bg=self.DARK_BG, fg="#a0a0c0",
            font=("Consolas", 8), relief="flat",
            state="disabled", wrap="word",
            insertbackground=self.TEXT_COLOR)
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

        tk.Button(log_frame, text="Limpar log", command=self._clear_log,
                  bg=self.PANEL_BG, fg="#6060a0", relief="flat",
                  font=("Consolas", 8), cursor="hand2").pack(pady=2)

    # ----------------------------------------------------------
    # LÓGICA DE CONTROLE
    # ----------------------------------------------------------
    def _on_source_change(self):
        st = self.source_type.get()
        self.source_entry.delete(0, "end")
        defaults = {
            "rtsp":   "rtsp://admin:senha@ip:554",
            "device": "0",
            "video":  "",
            "images": "",
        }
        self.source_entry.insert(0, defaults.get(st, ""))

    def _browse_source(self):
        st = self.source_type.get()
        if st == "video":
            path = filedialog.askopenfilename(
                title="Selecionar vídeo",
                filetypes=[("Vídeos", "*.mp4 *.avi *.mkv *.mov *.ts *.flv"), ("Todos", "*.*")])
        elif st == "images":
            path = filedialog.askdirectory(title="Selecionar pasta de imagens")
        else:
            return
        if path:
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Selecionar pasta de saída")
        if path:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, path)

    def _start(self):
        if self.running:
            return

        source_type  = self.source_type.get()
        source_value = self.source_entry.get().strip()
        output_dir   = self.output_entry.get().strip()

        if not source_value:
            messagebox.showwarning("Atenção", "Informe a URL/caminho da fonte.")
            return
        if not output_dir:
            messagebox.showwarning("Atenção", "Informe a pasta de saída.")
            return

        self.stop_event.clear()
        self.proc_thread = ProcessingThread(
            source_type, source_value, output_dir, self.cfg,
            self.frame_queue, self.log_queue, self.stats_queue, self.stop_event,
            self.show_stars, self.show_meteors, self.show_clouds, self.show_triangles
        )
        self.proc_thread.start()
        self.running = True

        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("● RODANDO")
        self.status_lbl.config(fg=self.ACCENT2)
        self.canvas.delete(self._placeholder)
        self._add_log("Iniciado.")

    def _stop(self):
        if not self.running:
            return
        self.stop_event.set()
        self.running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.status_var.set("● PARADO")
        self.status_lbl.config(fg=self.WARN_COLOR)
        self._add_log("Parado pelo usuário.")

    def _open_output_folder(self):
        path = self.output_entry.get().strip() or "dataset_sky_monitor"
        Path(path).mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception:
            messagebox.showinfo("Pasta de saída", str(Path(path).resolve()))

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _add_log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    # ----------------------------------------------------------
    # POLLING
    # ----------------------------------------------------------
    def _poll_frames(self):
        try:
            frame = self.frame_queue.get_nowait()
            self._display_frame(frame)
        except queue.Empty:
            pass
        self.root.after(int(1000 / self.FPS_TARGET), self._poll_frames)

    def _poll_logs(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self._add_log(msg)
        except queue.Empty:
            pass
        self.root.after(200, self._poll_logs)

    def _poll_stats(self):
        try:
            stats = self.stats_queue.get_nowait()
            for key, var in self.stat_vars.items():
                var.set(str(stats.get(key, "—")))
        except queue.Empty:
            pass
        self.root.after(300, self._poll_stats)

    def _display_frame(self, frame_bgr):
        if not HAS_PIL:
            return
        h, w = frame_bgr.shape[:2]
        cw, ch = self._canvas_w, self._canvas_h
        scale  = min(cw / w, ch / h)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(frame_bgr, (nw, nh))
        rgb     = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        img     = Image.fromarray(rgb)
        imgtk   = ImageTk.PhotoImage(image=img)
        self.current_imgtk = imgtk
        x = (cw - nw) // 2
        y = (ch - nh) // 2
        self.canvas.delete("all")
        self.canvas.create_image(x, y, anchor="nw", image=imgtk)

    def _on_canvas_resize(self, event):
        self._canvas_w = event.width
        self._canvas_h = event.height

    # ----------------------------------------------------------
    # SETTINGS DIALOG
    # ----------------------------------------------------------
    def _open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Configurações Avançadas")
        win.configure(bg=self.DARK_BG)
        win.resizable(False, False)

        tk.Label(win, text="CONFIGURAÇÕES AVANÇADAS", bg=self.DARK_BG,
                 fg=self.ACCENT2, font=("Consolas", 11, "bold")).pack(pady=10)

        frame = tk.Frame(win, bg=self.DARK_BG)
        frame.pack(padx=20, pady=4)

        entries = {}
        row = 0
        editable = [
            ("TOP_CROP_PX",           "Corte topo (px)"),
            ("BOTTOM_CROP_PX",        "Corte base (px)"),
            ("MAX_STARS",             "Máx. estrelas"),
            ("SIGMA_FACTOR",          "Fator sigma"),
            ("CONFIDENCE_THRESHOLD",  "Threshold confiança"),
            ("METEOR_MIN_LEN",        "Meteoro comprimento mín."),
            ("METEOR_MIN_ASPECT",     "Meteoro aspecto mín."),
            ("CLOUD_PERCENTILE",      "Nuvem percentil"),
            ("CLOUD_MIN_AREA",        "Nuvem área mín."),
            ("CLOUD_MERGE_DIST",      "Nuvem dist. fusão (px)"),
            ("CONST_NEIGHBORS",       "Triangulação vizinhos"),
            ("CONST_MAX_EDGE",        "Triangulação aresta máx."),
        ]
        for key, label in editable:
            tk.Label(frame, text=label + ":", bg=self.DARK_BG, fg=self.TEXT_COLOR,
                     font=("Consolas", 9), width=28, anchor="w").grid(
                row=row, column=0, sticky="w", pady=2)
            var = tk.StringVar(value=str(self.cfg[key]))
            e = tk.Entry(frame, textvariable=var, bg=self.PANEL_BG, fg=self.TEXT_COLOR,
                         insertbackground=self.TEXT_COLOR, font=("Consolas", 9),
                         width=10, relief="flat",
                         highlightthickness=1, highlightbackground="#333355")
            e.grid(row=row, column=1, sticky="w", padx=8, pady=2, ipady=3)
            entries[key] = var
            row += 1

        def apply():
            for key, var in entries.items():
                try:
                    orig = self.cfg[key]
                    val  = type(orig)(var.get())
                    self.cfg[key] = val
                except ValueError:
                    pass
            win.destroy()
            messagebox.showinfo("Configurações", "Configurações aplicadas.")

        def reset():
            for key, var in entries.items():
                var.set(str(CFG[key]))

        btn_frame = tk.Frame(win, bg=self.DARK_BG)
        btn_frame.pack(pady=12)
        tk.Button(btn_frame, text="Aplicar", command=apply,
                  bg="#1b5e20", fg="white", relief="flat",
                  font=("Consolas", 10, "bold"), cursor="hand2", padx=16, pady=6).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Restaurar padrão", command=reset,
                  bg=self.ACCENT, fg="white", relief="flat",
                  font=("Consolas", 10), cursor="hand2", padx=12, pady=6).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Fechar", command=win.destroy,
                  bg="#37373f", fg=self.TEXT_COLOR, relief="flat",
                  font=("Consolas", 10), cursor="hand2", padx=12, pady=6).pack(side="left", padx=6)

    def _on_close(self):
        self._stop()
        time.sleep(0.3)
        self.root.destroy()


# ==========================================================
# ENTRY POINT
# ==========================================================
def main():
    root = tk.Tk()
    root.protocol("WM_DELETE_WINDOW", lambda: app._on_close())

    # Ícone (apenas Windows, ignora em outros SOs)
    try:
        root.iconbitmap("sky_monitor.ico")
    except Exception:
        pass

    app = SkyMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()