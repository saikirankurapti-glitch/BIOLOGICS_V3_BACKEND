# Biologics Discovery Platform - Backend

This constitutes the backend core engine for the Biologics Discovery Platform.

## Tech Stack
- **Framework**: FastAPI
- **Language**: Python 3.10+
- **Database**: PostgreSQL (Primary), Redis (Cache/Queue), Neo4j (Optional for graphs)
- **Async Jobs**: Celery + Redis
- **Scientific Libraries**: Biopython, RDKit, Pandas, Scikit-learn, PyTorch, AutoDock Vina

## Setup
1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   uvicorn app.main:app --reload
   ```

## Folder Structure
- `app/`: Main application code
  - `api/`: API route handlers
  - `services/`: External service integrations (PDB, UniProt, etc.)
  - `ml/`: Machine Learning models and inference
  - `db/`: Database models and connection
  - `utils/`: Helper utilities
- `celery_worker/`: Background task configurations

## API Documentation
Once running, visit `http://localhost:8000/docs` for Swagger UI.
