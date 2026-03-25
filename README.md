
# README.md

Option A — Stack complète (Docker)
 
  # 1. Copier et configurer les variables
  cp .env.example .env                                                                                                                                                                         
  # Éditer .env : renseigner POSTGRES_PASSWORD, JWT_SECRET HF_TOKEN                                                                                                                        
  
  # 2. Lancer tous les services                                                                                                                                                             
  docker compose up --build                                                                                                                                                                                                                              
  # 3. Créer le premier compte admin                                                                                                                                                        
  docker compose exec api python create_admin.py                                                                                                                                            
  
  # 
    cd api
  python create_admin.py --email admin@kreyol.mq --password NouveauMotDePasse!

  URLs disponibles :                                                                                                                                                                        
  ┌───────────────┬────────────────────────────┐               
  │    Service    │            URL             │                                                                                                                                            
  ├───────────────┼────────────────────────────┤                                                                                                                                            
  │ API (Swagger) │ http://localhost:8000/docs │                                                                                                                                            
  ├───────────────┼────────────────────────────┤            
  │ Frontend      │ http://localhost:3000      │                                                                                                                                            
  ├───────────────┼────────────────────────────┤
  │ Adminer (DB)  │ http://localhost:8080      │                                                                                                                                            
  └───────────────┴────────────────────────────┘                                                                                                                                                
  ---                                                                                                                                                                                          
  Option B — API seule (sans Docker)                        

  cd api
  python -m venv .venv && source .venv/bin/activate                                                                                                                                            
  pip install -r requirements.txt
                                                                                                                                                                                           
  # Lancer (nécessite PostgreSQL déjà démarré)              
  uvicorn app.main:app --reload --port 8000                                                                                                                                                    
---                                                                                                                                                                                          
  Option C — Tests unitaires (SQLite, sans Docker)                                                                                                                                          
  cd api                                                    
  source .venv/bin/activate  # si venv déjà créé                                                                                                                                            
  pytest tests/ -v                                                                                                                                                                          
  19 tests passent, 2 skippés (nécessitent pg_trgm). 