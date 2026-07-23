import os
from dotenv import load_dotenv

# Direct path to .env file
base_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(base_dir, '.env'))
load_dotenv(os.path.join(base_dir, '.env.txt'))  # Backup if still named .env.txt

# Verification Print
print("--------------------------------------------------")
print("GROQ KEY STATUS:", "Loaded Successfully! ✅" if os.getenv("GROQ_API_KEY") else "NOT LOADED! ❌")
print("--------------------------------------------------")

# Debug Test: Print to console on server startprint("GROQ KEY STATUS:", "Loaded Successfully!" if os.getenv("GROQ_API_KEY") else "NOT LOADED!"
import json
import threading
from flask import Flask, render_template, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

# Existing Core Pipeline Modules
from utils.protein_prep import prepare_receptor
from utils.ligand_prep import process_ligand_batch
from utils.docking_engine import run_vina_docking
from utils.report_orchestrator import generate_results

# RAG & Literature Imports
from utils.hit_literature_fetcher import fetch_hit_literature
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader

# Groq AI Assistant Import
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

app = Flask(__name__)

# Folders Setup
UPLOAD_FOLDER = os.path.join("data", "uploads")
OUTPUT_FOLDER = os.path.join("outputs", "run_active")

PROTEIN_DIR = os.path.join(UPLOAD_FOLDER, "protein")
LIGAND_DIR = os.path.join(UPLOAD_FOLDER, "ligand")
CONFIG_DIR = os.path.join(UPLOAD_FOLDER, "config")

os.makedirs(PROTEIN_DIR, exist_ok=True)
os.makedirs(LIGAND_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Global Progress Control
PROGRESS_LOCK = threading.Lock()
PROGRESS = {
    "status": "idle",
    "progress": 0,
    "current_compound": "",
    "stage": 0,
    "total_compounds": 0
}

def update_progress(stage, progress, compound="", status="running"):
    with PROGRESS_LOCK:
        PROGRESS["stage"] = stage
        PROGRESS["progress"] = progress
        PROGRESS["current_compound"] = compound
        PROGRESS["status"] = status

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/progress")
def get_progress():
    with PROGRESS_LOCK:
        return jsonify(PROGRESS)

@app.route("/api/results")
def get_results():
    results_file = os.path.join(OUTPUT_FOLDER, "results.json")
    if os.path.exists(results_file):
        with open(results_file, "r") as f:
            return jsonify(json.load(f))
    return jsonify([])

# Helper Function to Save Uploaded Files & Return JSON Always
def handle_upload(request_obj, target_dir):
    try:
        if "file" not in request_obj.files:
            return jsonify({"status": "error", "message": "No file field in request"}), 400
        
        file = request_obj.files["file"]
        if file.filename == "":
            return jsonify({"status": "error", "message": "No file selected"}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(target_dir, filename)
        file.save(filepath)
        
        return jsonify({
            "status": "success", 
            "filename": filename, 
            "filepath": filepath
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# File Upload Endpoints
@app.route("/api/upload/protein", methods=["POST"])
def upload_protein():
    return handle_upload(request, PROTEIN_DIR)

@app.route("/api/upload/ligand", methods=["POST"])
def upload_ligand():
    return handle_upload(request, LIGAND_DIR)

@app.route("/api/upload/config", methods=["POST"])
def upload_config():
    return handle_upload(request, CONFIG_DIR)

@app.route("/api/upload", methods=["POST"])
def upload_generic():
    return handle_upload(request, UPLOAD_FOLDER)

# Global 500 & 404 JSON Error Handlers (Prevents <!doctype html> Error)
@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "message": "API Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"status": "error", "message": "Internal server error occurred"}), 500

# Pipeline Execution Thread
def run_pipeline_thread(config):
    try:
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        update_progress(1, 10, "Preparing Target Protein")
        receptor_file = config.get("receptor_path") or config.get("receptor_id")
        rec_info = prepare_receptor(receptor_file, OUTPUT_FOLDER, ph=7.4)

        update_progress(2, 30, "Preparing Ligand Library Batch")
        sdf_file = config.get("sdf_path")
        ligands = process_ligand_batch(sdf_file, os.path.join(OUTPUT_FOLDER, "ligands"))

        total = len(ligands)
        docking_dir = os.path.join(OUTPUT_FOLDER, "docking_out")
        os.makedirs(docking_dir, exist_ok=True)

        for idx, lig in enumerate(ligands):
            prog = 30 + int((idx / max(total, 1)) * 45)
            update_progress(3, prog, f"Docking compound {idx+1}/{total}")
            run_vina_docking(
                rec_info["receptor_pdbqt"], 
                lig, 
                docking_dir, 
                grid_center=config.get("grid_center", (0.0, 0.0, 0.0))
            )

        update_progress(5, 80, "Generating Analytics & Top Hits Literature")
        results_data = generate_results(OUTPUT_FOLDER, corpus_dir="data/literature", metadata=config)

        top_hits = []
        if isinstance(results_data, list) and len(results_data) > 0:
            top_hits = [hit.get("compound_id", "CMNPD23787") for hit in results_data[:5]]
        else:
            top_hits = ["CMNPD23787"]

        for comp_id in top_hits:
            fetch_hit_literature(comp_id)

        update_progress(5, 92, "Updating RAG FAISS Vector Database")
        lit_dir = "data/literature"
        if os.path.exists(lit_dir) and len(os.listdir(lit_dir)) > 0:
            loader = DirectoryLoader(lit_dir, glob="*.txt", loader_cls=TextLoader)
            docs = loader.load()
            embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            vector_db = FAISS.from_documents(docs, embeddings)
            vector_db.save_local("data/faiss_index")

        update_progress(5, 100, "Screening complete - results and top complexes ready.", status="completed")

    except Exception as e:
        update_progress(0, 0, f"Error: {str(e)}", status="failed")

@app.route("/api/start", methods=["POST"])
def start_pipeline():
    config = request.json or {}
    thread = threading.Thread(target=run_pipeline_thread, args=(config,))
    thread.start()
    return jsonify({"status": "started"})

@app.route("/api/chat", methods=["POST"])
def ai_chat():
    data = request.json or {}
    user_prompt = data.get("prompt", "")
    
    if not GROQ_AVAILABLE:
        return jsonify({"response": "Groq package missing. Please install via pip install groq"}), 500
        
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return jsonify({"response": "GROQ_API_KEY environment variable set nahi hai."}), 400

    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are an expert AI Research Assistant specialized in computational biochemistry and virtual screening analysis."},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3
        )
        answer = completion.choices[0].message.content
        return jsonify({"response": answer})
    except Exception as e:
        return jsonify({"response": f"Error communicating with AI Assistant: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)