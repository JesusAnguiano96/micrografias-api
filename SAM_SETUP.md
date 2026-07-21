# ConfiguraciÃ³n de SAM clÃ¡sico para el backend

Este documento describe cÃ³mo preparar el ambiente local para ejecutar el modelo
SAM clÃ¡sico dentro del backend Flask del sistema de anÃ¡lisis de micrografÃ­as.

El flujo documentado corresponde al modelo usado en el prototipo base:

- Modelo: Segment Anything Model clÃ¡sico
- Variante: ViT-H
- Checkpoint: `sam_vit_h_4b8939.pth`
- Backend: Flask
- Entorno recomendado: Conda + Python 3.10
- GPU probada: NVIDIA GeForce RTX 4060

---

## 1. Activar el ambiente de backend

Desde la carpeta `apiMAS`:

```powershell
conda activate tesis-mas-api
```

Si el ambiente no existe, crearlo con:

```powershell
conda create -n tesis-mas-api python=3.10
conda activate tesis-mas-api
pip install -r requirements.txt
```

---

## 2. Verificar GPU NVIDIA

Ejecutar:

```powershell
nvidia-smi
```

Si el comando muestra informaciÃ³n de la GPU, entonces el equipo tiene una GPU NVIDIA disponible.

En el equipo de prueba se obtuvo una GPU NVIDIA GeForce RTX 4060.

---

## 3. Instalar PyTorch con CUDA

Para Windows + pip + CUDA 12.4 se usÃ³:

```powershell
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

Verificar instalaciÃ³n:

```powershell
python -c "import torch; import torchvision; print('torch:', torch.__version__); print('torchvision:', torchvision.__version__); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

Salida esperada:

```text
CUDA available: True
GPU: NVIDIA GeForce RTX 4060 ...
```

---

## 4. Instalar dependencias de procesamiento de imÃ¡genes

```powershell
python -m pip install opencv-python matplotlib numpy pillow
```

---

## 5. Instalar Segment Anything

```powershell
python -m pip install git+https://github.com/facebookresearch/segment-anything.git
```

Verificar dependencias:

```powershell
python -c "import cv2; import matplotlib; import numpy; import PIL; import torch; import torchvision; import segment_anything; print('SAM dependencies OK')"
```

Salida esperada:

```text
SAM dependencies OK
```

---

## 6. Descargar checkpoint ViT-H

Crear carpeta de checkpoints si no existe:

```powershell
New-Item -ItemType Directory -Force checkpoints
```

Descargar el checkpoint oficial ViT-H:

```powershell
Invoke-WebRequest `
  -Uri "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth" `
  -OutFile ".\checkpoints\sam_vit_h_4b8939.pth"
```

Verificar que el archivo exista:

```powershell
Get-ChildItem .\checkpoints -File | Select-Object Name, Length
```

Debe aparecer:

```text
sam_vit_h_4b8939.pth
```

---

## 7. Importante: no subir el checkpoint a GitHub

El archivo `.pth` es pesado y no debe subirse al repositorio.

El `.gitignore` debe incluir:

```gitignore
# Model checkpoints
checkpoints/*
!checkpoints/.gitkeep
```

Para verificar que Git lo ignora:

```powershell
git check-ignore -v .\checkpoints\sam_vit_h_4b8939.pth
```

---

## 8. Probar SAM clÃ¡sico desde script modular

El script de prueba modular es:

```text
tools/test_legacy_sam_module.py
```

Ejemplo de ejecuciÃ³n:

```powershell
python tools\test_legacy_sam_module.py `
  --image "C:\Users\jesus\Downloads\micrografia_prueba.tif" `
  --checkpoint ".\checkpoints\sam_vit_h_4b8939.pth" `
  --factor 5.95
```

Salidas esperadas en:

```text
outputs/sam_legacy/
```

Archivos generados:

```text
micrografia_prueba_sam_legacy_annotated.png
micrografia_prueba_sam_legacy_summary.png
micrografia_prueba_sam_legacy_metrics.json
```

La imagen anotada contiene:

- bounding boxes
- diagonales verdes
- partÃ­culas detectadas

La figura resumen contiene:

- micrografÃ­a anotada
- grÃ¡fica de Ã¡reas
- grÃ¡fica de longitudes

El archivo JSON contiene:

- `particle_count`
- `total_masks`
- `valid_masks`
- `rejected_masks`
- `areas_nm2`
- `diagonals_nm`
- distribuciones de Ã¡rea y longitud

---

## 9. Probar SAM desde el endpoint del backend

Primero correr Flask:

```powershell
python run.py
```

Luego probar el endpoint:

```powershell
$body = @{
    micrograph_id = 1
    user_id = 1
    model_name = "SAM"
    parameters = @{
        points_per_side = 44
        pred_iou_thresh = 0.85
        stability_score_thresh = 0.97
        crop_n_layers = 1
        crop_n_points_downscale_factor = 2
        min_mask_region_area = 1000
        factor = 5.95
        step_number = 10
        pixel_threshold = 140
    }
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/analysis/run" `
  -Method POST `
  -Body $body `
  -ContentType "application/json"
```

Salida esperada:

```text
Analysis completed successfully
model_name = SAM
status = completed
particle_count = valor real
total_masks = valor real
valid_masks = valor real
rejected_masks = valor real
```

---

## 10. Probar que SAM2 simulado siga funcionando

```powershell
$body = @{
    micrograph_id = 1
    user_id = 1
    model_name = "SAM2"
    parameters = @{
        points_per_side = 44
    }
} | ConvertTo-Json -Depth 3

Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/analysis/run" `
  -Method POST `
  -Body $body `
  -ContentType "application/json"
```

Salida esperada:

```text
model_name = SAM2
status = completed
particle_count = 0
```

Esto confirma que el sistema tiene dos rutas:

```text
SAM  -> anÃ¡lisis real con SAM clÃ¡sico ViT-H
SAM2 -> anÃ¡lisis simulado temporal
```

---

## 11. Archivos importantes del mÃ³dulo SAM clÃ¡sico

```text
myapp/analysis_engine/legacy_sam_analyzer.py
myapp/analysis_engine/mask_filters.py
myapp/analysis_engine/measurement.py
myapp/analysis_engine/visualization.py
myapp/analysis_engine/chart_generator.py
```

Responsabilidades:

```text
legacy_sam_analyzer.py -> coordina el anÃ¡lisis SAM clÃ¡sico
mask_filters.py        -> filtra barra inferior, letras, ruido y contenedores
measurement.py         -> calcula Ã¡reas y diagonales
visualization.py       -> dibuja bounding boxes y diagonales
chart_generator.py     -> genera figura resumen
```

---

## 12. Problemas comunes

### Error: `ModuleNotFoundError: No module named 'torch'`

Significa que PyTorch no estÃ¡ instalado.

SoluciÃ³n:

```powershell
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

---

### Error: `ModuleNotFoundError: No module named 'segment_anything'`

Significa que SAM no estÃ¡ instalado.

SoluciÃ³n:

```powershell
python -m pip install git+https://github.com/facebookresearch/segment-anything.git
```

---

### Error: `No se encontrÃ³ el checkpoint`

Verificar que exista:

```powershell
Get-ChildItem .\checkpoints -File
```

Debe existir:

```text
sam_vit_h_4b8939.pth
```

---

### Error: `No se pudo abrir la imagen`

En Windows, OpenCV puede fallar con rutas que contienen acentos o caracteres especiales.

El mÃ³dulo `legacy_sam_analyzer.py` usa lectura robusta con:

```python
np.fromfile + cv2.imdecode
```

y escritura robusta con:

```python
cv2.imencode + tofile
```

Esto evita problemas con rutas como:

```text
CÃ³digo de Diego
```

---

### Error: `No es posible conectar con el servidor remoto`

Significa que Flask no estÃ¡ corriendo.

SoluciÃ³n:

```powershell
python run.py
```

Verificar:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/health" -Method GET
```

---

## 13. Notas de diseÃ±o

El modelo SAM clÃ¡sico se integrÃ³ como base funcional heredada del prototipo anterior.

El flujo actual es:

```text
React
â†“
POST /api/analysis/run
â†“
AnalysisService
â†“
LegacySamAnalyzer
â†“
SAM clÃ¡sico ViT-H
â†“
mÃ¡scaras
â†“
filtros
â†“
bounding boxes
â†“
diagonales
â†“
grÃ¡ficas
â†“
mÃ©tricas
â†“
reporte
```

Este flujo permite mantener la compatibilidad con el prototipo anterior y preparar la integraciÃ³n posterior de SAM 2.

---

## 14. Estado actual

Funcionalidades disponibles:

```text
SAM classic:
- ejecuta SAM real ViT-H
- genera imagen anotada
- genera figura resumen
- genera mÃ©tricas JSON
- actualiza AnalysisResult
- permite reporte enriquecido

SAM2:
- flujo simulado temporal
- pendiente de reemplazar por integraciÃ³n SAM 2 real
```

---

## 15. Commit recomendado

DespuÃ©s de crear este archivo:

```powershell
git status
git add SAM_SETUP.md
git commit -m "Document legacy SAM setup"
git push
```

---

## 16. Instalación mediante archivos de dependencias

Además de los comandos manuales, el repositorio incluye archivos separados para instalar las dependencias de SAM clásico.

Instalar PyTorch con CUDA 12.4:

```powershell
python -m pip install -r requirements-torch-cu124.txt
```

Instalar dependencias de procesamiento de imágenes y Segment Anything:

```powershell
python -m pip install -r requirements-sam.txt
```

Orden recomendado:

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-torch-cu124.txt
python -m pip install -r requirements-sam.txt
```

Se separa PyTorch del `requirements.txt` principal porque las versiones con CUDA dependen del equipo, sistema operativo y versión compatible de CUDA.

