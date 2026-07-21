# Referencia de API del backend

Este documento describe los endpoints principales del backend Flask del sistema
de análisis de micrografías TEM/SEM.

El backend permite:

- registrar usuarios
- iniciar sesión
- cargar micrografías
- ejecutar análisis con SAM clásico o SAM 2 simulado
- consultar historial de análisis
- abrir archivos generados
- generar y descargar reportes

---

## 1. URL base local

Durante el desarrollo local, la API se ejecuta en:

```text
http://127.0.0.1:5000
```

Ejemplo:

```text
http://127.0.0.1:5000/api/health
```

---

## 2. Ejecutar el backend

Desde la carpeta `apiMAS`:

```powershell
conda activate tesis-mas-api
python run.py
```

Salida esperada:

```text
Running on http://127.0.0.1:5000
```

---

## 3. Verificar estado del backend

### Endpoint

```http
GET /api/health
```

### Ejemplo PowerShell

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/health" `
  -Method GET
```

### Respuesta esperada

```json
{
  "status": "ok"
}
```

Este endpoint permite comprobar que Flask está corriendo correctamente.

---

## 4. Registrar usuario

### Endpoint

```http
POST /api/auth/register
```

### Descripción

Crea un usuario nuevo en la base de datos local.

### Body JSON

```json
{
  "email": "usuario@example.com",
  "password": "password123",
  "occupation": "Researcher"
}
```

### Ejemplo PowerShell

```powershell
$body = @{
    email = "usuario@example.com"
    password = "password123"
    occupation = "Researcher"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/auth/register" `
  -Method POST `
  -Body $body `
  -ContentType "application/json"
```

### Respuesta esperada

```json
{
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "email": "usuario@example.com",
    "occupation": "Researcher",
    "created_at": "2026-07-21T00:00:00"
  }
}
```

---

## 5. Iniciar sesión

### Endpoint

```http
POST /api/auth/login
```

### Descripción

Valida las credenciales de un usuario registrado.

### Body JSON

```json
{
  "email": "usuario@example.com",
  "password": "password123"
}
```

### Ejemplo PowerShell

```powershell
$body = @{
    email = "usuario@example.com"
    password = "password123"
} | ConvertTo-Json

Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/auth/login" `
  -Method POST `
  -Body $body `
  -ContentType "application/json"
```

### Respuesta esperada

```json
{
  "message": "Login successful",
  "user": {
    "id": 1,
    "email": "usuario@example.com",
    "occupation": "Researcher",
    "created_at": "2026-07-21T00:00:00"
  }
}
```

---

## 6. Cargar micrografía

### Endpoint

```http
POST /api/micrographs/upload
```

### Descripción

Carga una imagen TEM o SEM al backend.

La imagen se guarda en:

```text
uploads/original/
```

### Tipo de petición

```text
multipart/form-data
```

### Campos esperados

```text
file              imagen de micrografía
user_id           identificador del usuario
micrograph_type   TEM o SEM
scale_value       valor de escala, opcional
scale_unit        nm, µm o px
description       descripción opcional
```

### Extensiones permitidas

```text
png, jpg, jpeg, tif, tiff, bmp
```

### Ejemplo PowerShell

```powershell
$form = @{
    file = Get-Item "C:\Users\jesus\Downloads\micrografia_prueba.tif"
    user_id = "1"
    micrograph_type = "TEM"
    scale_value = "100"
    scale_unit = "nm"
    description = "Micrografía de prueba"
}

Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/micrographs/upload" `
  -Method POST `
  -Form $form
```

### Respuesta esperada

```json
{
  "message": "Micrograph uploaded successfully",
  "micrograph": {
    "id": 1,
    "user_id": 1,
    "original_filename": "micrografia_prueba.tif",
    "stored_filename": "uuid_micrografia_prueba.tif",
    "file_path": "ruta/local/uploads/original/uuid_micrografia_prueba.tif",
    "micrograph_type": "TEM",
    "scale_value": 100,
    "scale_unit": "nm",
    "description": "Micrografía de prueba",
    "uploaded_at": "2026-07-21T00:00:00"
  }
}
```

---

## 7. Consultar micrografías

### Endpoint

```http
GET /api/micrographs
```

### Descripción

Obtiene micrografías almacenadas en la base de datos.

Puede recibir `user_id` como parámetro de consulta.

### Ejemplo PowerShell

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/micrographs?user_id=1" `
  -Method GET
```

### Respuesta esperada

```json
{
  "micrographs": [
    {
      "id": 1,
      "user_id": 1,
      "original_filename": "micrografia_prueba.tif",
      "stored_filename": "uuid_micrografia_prueba.tif",
      "micrograph_type": "TEM",
      "scale_value": 100,
      "scale_unit": "nm",
      "description": "Micrografía de prueba",
      "uploaded_at": "2026-07-21T00:00:00"
    }
  ]
}
```

---

## 8. Ejecutar análisis

### Endpoint

```http
POST /api/analysis/run
```

### Descripción

Ejecuta el análisis de una micrografía previamente cargada.

Actualmente existen dos rutas:

```text
SAM  -> ejecuta SAM clásico real con ViT-H
SAM2 -> ejecuta flujo simulado temporal
```

### Body JSON para SAM clásico

```json
{
  "micrograph_id": 1,
  "user_id": 1,
  "model_name": "SAM",
  "parameters": {
    "points_per_side": 44,
    "pred_iou_thresh": 0.85,
    "stability_score_thresh": 0.97,
    "crop_n_layers": 1,
    "crop_n_points_downscale_factor": 2,
    "min_mask_region_area": 1000,
    "box_nms_thresh": 0.5,
    "factor": 5.95,
    "step_number": 10,
    "pixel_threshold": 140
  }
}
```

### Ejemplo PowerShell para SAM clásico

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

### Respuesta esperada para SAM clásico

```json
{
  "message": "Analysis completed successfully",
  "analysis": {
    "id": 1,
    "user_id": 1,
    "micrograph_id": 1,
    "model_name": "SAM",
    "status": "completed",
    "parameters": {
      "points_per_side": 44,
      "pred_iou_thresh": 0.85,
      "stability_score_thresh": 0.97
    },
    "started_at": "2026-07-21T00:00:00",
    "completed_at": "2026-07-21T00:01:00",
    "error_message": null
  },
  "result": {
    "id": 1,
    "analysis_id": 1,
    "particle_count": 12,
    "total_masks": 30,
    "valid_masks": 12,
    "rejected_masks": 18,
    "segmented_image_path": "ruta/local/uploads/segmented/imagen_sam_legacy_annotated.png"
  }
}
```

### Archivos generados por SAM clásico

Cuando se usa `model_name = "SAM"`, se generan archivos en:

```text
uploads/segmented/
```

Archivos esperados:

```text
imagen_sam_legacy_annotated.png
imagen_sam_legacy_summary.png
imagen_sam_legacy_metrics.json
```

Descripción:

```text
*_annotated.png -> imagen con bounding boxes y diagonales
*_summary.png   -> figura resumen con imagen y gráficas
*_metrics.json  -> métricas y distribuciones
```

---

## 9. Ejecutar análisis SAM2 simulado

### Endpoint

```http
POST /api/analysis/run
```

### Body JSON para SAM2

```json
{
  "micrograph_id": 1,
  "user_id": 1,
  "model_name": "SAM2",
  "parameters": {
    "points_per_side": 44
  }
}
```

### Ejemplo PowerShell

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

### Respuesta esperada

```json
{
  "message": "Analysis completed successfully",
  "analysis": {
    "id": 2,
    "user_id": 1,
    "micrograph_id": 1,
    "model_name": "SAM2",
    "status": "completed"
  },
  "result": {
    "id": 2,
    "analysis_id": 2,
    "particle_count": 0,
    "total_masks": 0,
    "valid_masks": 0,
    "rejected_masks": 0,
    "segmented_image_path": "ruta/local/uploads/segmented/imagen_analysis_2_simulated_segmented.tif"
  }
}
```

Nota: en esta etapa, `SAM2` conserva un flujo simulado temporal para validar la arquitectura y la comunicación frontend-backend.

---

## 10. Consultar análisis por ID

### Endpoint

```http
GET /api/analysis/<analysis_id>
```

### Ejemplo

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/analysis/1" `
  -Method GET
```

### Respuesta esperada

```json
{
  "analysis": {
    "id": 1,
    "user_id": 1,
    "micrograph_id": 1,
    "model_name": "SAM",
    "status": "completed",
    "started_at": "2026-07-21T00:00:00",
    "completed_at": "2026-07-21T00:01:00"
  },
  "micrograph": {
    "id": 1,
    "original_filename": "micrografia_prueba.tif",
    "stored_filename": "uuid_micrografia_prueba.tif",
    "micrograph_type": "TEM"
  },
  "result": {
    "particle_count": 12,
    "total_masks": 30,
    "valid_masks": 12,
    "rejected_masks": 18,
    "segmented_image_path": "ruta/local/uploads/segmented/imagen_sam_legacy_annotated.png"
  }
}
```

---

## 11. Consultar historial de análisis

### Endpoint

```http
GET /api/analysis/history
```

### Descripción

Obtiene los análisis realizados por un usuario.

### Parámetro opcional

```text
user_id
```

### Ejemplo PowerShell

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/analysis/history?user_id=1" `
  -Method GET
```

### Respuesta esperada

```json
{
  "analyses": [
    {
      "analysis": {
        "id": 1,
        "user_id": 1,
        "micrograph_id": 1,
        "model_name": "SAM",
        "status": "completed",
        "started_at": "2026-07-21T00:00:00",
        "completed_at": "2026-07-21T00:01:00"
      },
      "micrograph": {
        "id": 1,
        "original_filename": "micrografia_prueba.tif",
        "stored_filename": "uuid_micrografia_prueba.tif",
        "micrograph_type": "TEM"
      },
      "result": {
        "particle_count": 12,
        "total_masks": 30,
        "valid_masks": 12,
        "rejected_masks": 18,
        "segmented_image_path": "ruta/local/uploads/segmented/imagen_sam_legacy_annotated.png"
      }
    }
  ]
}
```

---

## 12. Abrir archivo original

### Endpoint

```http
GET /api/files/original/<filename>
```

### Descripción

Sirve una micrografía original previamente cargada.

### Ejemplo navegador

```text
http://127.0.0.1:5000/api/files/original/uuid_micrografia_prueba.tif
```

### Uso en frontend

```javascript
API_ENDPOINTS.micrographs.originalFile(filename);
```

---

## 13. Abrir archivo segmentado

### Endpoint

```http
GET /api/files/segmented/<filename>
```

### Descripción

Sirve imágenes generadas por el análisis.

Puede servir:

```text
*_sam_legacy_annotated.png
*_sam_legacy_summary.png
*_analysis_<id>_simulated_segmented.*
```

### Ejemplo navegador

```text
http://127.0.0.1:5000/api/files/segmented/imagen_sam_legacy_annotated.png
```

### Uso en frontend

```javascript
API_ENDPOINTS.micrographs.segmentedFile(filename);
```

---

## 14. Generar reporte

### Endpoint

```http
POST /api/reports/generate
```

### Descripción

Genera un reporte de texto asociado a un análisis.

Si el análisis fue realizado con SAM clásico, el reporte incluye:

- conteo de partículas
- total de máscaras
- máscaras válidas
- máscaras rechazadas
- ruta de imagen anotada
- ruta de figura resumen
- distribución de áreas
- distribución de longitudes

### Body JSON

```json
{
  "analysis_id": 1
}
```

### Ejemplo PowerShell

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

### Respuesta esperada

```json
{
  "message": "Report generated successfully",
  "report": {
    "id": 1,
    "analysis_id": 1,
    "filename": "analysis_1_report.txt",
    "file_path": "ruta/local/reports/analysis_1_report.txt",
    "generated_at": "2026-07-21T00:00:00"
  }
}
```

---

## 15. Descargar reporte

### Endpoint

```http
GET /api/reports/<report_id>/download
```

### Descripción

Descarga el archivo `.txt` generado para un análisis.

### Ejemplo navegador

```text
http://127.0.0.1:5000/api/reports/1/download
```

### Uso en frontend

```javascript
API_ENDPOINTS.reports.download(reportId);
```

---

## 16. Flujo completo desde PowerShell

Este flujo prueba:

- carga de micrografía
- análisis con SAM clásico
- generación de reporte

### 16.1 Cargar micrografía

```powershell
$form = @{
    file = Get-Item "C:\Users\jesus\Downloads\micrografia_prueba.tif"
    user_id = "1"
    micrograph_type = "TEM"
    scale_value = "100"
    scale_unit = "nm"
    description = "Micrografía de prueba"
}

$uploadResponse = Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/micrographs/upload" `
  -Method POST `
  -Form $form

$uploadResponse | ConvertTo-Json -Depth 5
```

### 16.2 Ejecutar SAM clásico

```powershell
$micrographId = $uploadResponse.micrograph.id

$analysisBody = @{
    micrograph_id = $micrographId
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

$analysisResponse = Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/analysis/run" `
  -Method POST `
  -Body $analysisBody `
  -ContentType "application/json"

$analysisResponse | ConvertTo-Json -Depth 5
```

### 16.3 Generar reporte

```powershell
$analysisId = $analysisResponse.analysis.id

$reportBody = @{
    analysis_id = $analysisId
} | ConvertTo-Json

$reportResponse = Invoke-RestMethod `
  -Uri "http://127.0.0.1:5000/api/reports/generate" `
  -Method POST `
  -Body $reportBody `
  -ContentType "application/json"

$reportResponse | ConvertTo-Json -Depth 5
```

---

## 17. Flujo desde React

El frontend consume estos endpoints mediante:

```text
src/services/api.js
```

Flujo principal:

```text
Login / Sign up
↓
Report
↓
Upload micrograph
↓
Run analysis
↓
Open segmented image
↓
Open summary figure
↓
Generate report
↓
Download report
```

Historial:

```text
History
↓
GET /api/analysis/history
↓
Open original micrograph
↓
Open segmented image
↓
Open summary figure
↓
Generate report
↓
Download report
```

---

## 18. Códigos de error comunes

### Backend apagado

Error típico en PowerShell:

```text
No es posible conectar con el servidor remoto
```

Solución:

```powershell
python run.py
```

---

### Micrografía no encontrada

Puede ocurrir si se envía un `micrograph_id` que no existe.

Respuesta esperada:

```json
{
  "message": "Micrograph not found"
}
```

---

### Análisis no encontrado

Puede ocurrir al generar reporte con un `analysis_id` inexistente.

Respuesta esperada:

```json
{
  "message": "Analysis not found"
}
```

---

### Resultado de análisis no encontrado

Puede ocurrir si el análisis existe, pero todavía no tiene resultado asociado.

Respuesta esperada:

```json
{
  "message": "Analysis result not found"
}
```

---

### Checkpoint no encontrado

Ocurre cuando se intenta ejecutar SAM clásico sin el archivo:

```text
checkpoints/sam_vit_h_4b8939.pth
```

Solución:

```text
Descargar el checkpoint y colocarlo en apiMAS/checkpoints/
```

---

## 19. Estado actual de la API

Endpoints funcionales:

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

Endpoints heredados temporales:

```text
POST /add
POST /userValidation
```

Los endpoints heredados se mantienen temporalmente por compatibilidad con el prototipo anterior, pero no forman parte del flujo principal actual.

---

## 20. Notas de implementación

La API está organizada alrededor de:

```text
myapp/routes.py
myapp/models.py
myapp/analysis_engine/analysis_service.py
myapp/reporting/report_service.py
```

El flujo de análisis se coordina desde:

```text
AnalysisService.run_analysis()
```

La selección del modelo se realiza con:

```text
model_name = "SAM"
model_name = "SAM2"
```

Cuando `model_name` es `SAM`, se ejecuta:

```text
LegacySamAnalyzer.analyze()
```

Cuando `model_name` es `SAM2`, se ejecuta temporalmente:

```text
AnalysisService.run_simulated_analysis()
```

Esto permite mantener funcional el sistema completo mientras se integra posteriormente SAM 2 real.
