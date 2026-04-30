curl -X POST http://10.19.4.45:8080/fl/start \
  -H "Content-Type: application/json" \
  -d '{
    "trainingParams": {
      "epochs": 5,
      "localRounds": 3,
      "globalRounds": 100,
      "minFitClients": 3,
      "minEvaluateClients": 3,
      "minAvailableClients": 3,
      "batchSize": 32,
      "learningRate": 0.001
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