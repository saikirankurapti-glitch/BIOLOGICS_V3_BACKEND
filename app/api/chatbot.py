from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from groq import Groq

router = APIRouter()

# Initialize Groq Client
API_KEY = os.getenv("GROQ_API_KEY", "YOUR_API_KEY_HERE")

try:
    from groq import Groq
    client = Groq(api_key=API_KEY)
except ImportError:
    print("Groq library not found. Install with `pip install groq`.")
    client = None
except Exception as e:
    print(f"Failed to initialize Groq client: {e}")
    client = None

class ChatRequest(BaseModel):
    message: str
    context: str = "" # Optional context from the page the user is on

from app.db.vector_store import vector_store

@router.post("/ask")
async def ask_chatbot(request: ChatRequest):
    if not client:
        raise HTTPException(status_code=503, detail="Chat service unavailable (API Key Error).")

    # RAG: Retrieve relevant context from Vector Store
    relevant_docs = vector_store.query(request.message, n_results=3)
    retrieved_context = "\n".join(relevant_docs) if relevant_docs else "No specific document context found."

    system_prompt = """You are 'BioAssist', an advanced AI assistant embedded in the Biologics Discovery Platform. 
Your goal is to help scientists navigate the platform and answer complex biological/pharma questions.

PLATFORM NAVIGATION GUIDE:
1. Target Explorer: Search for targets (proteins/genes) and view 3D structures.
2. Structural Docking: Predict binding orientations and energies using AutoDock Vina.
3. Hit Screening: Upload .smi files to screen millions of compounds using XGBoost.
4. Lead Optimization: Use Genetic Algorithms to evolve/mutate a hit into a better candidate.
5. ADMET Intelligence: Predict pharmacokinetics and toxicity.
6. Wet-Lab Validation: Generate protocols (OT-2) for physical testing.

SCIENTIFIC PERSONA:
- You are an expert in Computational Biology, Medicinal Chemistry, and Pharmacology.
- Use retrieved document context when provided to answer specific scientific queries.
- Be concise, professional, and helpful.
"""

    try:
        full_user_content = f"Context from Platform: {request.context}\nKnowledge Base Context: {retrieved_context}\n\nUser Question: {request.message}"
        
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_user_content}
            ],
            temperature=0.3, # Lower temperature for higher factuality
            max_tokens=800,
            top_p=1,
            stream=False,
        )
        
        return {
            "response": completion.choices[0].message.content,
            "rag_context_used": len(relevant_docs) > 0
        }

    except Exception as e:
        print(f"Groq API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
