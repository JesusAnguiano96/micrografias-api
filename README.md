# Micrograph Analysis System - Backend

Backend Flask para el sistema de análisis de micrografías TEM/SEM orientado al conteo de nanopartículas esféricas.

Este backend permite cargar micrografías, ejecutar análisis de segmentación, almacenar resultados, consultar historial y generar reportes de análisis.

---

## Estado actual del backend

El sistema cuenta actualmente con dos rutas de análisis:

```text
SAM  -> análisis real usando Segment Anything Model clásico ViT-H
SAM2 -> flujo simulado temporal para validar arquitectura
```

El flujo funcional principal es:

```text
React frontend
↓
Flask API
↓
Carga de micrografía
↓
Análisis SAM / SAM2
↓
Generación de imagen segmentada
↓
Generación de figura resumen
↓
Almacenamiento de resultados
↓
Generación de reporte
```

---

## Tecnologías principales

```text
Python 3.10
Flask
Flask-CORS
Flask-SQLAlchemy
SQLite
PyTorch
Segment Anything
OpenCV
Matplotlib
NumPy
Pillow
```

---

## Estructura principal

```text
apiMAS/
├── myapp/
│   ├── __init__.py
│   ├── extensions.py
│   ├── models.py
│   ├── routes.py
│   ├── analysis_engine/
│   │   ├── analysis_service.py
│   │   ├── legacy_sam_analyzer.py
│   │   ├── mask_filters.py
│   │   ├── measurement.py
│   │   ├── visualization.py
│   │   └── chart_generator.py
│   └── reporting/
│       └── report_service.py
├── checkpoints/
├── uploads/
│   ├── original/
│   └── segmented/
├── reports/
├── tools/
├── requirements.txt
├── requirements-sam.txt
├── requirements-torch-cu124.txt
├── SAM_SETUP.md
├── API_REFERENCE.md
├── README.md
└── run.py
```

---

## Carpetas generadas localmente

Durante la ejecución local se utilizan las siguientes carpetas:

```text
uploads/original/     -> micrografías originales cargadas por el usuario
uploads/segmented/    -> imágenes generadas por los análisis
reports/              -> reportes TXT generados
checkpoints/          -> modelos/checkpoints locales
outputs/              -> salidas de pruebas locales
```

Estas carpetas pueden contener archivos pesados o generados automáticamente, por lo que se ignoran en Git mediante `.gitignore`.

---

## Instalación rápida

Desde la carpeta `apiMAS`:

```powershell
conda create -n tesis-mas-api python=3.10
conda activate tesis-mas-api
pip install -r requirements.txt
```

Para instalar las dependencias de SAM clásico:

```powershell
python -m pip install -r requirements-torch-cu124.txt
python -m pip install -r requirements-sam.txt
```

---

## Configuración de SAM clásico

El análisis real con SAM clásico requiere el checkpoint:

```text
checkpoints/sam_vit_h_4b8939.pth
```

Este archivo no se sube al repositorio porque es pesado.

La configuración detallada de SAM clásico está documentada en:

```text
SAM_SETUP.md
```

Ese documento incluye:

```text
- instalación de PyTorch con CUDA
- instalación de Segment Anything
- descarga del checkpoint ViT-H
- prueba del módulo SAM clásico
- prueba desde endpoint Flask
- problemas comunes
```

---

## Ejecutar el backend

Activar el ambiente:

```powershell
conda activate tesis-mas-api
```

Ejecutar Flask:

```powershell
python run.py
```

Salida esperada:

```text
Running on http://127.0.0.1:5000
```

---

## Verificar que la API esté funcionando

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/health" `
  -Method GET
```

Respuesta esperada:

```json
{
  "status": "ok"
}
```

---

## Endpoints principales

```text
GET  /api/health
POST /api/auth/register
POST /api/auth/login
POST /api/micrographs/upload
GET  /api/micrographs
POST /api/analysis/run
GET  /api/analysis/<analysis_id>
GET  /api/analysis/history
GET  /api/files/original/<filename>
GET  /api/files/segmented/<filename>
POST /api/reports/generate
GET  /api/reports/<report_id>/download
```

La documentación completa de la API está disponible en:

```text
API_REFERENCE.md
```

---

## Flujo de análisis con SAM clásico

Cuando el frontend o un cliente externo envía:

```json
{
  "model_name": "SAM"
}
```

el backend ejecuta el flujo real de SAM clásico:

```text
AnalysisService.run_analysis()
↓
AnalysisService.run_legacy_sam_analysis()
↓
LegacySamAnalyzer.analyze()
↓
SAM ViT-H
↓
generación de máscaras
↓
filtrado de máscaras
↓
medición de partículas
↓
imagen anotada
↓
figura resumen
↓
métricas JSON
↓
registro en base de datos
```

---

## Archivos generados por SAM clásico

Para una micrografía analizada con SAM clásico se generan archivos en:

```text
uploads/segmented/
```

Ejemplo:

```text
micrografia_sam_legacy_annotated.png
micrografia_sam_legacy_summary.png
micrografia_sam_legacy_metrics.json
```

Descripción:

```text
*_annotated.png -> imagen con bounding boxes y diagonales
*_summary.png   -> figura resumen con imagen anotada y gráficas
*_metrics.json  -> métricas, áreas, diagonales y distribuciones
```

---

## Flujo SAM2 temporal

Cuando se envía:

```json
{
  "model_name": "SAM2"
}
```

el backend ejecuta actualmente un flujo simulado:

```text
AnalysisService.run_simulated_analysis()
```

Este flujo copia la micrografía original como salida temporal y registra un resultado con conteos en cero.

Este comportamiento se mantiene para validar la arquitectura mientras se integra posteriormente el modelo SAM 2 real.

---

## Base de datos local

El backend utiliza SQLite durante el desarrollo local.

El archivo se crea automáticamente como:

```text
mas_local.db
```

La base de datos se inicializa desde la app factory mediante:

```text
db.create_all()
```

El archivo `.db` no se sube a GitHub.

---

## Modelos principales

Los modelos definidos en `myapp/models.py` son:

```text
User
Micrograph
Analysis
AnalysisResult
Report
PlantEntry
```

`PlantEntry` es un modelo heredado temporal del prototipo anterior.

---

## Reportes

El servicio de reportes se encuentra en:

```text
myapp/reporting/report_service.py
```

El endpoint:

```text
POST /api/reports/generate
```

genera un reporte `.txt` asociado a un análisis.

Para análisis con SAM clásico, el reporte incluye:

```text
- conteo de partículas
- total de máscaras
- máscaras válidas
- máscaras rechazadas
- ruta de imagen anotada
- ruta de figura resumen
- distribución de áreas
- distribución de longitudes
```

---

## Prueba rápida del flujo desde PowerShell

### 1. Ejecutar análisis

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
        box_nms_thresh = 0.5
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

### 2. Generar reporte

```powershell
$body = @{
    analysis_id = 1
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/reports/generate" `
  -Method POST `
  -Body $body `
  -ContentType "application/json"
```

---

## Documentación adicional

```text
SAM_SETUP.md      -> instalación y configuración de SAM clásico
API_REFERENCE.md  -> documentación completa de endpoints
```

---

## Notas importantes

El checkpoint de SAM clásico no se incluye en el repositorio.

Debe colocarse manualmente en:

```text
checkpoints/sam_vit_h_4b8939.pth
```

Los archivos generados localmente tampoco se suben al repositorio:

```text
uploads/
outputs/
reports/
*.db
```

---

## Estado del prototipo

Funcionalidades implementadas:

```text
- registro de usuarios
- inicio de sesión
- carga de micrografías TEM/SEM
- almacenamiento local de micrografías
- análisis real con SAM clásico ViT-H
- análisis temporal simulado para SAM2
- generación de imagen anotada
- generación de figura resumen
- almacenamiento de resultados
- consulta de historial
- generación de reportes TXT
- descarga de reportes
```

Pendiente para etapas posteriores:

```text
- integración real de SAM 2
- autenticación persistente con tokens/sesiones
- almacenamiento en infraestructura cloud
- reportes en PDF
- configuración avanzada desde interfaz
- despliegue completo como SaaS
```
