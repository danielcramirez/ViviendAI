# LeadFlow 30X

Prototipo interactivo del reto de vivienda: Meta Ads → perfilamiento del sueño
de vivienda → prioridad comercial explicable → SQLite (gemelo digital de SAP
HANA Cloud) → Salesforce simulado.

La prioridad comercial no es una aprobación de crédito ni una asignación de
subsidio. El prototipo no consulta DataCrédito ni información bancaria real.

## Ejecutar en Windows

```powershell
.\venv\Scripts\Activate.ps1
streamlit run app.py
```

Luego abre `http://localhost:8501`.

## Pruebas

```powershell
.\venv\Scripts\python.exe -m unittest -v
```

La base local `leads.db` se crea automáticamente al iniciar la aplicación.
