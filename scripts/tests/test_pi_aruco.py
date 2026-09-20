import cv2
print('OpenCV Version:', cv2.__version__)
print('Has aruco:', hasattr(cv2, 'aruco'))
if hasattr(cv2, 'aruco'):
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50) if hasattr(cv2.aruco, 'getPredefinedDictionary') else cv2.aruco.Dictionary_get(cv2.aruco.DICT_4X4_50)
    print('Aruco dict loaded successfully!')
    if hasattr(cv2.aruco, 'drawMarker'):
        m = cv2.aruco.drawMarker(aruco_dict, 1, 100)
        print('drawMarker available, shape:', m.shape)
    elif hasattr(aruco_dict, 'generateImageMarker'):
        m = aruco_dict.generateImageMarker(1, 100)
        print('generateImageMarker available, shape:', m.shape)
