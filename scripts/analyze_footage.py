import cv2
import numpy as np
import os
import sys

def analyze_frame(file_path):
    if not os.path.exists(file_path):
        return {"error": f"File {file_path} does not exist"}

    img = cv2.imread(file_path)
    if img is None:
        return {"error": f"Failed to decode image {file_path}"}

    h, w, c = img.shape
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Brightness and contrast
    mean_brightness = float(np.mean(gray))
    std_contrast = float(np.std(gray))
    
    # Edge density (indicates visual complexity, circuit geometry, telemetry text)
    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.sum(edges > 0) / (h * w))
    
    # Color distribution (Check for Sepang Petronas cyan / emerald presence)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Cyan/Teal range: H between 80 and 95
    cyan_mask = cv2.inRange(hsv, np.array([80, 50, 50]), np.array([100, 255, 255]))
    cyan_ratio = float(np.sum(cyan_mask > 0) / (h * w))

    return {
        "file": os.path.basename(file_path),
        "dimensions": f"{w}x{h}",
        "mean_brightness": round(mean_brightness, 2),
        "contrast_std": round(std_contrast, 2),
        "edge_density_pct": round(edge_density * 100, 2),
        "petronas_cyan_pct": round(cyan_ratio * 100, 2),
        "status": "PASS" if std_contrast > 25 and edge_density > 0.01 else "WARN"
    }

def main():
    rec_dir = "recordings"
    if not os.path.exists(rec_dir):
        print(f"Recordings directory '{rec_dir}' not found.")
        sys.exit(1)

    files = sorted([os.path.join(rec_dir, f) for f in os.listdir(rec_dir) if f.endswith(".png")])
    if not files:
        print("No recorded frames found in recordings/.")
        sys.exit(1)

    print("=" * 60)
    print("SEPANG PIT WALL — FOOTAGE QUALITY & TELEMETRY ANALYSIS")
    print("=" * 60)

    all_passed = True
    for f in files:
        res = analyze_frame(f)
        print(f"Frame: {res.get('file')}")
        print(f"  Dimensions: {res.get('dimensions')} | Brightness: {res.get('mean_brightness')} | Contrast: {res.get('contrast_std')}")
        print(f"  Edge Density: {res.get('edge_density_pct')}% | Sepang Cyan: {res.get('petronas_cyan_pct')}% | Status: {res.get('status')}")
        if res.get('status') != "PASS":
            all_passed = False

    print("=" * 60)
    print(f"Overall Footage Assessment: {'ALL FRAMES PASSED QUALITY CHECKS' if all_passed else 'SOME FRAMES NEED REFINEMENT'}")
    print("=" * 60)

if __name__ == "__main__":
    main()