from ultralytics import YOLO


class PestClassifier:
    def __init__(self, model_path: str):
        self.model = YOLO(model_path)

    @property
    def class_names(self) -> dict:
        return self.model.names

    def predict(self, img_path: str) -> dict | None:
        """
        이미지 경로를 받아 가장 높은 신뢰도의 탐지 결과를 반환.
        탐지 결과가 없으면 None 반환.
        """
        results = self.model(img_path, conf=0.4, verbose=False)
        boxes = results[0].boxes

        if not boxes:
            return None

        best = max(boxes, key=lambda b: float(b.conf))
        pest_code = self.model.names[int(best.cls)]

        return {
            "pest_code": pest_code,
            "confidence": round(float(best.conf), 3),
        }
