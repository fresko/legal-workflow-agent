from openai import OpenAI
client = OpenAI()

response = client.responses.create(
  model="gpt-4.1-mini",
  input=[
    {
      "role": "system",
      "content": [
        {
          "type": "input_text",
          "text": "identifica los datos de expediente,ciudad(Cali o Bogota o Medellin o Barranquilla),hechos,peticiones,cuantia,convocante, convocado, fecha de audicencia, jornada am o pm del archivo adjunto. responda segun este eschema structure_output."
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "Analiza el documento según las instrucciones proporcionadas"
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "extrae datos "
        },
        {
          "type": "input_file",
          "filename": "solicitud_audiencia_balnco.pdf",
          "file_data": "data:application/pdf;base64,"
        }
      ]
    },
    {
      "id": "msg_683e1336aa8081998e96b043cba99b6b051e432c1983583e",
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "{\n  \"ciudad\": \"No especificado claramente\",\n  \"hechos\": \"El día _____ de _____________ de _________ en la (Dirección) ________________________________ se presentó un choque entre los vehículos de placas _____________.\",\n  \"cuantia\": \"\",\n  \"convocados\": [],\n  \"expediente\": \"\",\n  \"peticiones\": \"\",\n  \"convocantes\": [],\n  \"jornada AM/PM\": \"\",\n  \"hora_conciliacion\": \"\",\n  \"fecha_conciliacion\": \"\"\n}"
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "extrae datos"
        },
        {
          "type": "input_file",
          "filename": "caso02.pdf",
          "filetype": "application/pdf",
        }
      ]
    },
    {
      "id": "msg_683e13591e84819980a9cc07570773c5051e432c1983583e",
      "role": "assistant",
      "content": [
        {
          "type": "output_text",
          "text": "{\n  \"ciudad\": \"CALI\",\n  \"hechos\": \"El día 10 de mayo de 2025 en la calle 5 se presentó un choque entre los vehículos de placas BBB333 - AAA222.\",\n  \"cuantia\": \"5.450.000\",\n  \"convocados\": [\n    {\n      \"rol\": \"Conductor\",\n      \"mail\": \"JUAN.PAZ.H@GMAIL.COM\",\n      \"nombre\": \"CARLOS SAENZ\",\n      \"telefono\": \"676767\"\n    },\n    {\n      \"rol\": \"Propietario\",\n      \"mail\": \"AGENTE@DIGITALMAGIA.COM\",\n      \"nombre\": \"CHECO PEREZ\",\n      \"telefono\": \"787878\"\n    }\n  ],\n  \"expediente\": \"CA-3020\",\n  \"peticiones\": \"VALOR DEL SINIESTRO\",\n  \"convocantes\": [\n    {\n      \"rol\": \"Conductor\",\n      \"email\": \"xxxxxxxxxxxxxxxxxxx\",\n      \"nombre\": \"FELIPE PARDO\",\n      \"telefono\": \"\"\n    },\n    {\n      \"rol\": \"Propietario\",\n      \"email\": \"IMPACTA.INC@GMAIL.COM\",\n      \"nombre\": \"PABLO MARMOL\",\n      \"telefono\": \"321000000\"\n    }\n  ],\n  \"jornada AM/PM\": \"A.M.\",\n  \"hora_conciliacion\": \"09:00\",\n  \"fecha_conciliacion\": \"01/06/2025\"\n}"
        }
      ]
    }
  ],
  text={
    "format": {
      "type": "json_schema",
      "name": "schema_description",
      "schema": {
        "type": "object",
        "required": [
          "expediente",
          "ciudad",
          "hechos",
          "peticiones",
          "cuantia",
          "convocantes",
          "convocados",
          "fecha_conciliacion",
          "hora_conciliacion",
          "jornada AM/PM"
        ],
        "properties": {
          "ciudad": {
            "type": "string"
          },
          "hechos": {
            "type": "string"
          },
          "cuantia": {
            "type": "string"
          },
          "convocados": {
            "type": "array",
            "items": {
              "type": "object",
              "required": [
                "rol",
                "nombre",
                "mail",
                "telefono"
              ],
              "properties": {
                "rol": {
                  "type": "string"
                },
                "mail": {
                  "type": "string"
                },
                "nombre": {
                  "type": "string"
                },
                "telefono": {
                  "type": "string"
                }
              },
              "additionalProperties": False
            }
          },
          "expediente": {
            "type": "string"
          },
          "peticiones": {
            "type": "string"
          },
          "convocantes": {
            "type": "array",
            "items": {
              "type": "object",
              "required": [
                "rol",
                "nombre",
                "email",
                "telefono"
              ],
              "properties": {
                "rol": {
                  "type": "string"
                },
                "email": {
                  "type": "string"
                },
                "nombre": {
                  "type": "string"
                },
                "telefono": {
                  "type": "string"
                }
              },
              "additionalProperties": False
            }
          },
          "jornada AM/PM": {
            "type": "string"
          },
          "hora_conciliacion": {
            "type": "string"
          },
          "fecha_conciliacion": {
            "type": "string"
          }
        },
        "additionalProperties": False
      },
      "strict": True
    }
  },
  reasoning={},
  tools=[],
  temperature=1,
  max_output_tokens=4845,
  top_p=1,
  store=True
)