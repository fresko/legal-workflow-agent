import requests
import json


if __name__ == "__main__":
    # URL del webhook
    webhook_url = "https://magia.app.n8n.cloud/webhook-test/6a27e3f7-2323-4341-adf3-e5baa613729c"
    
    # Datos a enviar
    data = {
        "convocantes": [
            {
                "rol": "Demandante",
                "nombre": "Juan Pérez",
                "email": "juan.paz.h@gmail.com"
            }
        ],
        "convocados": [
            {
                "rol": "Demandado",
                "nombre": "Carlos López",
                "mail": "impacta.inc@gmail.com"
            }
        ],
        "fecha_conciliacion": "2025-06-15",
        "hora_conciliacion": "10:30",
        "hechos": "Descripción de los hechos relevantes..."
    }
    
    # Enviar el webhook
    send_webhook(webhook_url, data)