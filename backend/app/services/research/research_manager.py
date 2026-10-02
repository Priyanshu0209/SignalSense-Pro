import uuid
import json
import os
import shutil
from datetime import datetime, timezone
from typing import Dict, List, Any

class ResearchManager:
    def __init__(self):
        self.data_dir = "data"
        self.experiments_file = os.path.join(self.data_dir, "experiments.json")
        self.datasets_dir = os.path.join(self.data_dir, "Datasets")
        os.makedirs(self.datasets_dir, exist_ok=True)
        
        self.experiments: Dict[str, Any] = {}
        self.notes: Dict[str, str] = {}
        
        self._load_state()

    def _load_state(self):
        if os.path.exists(self.experiments_file):
            try:
                with open(self.experiments_file, 'r') as f:
                    data = json.load(f)
                    self.experiments = data.get("experiments", {})
                    self.notes = data.get("notes", {})
            except Exception as e:
                print(f"Error loading experiments: {e}")

    def _save_state(self):
        try:
            with open(self.experiments_file, 'w') as f:
                json.dump({
                    "experiments": self.experiments,
                    "notes": self.notes
                }, f, indent=2)
        except Exception as e:
            print(f"Error saving experiments: {e}")

    def log_experiment(self, env: str, profile_name: str, router_name: str, router_mac: str, esp32_mac: str, sample_count: int, duration: int, status: str, operator: str = "Auto", notes: str = "", metrics: dict = None) -> str:
        exp_id = f"EXP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
        now = datetime.now(timezone.utc)
        
        experiment = {
            "id": exp_id,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "environment": env,
            "calibration_profile": profile_name,
            "router_name": router_name,
            "router_mac": router_mac,
            "esp32_mac": esp32_mac,
            "sample_count": sample_count,
            "duration": duration,
            "operator": operator,
            "notes": notes,
            "status": status,
            "metrics": metrics or {}
        }
        
        self.experiments[exp_id] = experiment
        self.notes[exp_id] = f"# Research Notes for {exp_id}\n\n{notes}"
        
        self._save_state()
        
        # Create dataset folder structure
        exp_dir = os.path.join(self.datasets_dir, env, exp_id)
        os.makedirs(exp_dir, exist_ok=True)
        
        # Save metadata to folder
        with open(os.path.join(exp_dir, "metadata.json"), 'w') as f:
            json.dump(experiment, f, indent=2)
            
        return exp_id
        
    def organize_experiment_files(self, exp_id: str, csv_path: str = None, pdf_path: str = None, graphs: List[str] = None, profile_data: dict = None):
        exp = self.experiments.get(exp_id)
        if not exp:
            return False
            
        env = exp["environment"]
        exp_dir = os.path.join(self.datasets_dir, env, exp_id)
        os.makedirs(exp_dir, exist_ok=True)
        
        if csv_path and os.path.exists(csv_path):
            shutil.copy(csv_path, os.path.join(exp_dir, "dataset.csv"))
            
        if pdf_path and os.path.exists(pdf_path):
            shutil.copy(pdf_path, os.path.join(exp_dir, "report.pdf"))
            
        if graphs:
            graphs_dir = os.path.join(exp_dir, "graphs")
            os.makedirs(graphs_dir, exist_ok=True)
            for g in graphs:
                if os.path.exists(g):
                    shutil.copy(g, os.path.join(graphs_dir, os.path.basename(g)))
                    
        if profile_data:
            with open(os.path.join(exp_dir, "calibration_profile.json"), 'w') as f:
                json.dump(profile_data, f, indent=2)
                
        return True

    def get_all_experiments(self) -> List[Any]:
        return sorted(list(self.experiments.values()), key=lambda x: x["date"] + x["time"], reverse=True)
        
    def get_experiment(self, exp_id: str) -> Any:
        return self.experiments.get(exp_id)

    def get_note(self, exp_id: str) -> str:
        return self.notes.get(exp_id, "")

    def update_note(self, exp_id: str, content: str):
        self.notes[exp_id] = content
        self._save_state()
        return True

research_manager = ResearchManager()

def get_research_manager() -> ResearchManager:
    return research_manager
