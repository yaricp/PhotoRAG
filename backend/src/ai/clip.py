import open_clip
import torch
import csv
import numpy as np
import os
import requests

class ClipTagger:
    # Use environment-aware paths
    CSV_PATH = "class-descriptions-boxable.csv"
    NPY_PATH = "tags_features.npy"
    TAGS_LIST_PATH = "tags_list.txt"
    VOCAB_URL = "https://storage.googleapis.com/openimages/v7/class-descriptions-boxable.csv"

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
        """Downloads the Open Images CSV and returns normalized tags."""
        print(f"Downloading Open Images Vocabulary from {self.VOCAB_URL}...")
        response = requests.get(self.VOCAB_URL)
        if response.status_code == 200:
            with open(self.CSV_PATH, "w") as f:
                f.write(response.text)
        
        tags = []
        with open(self.CSV_PATH, "r") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) > 1:
                    tags.append(row[1])
        
        normalized = self._normalize_tags(tags)
        # Save tags list for reference
        with open(self.TAGS_LIST_PATH, "w") as f:
            for t in normalized:
                f.write(f"{t}\n")
        
        return normalized

    def compute_embeddings(self, tags: list[str]):
        """Runs CLIP text encoder and saves features to NPY."""
        self.load()
        print(f"Computing embeddings for {len(tags)} tags...")
        
        # Batch processing to avoid OOM
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
        print(f"Saved {self.tags_features.shape} embeddings to {self.NPY_PATH}")

    def download(self):
        """Full bootstrap process: Models -> CSV -> NPY."""
        # 1. Download Model Weights
        open_clip.create_model_and_transforms(self.model_name, self.pretrained)
        
        # 2. Vocabulary
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

    def generate_keywords(self, filepath: str, top_k=5) -> list[str]:
        """Zero-Shot classification against cached vocabulary."""
        from PIL import Image
        self.load()
        
        if self.tags_features is None or not self.tags:
            return ["error: vocabulary not initialized"]

        image = self.preprocess(Image.open(filepath)).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            image_features = self.model.encode_image(image)
            img_norm = image_features.norm(dim=-1, keepdim=True)
            image_features = image_features / img_norm
            
            # Cosine Similarity (Dot product since normalized)
            similarities = (image_features.cpu().numpy() @ self.tags_features.T).squeeze()
            
            top_indices = similarities.argsort()[-top_k:][::-1]
            return [self.tags[i] for i in top_indices]
