import math
from typing import List, Dict, Any, Optional
from detection.multimodal.schemas import MultimodalCandidateItem


def compute_bbox_geometry(bbox: List[float]) -> Dict[str, float]:
    """Calculate normalized geometric layout features from [x1, y1, x2, y2]."""
    if not bbox or len(bbox) != 4:
        return {
            "width": 1.0, "height": 0.05, "area": 0.05, "aspect_ratio": 20.0,
            "center_x": 0.5, "center_y": 0.5, "is_header_region": 0.0,
            "is_footer_region": 0.0, "is_left_margin": 0.0, "is_right_margin": 0.0
        }

    x1, y1, x2, y2 = bbox
    width = max(0.0, x2 - x1)
    height = max(0.0, y2 - y1)
    area = width * height
    aspect_ratio = width / (height + 1e-5)
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0

    return {
        "width": round(width, 4),
        "height": round(height, 4),
        "area": round(area, 4),
        "aspect_ratio": round(min(50.0, aspect_ratio), 4),
        "center_x": round(center_x, 4),
        "center_y": round(center_y, 4),
        "is_header_region": 1.0 if center_y < 0.15 else 0.0,
        "is_footer_region": 1.0 if center_y > 0.85 else 0.0,
        "is_left_margin": 1.0 if center_x < 0.30 else 0.0,
        "is_right_margin": 1.0 if center_x > 0.70 else 0.0,
    }


def compute_neighbor_layout_relationships(
    target_item: MultimodalCandidateItem,
    all_items: List[MultimodalCandidateItem],
    max_radius: float = 0.35
) -> Dict[str, float]:
    """
    Analyze spatial relationships between target item and neighboring blocks:
    - Distance to nearest block
    - Nearby block density
    - Horizontal/vertical alignment indicators
    - Label-value proximity patterns
    """
    t_geom = compute_bbox_geometry(target_item.bbox)
    tx, ty = t_geom["center_x"], t_geom["center_y"]

    distances = []
    has_left_neighbor = 0.0
    has_top_neighbor = 0.0
    horizontally_aligned_count = 0
    vertically_aligned_count = 0

    x1, y1, x2, y2 = target_item.bbox if len(target_item.bbox) == 4 else [0.0, 0.0, 1.0, 1.0]

    for other in all_items:
        if other.block_id == target_item.block_id:
            continue
        if other.page_or_slide != target_item.page_or_slide:
            continue

        o_geom = compute_bbox_geometry(other.bbox)
        ox, oy = o_geom["center_x"], o_geom["center_y"]
        dist = math.sqrt((tx - ox) ** 2 + (ty - oy) ** 2)

        if dist <= max_radius:
            distances.append(dist)

            ox1, oy1, ox2, oy2 = other.bbox if len(other.bbox) == 4 else [0.0, 0.0, 1.0, 1.0]

            # Horizontal alignment: vertical overlap
            v_overlap = max(0.0, min(y2, oy2) - max(y1, oy1))
            if v_overlap > 0.0:
                horizontally_aligned_count += 1
                # Left neighbor (Label -> Value candidate)
                if ox2 <= x1 + 0.05 and (x1 - ox2) < 0.25:
                    has_left_neighbor = 1.0

            # Vertical alignment: horizontal overlap
            h_overlap = max(0.0, min(x2, ox2) - max(x1, ox1))
            if h_overlap > 0.0:
                vertically_aligned_count += 1
                # Top neighbor (Header -> Cell candidate)
                if oy2 <= y1 + 0.05 and (y1 - oy2) < 0.20:
                    has_top_neighbor = 1.0

    nearest_dist = min(distances) if distances else 1.0

    return {
        "nearby_block_count": float(len(distances)),
        "nearest_block_distance": round(nearest_dist, 4),
        "has_left_neighbor": has_left_neighbor,
        "has_top_neighbor": has_top_neighbor,
        "horizontally_aligned_count": float(horizontally_aligned_count),
        "vertically_aligned_count": float(vertically_aligned_count),
    }


def extract_layout_features(
    target_item: MultimodalCandidateItem,
    all_items: Optional[List[MultimodalCandidateItem]] = None
) -> Dict[str, float]:
    """Aggregate all geometric and relative layout features into a flat feature map."""
    features = {}
    features.update(compute_bbox_geometry(target_item.bbox))

    if all_items:
        features.update(compute_neighbor_layout_relationships(target_item, all_items))
    else:
        features.update({
            "nearby_block_count": 0.0,
            "nearest_block_distance": 1.0,
            "has_left_neighbor": 0.0,
            "has_top_neighbor": 0.0,
            "horizontally_aligned_count": 0.0,
            "vertically_aligned_count": 0.0,
        })

    return features
