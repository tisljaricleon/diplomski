curl -X POST http://10.19.4.45:8080/fl/start \
  -H "Content-Type: application/json" \
  -d '{
    "trainingParams": {
      "epochs": 5,
      "localRounds": 2,
      "globalRounds": 10,
      "minFitClients": 2,
      "minEvaluateClients": 2,
      "minAvailableClients": 2,
      "batchSize": 32,
      "learningRate": 0.001,
      "aomRoundsThreshold": 3,
      "aomSelectionEnabled": true,
      "inflightThreshold": 9999999.0,
      "serverEvalEveryRounds": 1,
      "serverEvalMaxBatches": 50
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