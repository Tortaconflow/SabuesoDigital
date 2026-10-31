# Tareas y Próximos Pasos Recomendados: Sabueso Digital

Este documento registra de manera transparente las funciones operativas concluidas y los puntos de evolución futura cuando la operación comercial de CÍDIKS lo requiera.

---

## 1. Funciones Entregadas y Operativas en 2.0
- [x] Confinamiento de seguridad local (127.0.0.1, debug=False, CORS local).
- [x] Eliminación de credenciales en código y soporte de variables de entorno `.env`.
- [x] Mitigación completa de SSRF y DOM XSS.
- [x] Base de datos relacional local SQLite (`sabueso_cidiks.db`) con auto-migración de datos históricos.
- [x] Carga automática al iniciar (solución definitiva a la pantalla en blanco al recargar con F5).
- [x] Normalización de prioridades (`critical`, `high`, `medium`, `low`) inmune a variaciones de acentos.
- [x] Motor de auditoría visual con Playwright y clasificación estricta (`VERIFICADA_VISIBLE`, `PENDIENTE_REVISION`, `DESCARTADA`, `NO_VERIFICABLE`).
- [x] Copiloto de mensajes en estilo CÍDIKS (Modalidad A: Problema Verificado vs Modalidad B: Oportunidad Exploratoria).
- [x] Confirmación humana obligatoria antes de marcar prospectos como contactados.
- [x] Importador de archivos históricos (.xlsx y .csv) con vista previa, detección de duplicados y reversión (rollback).
- [x] Exportador dual a CSV y Excel nativo (.xlsx).
- [x] Lanzador automático inteligente `iniciar_sabueso.bat` y acceso directo en Escritorio `Sabueso Digital.lnk`.
- [x] 16 pruebas automatizadas de aceptación aprobadas al 100%.

---

## 2. Próximos Pasos Recomendados (Fase Futura)
1. **Rotación de Credenciales:**
   - Rotar las claves de Google Gemini, SerpAPI y Google Maps en sus respectivos paneles de administración, ya que estuvieron en texto plano en la versión 1.0.
2. **Generador de Demos Express Visuales (Fase 9):**
   - Implementar un generador de plantillas estáticas con datos ficticios para que CÍDIKS pueda mostrar una maqueta interactiva en 5 minutos al cliente interesado, sin credenciales reales ni pasarelas de pago.
3. **Recordatorios de Seguimiento en Windows:**
   - Integrar notificaciones nativas de Windows (mediante `win10toast` o PowerShell) cuando haya seguimientos comerciales con fecha para el día actual.
4. **Respaldo Automatizado de SQLite:**
   - Crear una tarea periódica que copie semanalmente `sabueso_cidiks.db` a una carpeta de respaldos comprimida con fecha.
