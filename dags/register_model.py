import mlflow
import os
from ultralytics import YOLO

def register():
    print("Démarrage de l'enregistrement...")
    
    # ✅ On déplace les configs MLflow ICI (dans la fonction)
    mlflow.set_tracking_uri("http://mlflow:5000")
    mlflow.set_experiment("Fire_Detection_Prod")
    
    # Chemin vers ton modèle local
    local_model_path = "/opt/airflow/dags/best.pt" 

    if not os.path.exists(local_model_path):
        print(f"❌ Erreur: Le fichier {local_model_path} est introuvable.")
        return

    with mlflow.start_run() as run:
        # On loggue les hyperparamètres (optionnel mais propre)
        mlflow.log_param("model_type", "YOLOv8")
        mlflow.log_param("version", "v1.0")

        # On loggue le modèle comme un artifact générique
        print("📤 Upload vers S3 en cours...")
        mlflow.log_artifact(local_model_path, artifact_path="model")

        # On l'enregistre officiellement
        model_uri = f"runs:/{run.info.run_id}/model"
        mv = mlflow.register_model(model_uri, "FireModelYOLO")
        
        print(f"✅ SUCCÈS ! Modèle enregistré : {mv.name} version {mv.version}")

if __name__ == "__main__":
    register()