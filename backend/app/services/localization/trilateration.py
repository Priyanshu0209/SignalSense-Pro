import numpy as np
import logging
from typing import List, Tuple, Dict, Optional

logger = logging.getLogger("signalsense.localization.trilateration")

def solve_trilateration(anchors: List[Tuple[float, float]], distances: List[float]) -> Optional[Tuple[float, float]]:
    """
    Calculates the 2D (x, y) coordinates of a target using trilateration (Least Squares).
    
    Args:
        anchors: A list of (x, y) tuples representing the Access Point locations.
        distances: A list of floats representing the estimated radial distance to each anchor.
                   The indices must correspond exactly to the anchors array.
                   
    Returns:
        (x, y) tuple representing the best-fit position, or None if the calculation fails.
    """
    if len(anchors) < 3 or len(distances) < 3:
        logger.error("Trilateration requires at least 3 anchor points and 3 distances.")
        return None
        
    if len(anchors) != len(distances):
        logger.error("Number of anchors must match number of distances.")
        return None

    try:
        # We use a Linear Least Squares approach by subtracting the last anchor's equation
        # from all other anchors' equations to eliminate the x^2 + y^2 non-linear terms.
        
        n = len(anchors)
        A = []
        b = []
        
        # We will use the last anchor (n-1) as the reference point
        ref_x, ref_y = anchors[-1]
        ref_d = distances[-1]
        
        for i in range(n - 1):
            x_i, y_i = anchors[i]
            d_i = distances[i]
            
            # A matrix: 2(x_n - x_i) , 2(y_n - y_i)
            A.append([2 * (ref_x - x_i), 2 * (ref_y - y_i)])
            
            # b vector: r_i^2 - r_n^2 - x_i^2 + x_n^2 - y_i^2 + y_n^2
            val = (d_i**2 - ref_d**2) - (x_i**2 - ref_x**2) - (y_i**2 - ref_y**2)
            b.append(val)
            
        A_mat = np.array(A)
        b_vec = np.array(b)
        
        # Solve Ax = b
        ans, residuals, rank, s = np.linalg.lstsq(A_mat, b_vec, rcond=None)
        
        # ans contains the estimated (x, y)
        return float(ans[0]), float(ans[1])
        
    except Exception as e:
        logger.error(f"Mathematical error during trilateration: {e}")
        return None
