try:
    import av
    print("✅ av imported successfully")
except ImportError as e:
    print(f"❌ av import failed: {e}")

try:
    import cv2
    print("✅ cv2 imported successfully")
except ImportError as e:
    print(f"❌ cv2 import failed: {e}")

try:
    from streamlit_webrtc import webrtc_streamer
    print("✅ streamlit_webrtc imported successfully")
except ImportError as e:
    print(f"❌ streamlit_webrtc import failed: {e}")
