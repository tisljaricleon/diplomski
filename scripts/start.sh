curl -X POST http://10.19.4.45:8080/fl/start \
  -H "Content-Type: application/json" \
  -d '{
    "trainingParams": {
      "epochs": 5,
      "localRounds": 2,
      "globalRounds": 16,
      "minFitClients": 3,
      "minEvaluateClients": 3,
      "minAvailableClients": 3,
      "batchSize": 64,
      "learningRate": 0.0003,
      "aomRoundsThreshold": 2,
      "aomSelectionEnabled": true,
      "inflightThreshold": 15.0
    },
    "inferenceParams": {
      "enableServing": true
    },
    "modelSize": 1.0,
    "costSource": "communication",
    "costConfiguration": {
      "costType": "totalBudget",
      "budget": 1000000
    },
    "configurationModel": "minKld",
    "rvaEnabled": false
  }'