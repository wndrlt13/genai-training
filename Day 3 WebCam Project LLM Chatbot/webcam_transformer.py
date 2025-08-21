import cv2
import numpy as np
from datetime import datetime
import os

#---------------------------------------
# Utility: Generate timestamped strings for filenames
#---------------------------------------
def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

#---------------------------------------
# Utility: Draw a simple Heads-Up Display (HUD) bar with text
#---------------------------------------
def hud(img, text):
    out = img.copy()
    if out.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    cv2.rectangle(out, (0, 0), (out.shape[1], 28), (0, 0, 0), -1)
    cv2.putText(out, text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 
                0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return out

#---------------------------------------
# Map numeric mode -> human-readable name
#---------------------------------------
def mode_name(m):
    name = {
        0: "Original",
        1: "Grayscale",
        2: "Gaussian_Blur",
        3: "Median_Blur",
        4: "Canny_Edges",
        5: "Sobel_Magnitude",
        6: "Sharpen"
    }
    return name.get(m, "Original")

#---------------------------------------
# Core image processing function
#----------------------------------------
def apply_transform(mode, frame_bgr):
    if mode == 0:  # Original
        return frame_bgr, frame_bgr
    
    if mode == 1:  # Grayscale
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        return gray, gray

    if mode == 2:  # Gaussian Blur
        g = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gb = cv2.GaussianBlur(g, (7, 7), 1.4)
        return gb, gb

    if mode == 3:  # Median Blur
        g = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        mb = cv2.medianBlur(g, 5)
        return mb, mb

    if mode == 4:  # Canny Edges
        g = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(g, 80, 160)
        return edges, edges

    if mode == 5:  # Sobel Magnitude
        g = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        sx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
        sy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(sx, sy)
        mmax = np.max(mag) if mag.size else 0.0
        if mmax > 1e-6:
            mag = (mag / mmax) * 255.0
        mag = np.clip(mag, 0, 255).astype(np.uint8)
        return mag, mag

    if mode == 6:  # Sharpen
        kernel = np.array([[0, -1, 0],
                           [-1, 5, -1],
                           [0, -1, 0]], dtype=np.float32)
        shp = cv2.filter2D(frame_bgr, -1, kernel)
        return shp, shp

    return frame_bgr, frame_bgr

#---------------------------------------
# Main loop: webcam capture and processing
#---------------------------------------
def main(cam_index=0, width=1280, height=720):
    cap = cv2.VideoCapture(cam_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    if not cap.isOpened():
        print("Error: Could not open webcam. Try cam_index=1.")
        return

    os.makedirs("captures", exist_ok=True)

    print("""
Controls:
0: Original
1: Grayscale    2: Gaussian Blur    3: Median Blur
4: Canny Edges  5: Sobel Magnitude  6: Sharpen
c: Capture image
q: Quit
""")

    mode = 1  # Start with Grayscale
    win = "Webcam Transformer (press 0-6 to change mode)"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    try:
        while True:
            ret, frame_bgr = cap.read()
            if not ret:
                print("Warning: Failed to read frame from webcam.")
                continue

            # Use frame_bgr instead of undefined `frame`
            processed, save_img = apply_transform(mode, frame_bgr)

            txt = f"{mode_name(mode)} | keys: 0..6 modes, c=capture, q=quit"
            disp = hud(processed, txt)

            # Ensure disp_bgr is defined
            if disp.ndim == 2:
                disp_bgr = cv2.cvtColor(disp, cv2.COLOR_GRAY2BGR)
            else:
                disp_bgr = disp

            cv2.imshow(win, disp_bgr)

            k = cv2.waitKey(1) & 0xFF
            if k == ord('q'):
                break
            elif k == ord('c'):
                fname = f"captures/{timestamp()}_{mode_name(mode)}.png"
                cv2.imwrite(fname, save_img)
                print("Saved:", fname)
            elif k in [ord(str(i)) for i in range(7)]:
                mode = int(chr(k))
    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        cv2.destroyAllWindows()

#---------------------------------------
# Entry Point
#---------------------------------------
if __name__ == "__main__":
    main(cam_index=0, width=1280, height=720)