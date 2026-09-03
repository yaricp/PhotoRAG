# Third-Party Notices — PhotoRAG

PhotoRAG includes or depends upon the following third-party software components.
Each component is listed with its license and copyright holder.

---

## ⚠️  IMPORTANT: Non-Commercial Model Notice

### facebook/nllb-200-distilled-600M

| Field       | Value |
|-------------|-------|
| Purpose     | Default local translation model |
| License     | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) |
| Copyright   | Meta AI (Facebook, Inc.) |
| Source      | https://huggingface.co/facebook/nllb-200-distilled-600M |

**This model is licensed for NON-COMMERCIAL USE ONLY.**  
Using PhotoRAG with the default NLLB-200 translation model in a commercial context
violates the CC BY-NC 4.0 terms imposed by Meta AI.

For commercial deployments, replace NLLB-200 with a permissively-licensed
alternative such as a remote OpenAI / Google Translate / Anthropic API,
or a self-hosted Ollama model with a compatible license.

### Qwen/Qwen2.5-Coder-3B-Instruct

| Field       | Value |
|-------------|-------|
| Purpose     | Default local code/text generation model (agent tools) |
| License     | [Qwen RESEARCH LICENSE AGREEMENT](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct/blob/main/LICENSE) |
| Copyright   | Alibaba Cloud / Tongyi Qianwen |
| Source      | https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct |

**This model is licensed for NON-COMMERCIAL USE ONLY.**  
Commercial applications require separate written permission from Alibaba Cloud —
there is no monthly-active-user threshold that permits commercial use, unlike
some other Qwen-family models.

For commercial deployments, replace this model with a permissively-licensed
alternative such as a remote OpenAI / Anthropic / Google API, or a self-hosted
Ollama model with a compatible license.

---

## AI / ML Models

### Qwen2-VL-2B-Instruct

| Field       | Value |
|-------------|-------|
| Purpose     | Vision-language model for photo description |
| License     | [Apache 2.0](https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct/blob/main/LICENSE) |
| Copyright   | Alibaba Cloud / Tongyi Qianwen |
| Source      | https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct |

Fully permissive: commercial use, modification, and redistribution are allowed.

### Qwen2.5-Coder-3B-Instruct

Non-commercial only — see the "IMPORTANT: Non-Commercial Model Notice" section
at the top of this file for full license details.

### CLIP (open_clip_torch / OpenCLIP)

| Field       | Value |
|-------------|-------|
| Purpose     | Image embeddings for visual search |
| License     | MIT |
| Copyright   | LAION e.V. and contributors |
| Source      | https://github.com/mlfoundations/open_clip |

---

## Python Backend Libraries

### PyTorch (torch, torchvision)

| License | BSD-3-Clause |
|---------|--------------|
| Copyright | Meta AI (Facebook, Inc.) and contributors |
| Source | https://github.com/pytorch/pytorch |

### Transformers (Hugging Face)

| License | Apache 2.0 |
|---------|------------|
| Copyright | Hugging Face, Inc. |
| Source | https://github.com/huggingface/transformers |

### LangChain / LangGraph

| License | MIT |
|---------|-----|
| Copyright | LangChain, Inc. |
| Source | https://github.com/langchain-ai/langchain |

### sentence-transformers

| License | Apache 2.0 |
|---------|------------|
| Copyright | Nils Reimers and contributors |
| Source | https://github.com/UKPLab/sentence-transformers |

### accelerate

| License | Apache 2.0 |
|---------|------------|
| Copyright | Hugging Face, Inc. |
| Source | https://github.com/huggingface/accelerate |

### EasyOCR

| License | Apache 2.0 |
|---------|------------|
| Copyright | Jaided AI |
| Source | https://github.com/JaidedAI/EasyOCR |

### python-bidi (EasyOCR dependency)

| License | GNU Lesser General Public License v2.1 or later (LGPL-2.1+) |
|---------|---------------------------------------------------------------|
| Copyright | Meir kriheli and contributors |
| Source | https://github.com/MeirKriheli/python-bidi |

Used unmodified as a standard Python library dependency (imported, not statically
linked into a single binary), which satisfies LGPL's relinking requirement.

### FastAPI

| License | MIT |
|---------|-----|
| Copyright | Sebastián Ramírez |
| Source | https://github.com/tiangolo/fastapi |

### Uvicorn

| License | BSD-3-Clause |
|---------|--------------|
| Copyright | Tom Christie and contributors |
| Source | https://github.com/encode/uvicorn |

### SQLAlchemy

| License | MIT |
|---------|-----|
| Copyright | Mike Bayer and contributors |
| Source | https://github.com/sqlalchemy/sqlalchemy |

### sqlite-vec

| License | MIT (core) / Apache 2.0 (some components) |
|---------|-------------------------------------------|
| Copyright | Alex Garcia |
| Source | https://github.com/asg017/sqlite-vec |

### Pydantic / pydantic-settings

| License | MIT |
|---------|-----|
| Copyright | Samuel Colvin and contributors |
| Source | https://github.com/pydantic/pydantic |

### Pillow (PIL Fork)

| License | Historical Permission Notice and Disclaimer (HPND) |
|---------|-----------------------------------------------------|
| Copyright | Jeffrey A. Clark (Alex) and contributors |
| Source | https://github.com/python-pillow/Pillow |

### Watchdog

| License | Apache 2.0 |
|---------|------------|
| Copyright | Yesudeep Mangalapilly and contributors |
| Source | https://github.com/gorakhargosh/watchdog |

### Huey

| License | MIT |
|---------|-----|
| Copyright | Charles Leifer |
| Source | https://github.com/coleifer/huey |

### exifread

| License | BSD-3-Clause |
|---------|--------------|
| Copyright | Ianaré Sévi and contributors |
| Source | https://github.com/ianare/exif-py |

### geopy

| License | MIT |
|---------|-----|
| Copyright | geopy contributors |
| Source | https://github.com/geopy/geopy |

### einops

| License | MIT |
|---------|-----|
| Copyright | Alex Rogozhnikov |
| Source | https://github.com/arogozhnikov/einops |

### imagehash

| License | BSD-2-Clause |
|---------|--------------|
| Copyright | Johannes Buchner |
| Source | https://github.com/JohannesBuchner/imagehash |

### loguru

| License | MIT |
|---------|-----|
| Copyright | Delgan |
| Source | https://github.com/Delgan/loguru |

### pgvector (Python client)

| License | MIT |
|---------|-----|
| Copyright | Andrew Kane |
| Source | https://github.com/pgvector/pgvector-python |

### langchain-openai

| License | MIT |
|---------|-----|
| Copyright | LangChain, Inc. |
| Source | https://github.com/langchain-ai/langchain |

### qwen-vl-utils

| License | Apache 2.0 |
|---------|------------|
| Copyright | Qwen Team, Alibaba Cloud |
| Source | https://github.com/QwenLM/Qwen2-VL |

---

## Frontend / Electron Libraries

### Electron

| License | MIT |
|---------|-----|
| Copyright | OpenJS Foundation and Electron contributors |
| Source | https://github.com/electron/electron |

### React / React DOM

| License | MIT |
|---------|-----|
| Copyright | Meta Platforms, Inc. and affiliates |
| Source | https://github.com/facebook/react |

### React Router

| License | MIT |
|---------|-----|
| Copyright | Remix Software, Inc. |
| Source | https://github.com/remix-run/react-router |

### i18next / react-i18next

| License | MIT |
|---------|-----|
| Copyright | i18next contributors |
| Source | https://github.com/i18next/i18next |

### Zustand

| License | MIT |
|---------|-----|
| Copyright | Paul Henschel (pmndrs) and contributors |
| Source | https://github.com/pmndrs/zustand |

### Heroicons

| License | MIT |
|---------|-----|
| Copyright | Tailwind Labs, Inc. |
| Source | https://github.com/tailwindlabs/heroicons |

### Vite / electron-vite

| License | MIT |
|---------|-----|
| Copyright | Evan You and Vite contributors / Alex Wei |
| Source | https://github.com/vitejs/vite |

### electron-builder

| License | MIT |
|---------|-----|
| Copyright | Develar and contributors |
| Source | https://github.com/electron-userland/electron-builder |

### @electron-toolkit

| License | MIT |
|---------|-----|
| Copyright | Alex Wei |
| Source | https://github.com/alex8088/electron-toolkit |

### TypeScript

| License | Apache 2.0 |
|---------|------------|
| Copyright | Microsoft Corporation |
| Source | https://github.com/microsoft/TypeScript |

---

## Bundled Runtime

### Python (python-build-standalone)

| License | Python Software Foundation License 2.0 (PSF-2.0) |
|---------|---------------------------------------------------|
| Copyright | Python Software Foundation |
| Source | https://github.com/astral-sh/python-build-standalone |

The bundled Python runtime is provided by the
[python-build-standalone](https://github.com/astral-sh/python-build-standalone) project
(Astral Software Inc., Apache 2.0 build tooling). The Python interpreter itself
is governed by the PSF-2.0 license.

---

## User-Selected and Self-Downloaded Models

PhotoRAG lets you choose, per pipeline stage, which AI model to run — one of the
bundled local defaults listed above, a locally-installed model of your own
choosing (e.g. via Ollama), or a remote provider API (OpenAI, Anthropic, Google,
and others supported by LangChain's `init_chat_model`). This is configured
through Settings / the setup wizard and stored in the `ai_model_configs` table
(`backend/src/config.py`).

**PhotoRAG's MIT license covers only the PhotoRAG application code.** It does not
grant, extend, or otherwise affect the license of any model weights. When you
select or download a model yourself — whether swapping a bundled default for a
newer version, or pointing PhotoRAG at any other local or remote model — **you
are solely responsible for reviewing and complying with that model's own license
terms**, including any restrictions on commercial use, redistribution, or
attribution. The notices in this document describe only the specific model
versions PhotoRAG bundles or recommends as of the date below; they do not cover
models you configure independently, and PhotoRAG's maintainers make no
representation about the licensing of any model not listed here.

As PhotoRAG's bundled default models are updated in future releases, this file
will be updated to reflect the license of whatever ships as the new default.

---

*This file was last updated: September 2026.*  
*For the most current license information for each package, refer to the  
source repository or the package metadata distributed with each release.*
