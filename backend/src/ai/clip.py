import open_clip
import torch
import csv
import numpy as np
import os
import requests
from loguru import logger

class ClipTagger:
    CSV_PATH = "data/class-descriptions-boxable.csv"
    NPY_PATH = "data/tags_features.npy"
    TAGS_LIST_PATH = "data/tags_list.txt"
    VOCAB_URL = "https://storage.googleapis.com/openimages/v7/oidv7-class-descriptions-boxable.csv"

    def __init__(self):
        self.model_name = "ViT-B-32"
        self.pretrained = "laion2b_s34b_b79k"
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.preprocess = None
        self.tags_features = None
        self.tags = []

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        return list(set(t.lower().strip() for t in tags if t.strip()))

    def download_vocabulary(self) -> list[str]:
        os.makedirs(os.path.dirname(self.CSV_PATH), exist_ok=True)
        logger.info(f"Downloading Open Images Vocabulary from {self.VOCAB_URL}...")
        try:
            response = requests.get(self.VOCAB_URL)
            logger.info(f"Response: {response}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to download vocabulary: {e}")
            raise Exception(f"Failed to download vocabulary: {e}")
        if response.status_code == 200:
            try:
                with open(self.CSV_PATH, "w") as f:
                    f.write(response.text)
                logger.info(f"Vocabulary saved to {self.CSV_PATH}")
            except Exception as e:
                logger.error(f"Failed to save vocabulary: {e}")
                raise Exception(f"Failed to save vocabulary: {e}")
        else:
            logger.error(f"Failed to download vocabulary: {response.status_code}")
            raise Exception(f"Failed to download vocabulary: {response.status_code}")
        
        tags = []
        with open(self.CSV_PATH, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) > 1:
                    tags.append(row[1])
        
        normalized = self._normalize_tags(tags)
        with open(self.TAGS_LIST_PATH, "w") as f:
            for t in normalized:
                f.write(f"{t}\n")
        logger.info("Vocabulary downloaded and normalized.")
        return normalized

    def compute_embeddings(self, tags: list[str]):
        self.load()
        logger.info(f"Computing embeddings for {len(tags)} tags...")
        batch_size = 128
        all_features = []
        
        with torch.no_grad():
            for i in range(0, len(tags), batch_size):
                batch = tags[i:i+batch_size]
                tokens = open_clip.tokenize(batch).to(self.device)
                features = self.model.encode_text(tokens)
                norm = features.norm(dim=-1, keepdim=True)
                features = features / norm
                all_features.append(features.detach().cpu().numpy())
        
        self.tags_features = np.concatenate(all_features, axis=0)
        np.save(self.NPY_PATH, self.tags_features)

    def download(self):
        open_clip.create_model_and_transforms(self.model_name, self.pretrained)
        if not os.path.exists(self.NPY_PATH):
            tags = self.download_vocabulary()
            self.compute_embeddings(tags)

    def load(self):
        if not self.model:
            self.model, _, self.preprocess = open_clip.create_model_and_transforms(
                self.model_name, self.pretrained, device=self.device
            )
            self.model.eval()
            
        if self.tags_features is None and os.path.exists(self.NPY_PATH):
            self.tags_features = np.load(self.NPY_PATH)
        
        if not self.tags and os.path.exists(self.TAGS_LIST_PATH):
            with open(self.TAGS_LIST_PATH, "r") as f:
                self.tags = [line.strip() for line in f]

    def find_tags(self, filepath: str, top_k=20) -> list[tuple[str, float]]:
        from PIL import Image
        self.load()
        if self.tags_features is None or not self.tags:
            return []
        image = self.preprocess(Image.open(filepath)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            image_features = self.model.encode_image(image)
            img_norm = image_features.norm(dim=-1, keepdim=True)
            image_features = image_features / img_norm
            similarities = (image_features.cpu().numpy() @ self.tags_features.T).squeeze()
            top_indices = similarities.argsort()[-top_k:][::-1]
            return [(self.tags[i], float(similarities[i])) for i in top_indices]

    def categorize(self, filepath: str, categories: list[str]) -> list[tuple[str, float]]:
        """Dynamic Zero-Shot categorization against custom category list."""
        from PIL import Image
        if not categories:
            return []
        self.load()
        image = self.preprocess(Image.open(filepath)).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            # 1. Encode Image
            image_features = self.model.encode_image(image)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            
            # 2. Encode Categories (On-the-fly)
            tokens = open_clip.tokenize(categories).to(self.device)
            text_features = self.model.encode_text(tokens)
            text_features /= text_features.norm(dim=-1, keepdim=True)
            
            # 3. Compare
            similarities = (image_features.cpu().numpy() @ text_features.cpu().numpy().T).squeeze()
            
            # Handles single category edge case
            if len(categories) == 1:
                return [(categories[0], float(similarities))]
                
            # Return sorted results
            results = [(categories[i], float(similarities[i])) for i in range(len(categories))]
            return sorted(results, key=lambda x: x[1], reverse=True)
